"""
execution.py — 执行层 (机器人控制的仿真替身, 对应 AUBO-i5)

真实赛场: 坐标变换链 -> 运动规划 -> 吸盘抓放 (AUBO-i5)。
本仿真: 验证逻辑正确性 —— 给定视觉的台面坐标+角度, 记录抓放动作, 评估定位误差,
并以同心环精度尺的环数读出最终放置偏移 (对应托盘评分方式)。
不做物理动力学 (pybullet 未接入; 真机用 AUBO SDK / ARCS 仿真)。

误差构成: AUBO-i5 厂商标称重复定位精度 ±0.02mm; 本仿真的放置偏移
只计算视觉定位误差, 未包含机械臂误差与标定误差。

拆分 (符合 interfaces 契约):
  - SimRobot 实现 interfaces.RobotController — 只负责运动, 不接触 ground-truth。
  - RingEvaluator 是仿真专属评分器 (不属于任何 Protocol), 用 scene 真值计算
    定位误差与落环。
"""
import math
import config as C
import interfaces


def offset_to_ring(offset_mm):
    """把放置偏移 (mm) 换算成落在第几环 (1mm/环, 每 5mm 加粗)。"""
    ring = int(round(offset_mm / C.RING_STEP_MM))
    bold = " (加粗环)" if ring % C.RING_BOLD_EVERY == 0 and ring > 0 else ""
    return ring, bold


class SimRobot:
    """实现 interfaces.RobotController: 只负责运动 (抓/放), 不接触 ground-truth。"""

    def __init__(self, io):
        self.io = io
        self.held = None

    def pick(self, color, target):
        self.io.log(f"  [执行] AUBO-i5 移至拍照点上方 -> 对准 {color}块 中心({target['x']:.1f},{target['y']:.1f})mm 角度{target['deg']:+.1f}° -> 吸盘抓取")
        self.held = color

    def place(self, block_color, tray_color, target):
        self.io.log(f"  [执行] 搬运 {block_color}块 -> {tray_color}托盘中心({target['x']:.1f},{target['y']:.1f})mm -> 释放吸盘")
        self.held = None


class RingEvaluator:
    """仿真专属评分 (非 Protocol): 用 scene 真值计算定位误差与同心环落环。"""

    def __init__(self, scene, io):
        self.scene = scene
        self.io = io

    def score_pick(self, color, det_block):
        t = self.scene.blocks[color]
        derr = math.dist((det_block['x'], det_block['y']), (t['x'], t['y']))
        aerr = abs(_fold90(det_block['deg'] - t['deg']))
        self.io.log(f"  [执行] 视觉定位误差 {derr:.2f}mm, 角度误差 {aerr:.1f}°")
        return derr

    def score_place(self, tray_color, det_slot, pick_err):
        true_tray = self.scene.slot_table_pos(tray_color)
        tray_err = math.dist((det_slot['x'], det_slot['y']), (true_tray['x'], true_tray['y']))
        total = pick_err + tray_err
        ring, bold = offset_to_ring(total)
        ok = total <= C.PLACE_TOLERANCE_MM
        self.io.log(f"  [评分] 放置偏移 ≈{total:.2f}mm -> 落在第 {ring} 环{bold} -> {'达标' if ok else '超差'} (预算 {C.PLACE_TOLERANCE_MM}mm)")
        return total, ring, ok


def _fold90(deg):
    """正方形 90° 旋转对称, 把角度差折叠到 [-45,45) 再比较。"""
    return ((deg + 45) % 90) - 45
