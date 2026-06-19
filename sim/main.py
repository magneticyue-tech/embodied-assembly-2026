"""
main.py — 主控状态机 (端到端跑通赛题全流程)

完整具身智能闭环:
  语音唤醒 -> 任务卡识别(VLM) -> 语音复述 -> [闭环装配 6 块] -> 完成播报。

托盘策略 (本版重点, 解决整块板 + 遮挡):
- 开局无遮挡时, 检测板位姿并【一次性标定】颜色->板局部坐标 (之后不再重识别颜色)。
- 每步装配前: 重测【板位姿】(靠外轮廓, 不被方块遮挡) + 重测自由方块位置(闭环再感知);
  目标色槽位置 = 板位姿 ⊕ 标定布局。放置后槽色被盖、或板被挪, 都不影响。

运行: cd sim && python main.py
产物: output/ 标注图 + parse_log_*.txt (带时间戳)。
"""
import os
import sys
import datetime
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
import annotate
from execution import Robot

_T0 = datetime.datetime(2026, 6, 17, 10, 0, 0)
_tick = [0]


def now_iso():
    _tick[0] += 1
    return (_T0 + datetime.timedelta(seconds=_tick[0])).isoformat()


class Log:
    def __init__(self, path):
        self.path = path
        self.lines = []

    def __call__(self, msg):
        line = f"[{now_iso()}] {msg}"
        self.lines.append(line)
        print(line)

    def flush(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines))


def speak(log, text):
    log(f"  [语音TTS] 「{text}」")


def save(img, name):
    path = os.path.join(C.OUTPUT_DIR, name)
    cv2.imwrite(path, img)
    return path


def run_task1(scene, log, slot_local):
    log("=== 任务一: 场景识别 ===")
    speak(log, "我已就绪，请下达指令")
    img = camera.render(scene)
    board = vision.detect_board_pose(img)
    blocks = vision.detect_blocks(img, board)
    desc = f"待装配区检测到{len(blocks)}个方块, 装配区检测到1块托盘板(含{len(slot_local)}个色槽)"
    parsed = cognition.parse_card1(desc, now_iso())
    ok, errmsg = cognition.check_confidence(parsed)
    if not ok:
        speak(log, errmsg); return False
    log(f"  [VLM] 场景解析: {parsed['description']} (conf={parsed['confidence']})")
    vis = annotate.draw(img, board, slot_local, blocks, "Task1 Scene Recognition")
    log(f"  [界面] 标注图 -> {save(vis, 'task1_scene.png')}")
    speak(log, f"场景识别完成，{desc}")
    speak(log, "任务已完成")
    return True


def run_task2(scene, log, slot_local):
    log("=== 任务二: 装配指令识别与执行 ===")
    speak(log, "我已就绪，请下达指令")
    parsed = cognition.parse_card2(cognition.SAMPLE_CARD2, now_iso())
    ok, errmsg = cognition.check_confidence(parsed)
    if not ok:
        speak(log, errmsg); return False
    log(f"  [VLM] 指令解析 JSON: {parsed['sequence']}")
    speak(log, "已识别装配指令，开始复述并执行")
    robot = Robot(log)
    rings = []
    for item in parsed["sequence"]:
        bc, tc, step = item["block_color"], item["tray_color"], item["step"]
        log(f"-- 第{step}步: {bc}块 -> {tc}托盘 (高亮当前步骤) --")
        speak(log, f"正在执行第{step}步，抓取{bc}方块，放到{tc}托盘")
        scene.perturb()                                  # 裁判中途挪动方块+托盘板
        img = camera.render(scene)
        board = vision.detect_board_pose(img)            # 重测板位姿(外轮廓, 遮挡鲁棒)
        blocks = vision.detect_blocks(img, board)        # 重测自由方块(闭环再感知)
        if board is None or bc not in blocks:
            speak(log, f"未定位到{bc}块或托盘板，重新感知"); continue
        # 目标槽位置 = 板位姿 ⊕ 开局标定布局 (不靠重识别颜色, 槽色被盖也不怕)
        slot = vision.slot_table_pos(tc, board, slot_local)
        true_slot = scene.slot_table_pos(tc)
        pick_err = robot.pick(bc, blocks[bc], scene.blocks[bc])
        total, ring, ok2 = robot.place(bc, tc, slot, true_slot, pick_err)
        rings.append((step, bc, tc, total, ring))
        scene.place_block(bc, slot["x"], slot["y"], slot["deg"])  # 放上托盘(盖住槽色)
        vis = annotate.draw(img, board, slot_local, blocks,
                            f"Task2 Step{step}: {bc}->{tc}", highlight=(bc, tc))
        save(vis, f"task2_step{step}_{bc}.png")
    log(f"  [界面] 各步标注图已保存至 {C.OUTPUT_DIR}/")
    log("  [评分汇总] " + "; ".join(
        f"第{s}步 {b}->{t} 偏移{o:.1f}mm(第{r}环)" for s, b, t, o, r in rings))
    speak(log, "任务已完成")
    return True


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    log = Log(os.path.join(C.OUTPUT_DIR, "parse_log_20260617.txt"))
    log("[唤醒KWS] 检测到唤醒词「小具同学」")
    scene = S.Scene(seed=7)

    # 开局一次性标定: 板位姿 + 颜色->板局部坐标 (此时无遮挡)
    img0 = camera.render(scene)
    board0 = vision.detect_board_pose(img0)
    slot_local = vision.calibrate_slots(img0, board0)
    log(f"  [标定] 检测托盘板位姿 + 标定 {len(slot_local)} 个色槽布局 (开局一次, 颜色固定)")
    save(annotate.draw(img0, board0, slot_local, vision.detect_blocks(img0, board0),
                       "Initial Scene + Slot Calibration"), "00_initial_scene.png")
    log(f"  [界面] 初始场景 -> {C.OUTPUT_DIR}/00_initial_scene.png")

    r1 = run_task1(scene, log, slot_local)
    r2 = run_task2(scene, log, slot_local)
    if r1 and r2:
        speak(log, "两个任务均已完成")
    log.flush()
    print(f"\n解析日志(带时间戳)已保存: {log.path}")


if __name__ == "__main__":
    main()
