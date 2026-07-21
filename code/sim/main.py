"""
main.py — 主控状态机 (端到端跑通赛题全流程)

流程:
  语音唤醒 -> 任务卡解析(当前为规则桩) -> 语音复述 -> [闭环装配 6 块] -> 完成播报。

依赖注入 + 面向接口:
- 主流程只依赖 interfaces 中的抽象契约, 通过构造把具体实现注入:
    相机 CameraSource / 视觉 VisionModule / 认知 CognitionModule /
    机器人 RobotController / 交互 InteractionModule / 评分 RingEvaluator。
  更换实现 (仿真桩 <-> 真机) 时主流程不变; 行为一致性需联调验证。

托盘策略:
- 开局无遮挡时, 检测板位姿并一次性标定颜色->板局部坐标 (之后不再重识别颜色)。
- 每步装配前: 重测板位姿 (依据外轮廓) + 重测自由方块位置 (闭环再感知);
  目标色槽位置 = 板位姿 ⊕ 标定布局。

运行: cd sim && python main.py
产物: output/ 标注图 + parse_log_*.txt (带时间戳)。
"""
# <!--A-->
import os
import sys
import cv2

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config as C
import scene as S
import camera
import vision
import cognition
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))
import execution
import interaction
import voice_interaction
import annotate


def save(img, name):
    path = os.path.join(C.OUTPUT_DIR, name)
    cv2.imwrite(path, img)
    return path


def run_task1(vis, cog, cam, io, slot_local):
    io.log("=== 任务一: 场景识别 ===")
    io.speak("我已就绪，请下达指令")
    img = cam.capture()
    board = vis.detect_board_pose(img)
    if board is None:
        io.log("  [感知] 未定位到托盘板，任务一终止")
        io.speak("未定位到托盘板，请检查工作区")
        return False
    blocks = vis.detect_blocks(img, board)
    desc = f"待装配区检测到{len(blocks)}个方块, 装配区检测到1块托盘板(含{len(slot_local)}个色槽)"
    parsed = cog.parse_card1(desc, io.now())
    ok, errmsg = cog.check_confidence(parsed)
    if not ok:
        io.speak(errmsg); return False
    io.log(f"  [认知/规则桩] 场景解析: {parsed['description']} (conf={parsed['confidence']})")
    vis_img = annotate.draw(img, board, slot_local, blocks, "Task1 Scene Recognition")
    io.log(f"  [界面] 标注图 -> {save(vis_img, 'task1_scene.png')}")
    io.speak(f"场景识别完成，{desc}")
    io.speak("任务已完成")
    return True


def run_task2(scene, vis, cog, robot, evaluator, cam, io, slot_local):
    io.log("=== 任务二: 装配指令识别与执行 ===")
    io.speak("我已就绪，请下达指令")
    parsed = cog.parse_card2(cognition.SAMPLE_CARD2, io.now())
    ok, errmsg = cog.check_confidence(parsed)
    if not ok:
        io.speak(errmsg); return False
    io.log(f"  [认知/规则桩] 指令解析 JSON: {parsed['sequence']}")
    io.speak("已识别装配指令，开始复述并执行")
    rings = []
    all_ok = True
    for item in parsed["sequence"]:
        bc, tc, step = item["block_color"], item["tray_color"], item["step"]
        io.log(f"-- 第{step}步: {bc}块 -> {tc}托盘 (高亮当前步骤) --")
        io.speak(f"正在执行第{step}步，抓取{bc}方块，放到{tc}托盘")
        scene.perturb()                                  # 模拟裁判中途挪动方块+托盘板
        img = cam.capture()
        board = vis.detect_board_pose(img)               # 重测板位姿 (依据外轮廓)
        blocks = vis.detect_blocks(img, board)           # 重测自由方块 (闭环再感知)
        if board is None or bc not in blocks:
            all_ok = False
            io.log(f"  [安全停止] 未定位到{bc}块或托盘板，终止本次装配")
            io.speak(f"未定位到{bc}块或托盘板，请停止操作并申请重抽任务卡")
            break
        # 目标槽位置 = 板位姿 ⊕ 开局标定布局 (不重识别颜色)
        slot = vis.slot_table_pos(tc, board, slot_local)
        try:
            robot.pick(bc, blocks[bc])
            pick_err = evaluator.score_pick(bc, blocks[bc])
            robot.place(bc, tc, slot)
        except execution.RobotExecutionError as exc:
            all_ok = False
            io.log(f"  [安全停止] {exc}")
            io.speak("机械臂执行失败，请停止操作并申请重抽任务卡")
            break

        total, ring, ok2 = evaluator.score_place(tc, slot, pick_err)
        if not ok2:
            all_ok = False
        rings.append((step, bc, tc, total, ring))
        scene.place_block(bc, slot["x"], slot["y"], slot["deg"])  # 放上托盘(覆盖槽色)
        vis_img = annotate.draw(img, board, slot_local, blocks,
                                f"Task2 Step{step}: {bc}->{tc}", highlight=(bc, tc))
        save(vis_img, f"task2_step{step}_{bc}.png")
    io.log(f"  [界面] 各步标注图已保存至 {C.OUTPUT_DIR}/")
    io.log("  [评分汇总] " + "; ".join(
        f"第{s}步 {b}->{t} 偏移{o:.1f}mm(第{r}环)" for s, b, t, o, r in rings))
    if all_ok:
        io.speak("任务已完成")
    else:
        io.speak("任务执行完成，但部分步骤存在问题")
    return all_ok


