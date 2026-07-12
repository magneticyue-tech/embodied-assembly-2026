"""
camera.py — 仿真相机

把 Scene (台面物理坐标 mm) 渲染成一张俯视 BGR 图像 (像素)。
真实赛场由工业单目相机采集; 本仿真用 OpenCV 按 PX_PER_MM 正射投影绘制。
绘制顺序 (体现遮挡): 托盘板 -> 板上同心环色槽 -> 已放置方块(覆盖槽色) -> 自由方块。
"""
import math
import numpy as np
import cv2
import config as C
from scene import board_to_table


def mm_to_px(x_mm, y_mm):
    return x_mm * C.PX_PER_MM, y_mm * C.PX_PER_MM


def _rot_box_pts(cx_mm, cy_mm, side_mm, deg):
    cu, cv = mm_to_px(cx_mm, cy_mm)
    half = side_mm * C.PX_PER_MM
    pts = cv2.boxPoints(((cu, cv), (half, half), deg))
    return np.round(pts).astype(np.int32)


def _draw_ring_slot(img, cx, cy, deg, color):
    """在 (cx,cy) 画一个同心环精度尺色槽 (随板位姿旋转)。"""
    n = int(C.RING_MAX_MM / C.RING_STEP_MM)
    for k in range(n, 0, -1):
        side = C.TRAY_CENTER_MM + 2 * k * C.RING_STEP_MM
        g = int(200 - 60 * (1 - k / n))
        thick = 2 if (k % C.RING_BOLD_EVERY == 0) else 1
        cv2.polylines(img, [_rot_box_pts(cx, cy, side, deg)], True, (g, g, g), thick, cv2.LINE_AA)
    cv2.fillConvexPoly(img, _rot_box_pts(cx, cy, C.TRAY_CENTER_MM, deg), C.COLOR_BGR[color])


def render(scene, noise=True):
    img = np.full((C.IMG_H, C.IMG_W, 3), 238, dtype=np.uint8)  # 浅灰台面

    # 1) 整块托盘板 (刚性矩形, 按板位姿旋转)
    bd = scene.board
    bw = C.TRAY_BOARD_W_MM * C.PX_PER_MM
    bh = C.TRAY_BOARD_H_MM * C.PX_PER_MM
    cu, cv = mm_to_px(bd["x"], bd["y"])
    rect = cv2.boxPoints(((cu, cv), (bw, bh), bd["deg"]))
    rect = np.round(rect).astype(np.int32)
    cv2.fillConvexPoly(img, rect, C.TRAY_BOARD_BGR)
    cv2.polylines(img, [rect], True, C.TRAY_BOARD_EDGE_BGR, 3, cv2.LINE_AA)

    # 2) 板上 6 个同心环色槽 (随板刚体变换)
    for color in C.COLORS:
        s = scene.slot_table_pos(color)
        _draw_ring_slot(img, s["x"], s["y"], s["deg"], color)

    # 3) 已放置方块 (盖在对应槽上, 遮挡槽的彩色中心)
    for color, b in scene.placed.items():
        pts = _rot_box_pts(b["x"], b["y"], C.BLOCK_MM, b["deg"])
        cv2.fillConvexPoly(img, pts, C.COLOR_BGR[color])
        cv2.polylines(img, [pts], True, (60, 60, 60), 1, cv2.LINE_AA)

    # 4) 待装配区自由方块 (旋转实心)
    for color, b in scene.blocks.items():
        if color in scene.picked:
            continue
        pts = _rot_box_pts(b["x"], b["y"], C.BLOCK_MM, b["deg"])
        cv2.fillConvexPoly(img, pts, C.COLOR_BGR[color])
        cv2.polylines(img, [pts], True, (60, 60, 60), 1, cv2.LINE_AA)

    if noise:
        grad = np.linspace(0.90, 1.07, C.IMG_W).reshape(1, -1, 1)
        img = np.clip(img.astype(np.float32) * grad, 0, 255).astype(np.uint8)
        nz = np.random.normal(0, 3.5, img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + nz, 0, 255).astype(np.uint8)
    return img


# ============================================================
# 接口适配 · 感知层相机采集 (interfaces.CameraSource)
# ============================================================

class SimCamera:
    """
    仿真相机: 实现 interfaces.CameraSource 协议。
    取一帧图像 = 对绑定的 Scene 做正射渲染 (委托 render())。
    真机实现为工业单目相机采集, 使用同一 capture() 接口。
    """

    def __init__(self, scene):
        self.scene = scene

    def capture(self):
        """取一帧 BGR 图像 (HxWx3, uint8)。委托模块级 render() 渲染当前 scene。"""
        return render(self.scene)
