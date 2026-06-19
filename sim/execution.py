"""
execution.py — 执行层 (机器人控制的仿真替身, 对应 AUBO-i5)

真实赛场: 坐标变换链 -> 运动规划 -> 吸盘抓放 (AUBO-i5, 重复定位 ±0.02mm)。
本仿真: 验证逻辑正确性 —— 给定视觉的台面坐标+角度, 计算抓放, 评估定位误差,
并以"同心环精度尺"的环数读出最终放置偏移 (对应托盘评分方式)。
不做物理动力学 (pybullet 在 py3.14 无法构建; 真机用 AUBO SDK / ARCS 仿真)。

关键: AUBO-i5 机械臂精度 ±0.02mm 远高于任务需求, 故误差几乎全部来自视觉定位。
"""
import math
import config as C


def offset_to_ring(offset_mm):
    """把放置偏移 (mm) 换算成落在第几环 (1mm/环, 5mm 加粗)。"""
    ring = int(round(offset_mm / C.RING_STEP_MM))
    bold = " (加粗环)" if ring % C.RING_BOLD_EVERY == 0 and ring > 0 else ""
    return ring, bold


class Robot:
    def __init__(self, logger):
        self.log = logger
        self.held = None

    def pick(self, color, det_block, true_block):
        """模拟吸盘抓取: 对准检测到的中心与旋转角。"""
        derr = math.dist((det_block["x"], det_block["y"]),
                         (true_block["x"], true_block["y"]))
        aerr = abs(_fold90(det_block["deg"] - true_block["deg"]))  # 正方形 90° 对称
        self.log(f"  [执行] AUBO-i5 移至拍照点上方 -> 对准 {color}块 "
                 f"中心({det_block['x']:.1f},{det_block['y']:.1f})mm 角度{det_block['deg']:+.1f}° -> 吸盘抓取")
        self.log(f"  [执行] 定位误差 {derr:.2f}mm, 角度误差 {aerr:.1f}° "
                 f"(机械臂自身 ±0.02mm, 误差主要来自视觉)")
        self.held = color
        return derr

    def place(self, block_color, tray_color, det_tray, true_tray, pick_err):
        """模拟放置, 并按同心环读出最终偏移。"""
        tray_err = math.dist((det_tray["x"], det_tray["y"]),
                             (true_tray["x"], true_tray["y"]))
        total = pick_err + tray_err          # 保守估计: 抓偏 + 托盘定位偏
        ring, bold = offset_to_ring(total)
        ok = total <= C.PLACE_TOLERANCE_MM
        self.log(f"  [执行] 搬运 {block_color}块 -> {tray_color}托盘中心"
                 f"({det_tray['x']:.1f},{det_tray['y']:.1f})mm -> 释放吸盘")
        self.log(f"  [评分] 放置偏移 ≈{total:.2f}mm -> 落在第 {ring} 环{bold} "
                 f"-> {'达标' if ok else '超差'} (预算 {C.PLACE_TOLERANCE_MM}mm)")
        self.held = None
        return total, ring, ok


def _fold90(deg):
    """正方形 90° 旋转对称, 把角度差折叠到 [-45,45) 再比较。"""
    return ((deg + 45) % 90) - 45