def create_robot(io, args):
    run_mode = getattr(C, 'RUN_MODE', 'sim')
    if args and args.mode:
        run_mode = args.mode

    if run_mode == "real":
        if not getattr(C, "REAL_PERCEPTION_READY", False):
            raise RuntimeError(
                "真机模式已阻止: 当前入口仍使用 SimCamera，尚未接入真实相机链路"
            )
        if not getattr(C, "REAL_TRANSFORM_CALIBRATED", False):
            raise RuntimeError(
                "真机模式已阻止: 台面到机器人基座的坐标变换尚未完成标定"
            )

        host = getattr(C, 'ROBOT_HOST', '127.0.0.1')
        port = getattr(C, 'ROBOT_PORT', 5000)
        transform_config = getattr(C, 'TRANSFORM_CONFIG', execution.DEFAULT_TRANSFORM_CONFIG)

        if args:
            if args.robot_host:
                host = args.robot_host
            if args.robot_port:
                port = args.robot_port
            if args.x_offset is not None:
                transform_config = dict(transform_config, x_offset=args.x_offset)
            if args.y_offset is not None:
                transform_config = dict(transform_config, y_offset=args.y_offset)
            if args.rotation_deg is not None:
                transform_config = dict(transform_config, rotation_deg=args.rotation_deg)
            if args.scale is not None:
                transform_config = dict(transform_config, scale=args.scale)

        io.log(f"  [模式] 真机模式: 连接 AUBO-i5 @ {host}:{port}")
        return execution.AuboRobot(io, transform_config=transform_config, host=host, port=port)
    else:
        io.log("  [模式] 仿真模式: 使用 SimRobot")
        return execution.SimRobot(io)


def main():
    args = execution.parse_args()
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)

    # 依赖装配: 主流程只依赖抽象接口, 这里注入仿真实现。
    log_path = os.path.join(C.OUTPUT_DIR, "parse_log_20260617.txt")

    use_voice = getattr(C, 'USE_VOICE', False)
    if args and hasattr(args, 'voice') and args.voice:
        use_voice = True

    if use_voice:
        io = voice_interaction.VoiceInteraction(log_path)
    else:
        io = interaction.ConsoleInteraction(log_path)
    vis = vision.OpenCVVision()
    cog = cognition.RuleBasedCognition()
    scene = S.Scene(seed=7)
    cam = camera.SimCamera(scene)
    robot = create_robot(io, args)
    evaluator = execution.RingEvaluator(scene, io)

    try:
        io.wake()

        # 开局一次性标定: 板位姿 + 颜色->板局部坐标 (此时无遮挡)
        img0 = cam.capture()
        board0 = vis.detect_board_pose(img0)
        if board0 is None:
            io.log("  [标定失败] 未定位到托盘板")
            io.speak("未定位到托盘板，请检查工作区")
            return 1

        slot_local = vis.calibrate_slots(img0, board0)
        missing_slots = set(C.COLORS).difference(slot_local)
        if missing_slots:
            missing = ", ".join(sorted(missing_slots))
            io.log(f"  [标定失败] 未识别全部色槽，缺少: {missing}")
            io.speak("托盘色槽标定不完整，请检查工作区")
            return 1

        io.log(f"  [标定] 检测托盘板位姿 + 标定 {len(slot_local)} 个色槽布局 (开局一次, 颜色固定)")
        save(annotate.draw(img0, board0, slot_local, vis.detect_blocks(img0, board0),
                           "Initial Scene + Slot Calibration"), "00_initial_scene.png")
        io.log(f"  [界面] 初始场景 -> {C.OUTPUT_DIR}/00_initial_scene.png")

        r1 = run_task1(vis, cog, cam, io, slot_local)
        r2 = run_task2(scene, vis, cog, robot, evaluator, cam, io, slot_local)
        if r1 and r2:
            io.speak("两个任务均已完成")
            return 0

        io.speak("任务未全部完成，请检查日志")
        return 1
    finally:
        if hasattr(robot, "close"):
            robot.close()
        io.flush()
        print(f"\n解析日志(带时间戳)已保存: {io.path}")


if __name__ == "__main__":
    raise SystemExit(main())
