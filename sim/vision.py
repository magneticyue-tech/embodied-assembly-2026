"""
vision.py — 视觉模块 (方案精度的根基)

实现赛题三大视觉功能: 任务卡识别(见 cognition.py)、方块识别、托盘识别。
本模块负责后两者, 并专门处理"整块刚性托盘板 + 遮挡"问题。

托盘视觉策略 (关键):
- 托盘是一整块刚性矩形板, 板上 6 色槽布局相对板固定。
- detect_board_pose(): 每步靠【板外轮廓矩形】求板位姿(中心+角度)。
  外轮廓是整块板的大矩形, 永远不会被放上去的小方块遮挡 -> 遮挡鲁棒。
- calibrate_slots(): 仅开局(无遮挡)执行一次, 标定"颜色 -> 板局部坐标"映射。
- runtime 取某色槽位置 = 板位姿 ⊕ 该色的板局部坐标 (slot_table_pos),
  不再靠重新识别彩色中心 -> 放置后颜色被方块盖住也不影响。

方块识别: BGR->HSV 分割 -> 形态学 -> 轮廓 -> minAreaRect(中心+角度) -> 单应反投影。
旋转鲁棒: minAreaRect 取朝向; 正方形 90° 对称折叠到 [-45,45)。
"""
import math
import numpy as np
import cv2
import config as C

# HSV 阈值表 (OpenCV: H 0-179)。真实赛场需现场光源下逐色标定。
HSV_RANGES = {
    "red":    [((0, 110, 70), (8, 255, 255)), ((170, 110, 70), (179, 255, 255))],
    "orange": [((9, 110, 70), (20, 255, 255))],
    "yellow": [((21, 110, 70), (34, 255, 255))],
    "green":  [((35, 60, 50), (85, 255, 255))],
    "blue":   [((90, 80, 50), (128, 255, 255))],
    "purple": [((129, 50, 50), (169, 255, 255))],
}


def _mask_for_color(hsv, color):
    mask = None
    for lo, hi in HSV_RANGES[color]:
        m = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        mask = m if mask is None else cv2.bitwise_or(mask, m)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    return mask


def px_to_table_mm(u, v):
    """单应反投影: 像素 -> 台面 mm。仿真为正射, 真实赛场用标定的 H。"""
    return (u / C.PX_PER_MM, v / C.PX_PER_MM)


def _fold90(deg):
    return ((deg + 45) % 90) - 45


# ---------- 托盘板位姿 (遮挡鲁棒: 只用外轮廓大矩形) ----------

def detect_board_pose(img):
    """从板的外轮廓矩形求板位姿。返回 dict(x,y,deg,uv,box) 或 None。
    板是台面上最大的矩形灰块, 不被小方块遮挡。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 板底色比台面略深, 用边缘+形态学找大矩形轮廓
    edges = cv2.Canny(gray, 30, 100)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    exp_area = (C.TRAY_BOARD_W_MM * C.PX_PER_MM) * (C.TRAY_BOARD_H_MM * C.PX_PER_MM)
    best = None
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < exp_area * 0.5:
            continue
        (cu, cv_), (w, h), ang = cv2.minAreaRect(cnt)
        if w < 1 or h < 1:
            continue
        # 校核长宽比与期望板一致 (容忍 ±25%)
        ar = max(w, h) / min(w, h)
        exp_ar = max(C.TRAY_BOARD_W_MM, C.TRAY_BOARD_H_MM) / min(C.TRAY_BOARD_W_MM, C.TRAY_BOARD_H_MM)
        if abs(ar - exp_ar) > exp_ar * 0.35:
            continue
        if best is None or area > best[0]:
            best = (area, cu, cv_, w, h, ang)
    if best is None:
        return None
    _, cu, cv_, w, h, ang = best
    # 解析朝向: 判断检测到的 w 轴对应板的 W 还是 H, 据此定 deg, 使绘制框与真实板对齐
    W_px = C.TRAY_BOARD_W_MM * C.PX_PER_MM
    H_px = C.TRAY_BOARD_H_MM * C.PX_PER_MM
    if abs(w - W_px) > abs(w - H_px):   # 检测 w 更接近板的 H -> 旋转了 90°
        ang += 90
    deg = ((ang + 90) % 180) - 90       # 板非正方形, 折叠到 [-90,90)
    x, y = px_to_table_mm(cu, cv_)
    return {"x": x, "y": y, "deg": deg, "uv": (int(cu), int(cv_))}


def _table_to_board_local(xy, board):
    """台面坐标 -> 板局部坐标 (board_to_table 的逆变换)。"""
    a = math.radians(board["deg"])
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = xy[0] - board["x"], xy[1] - board["y"]
    return (dx * ca + dy * sa, -dx * sa + dy * ca)


# ---------- 开局一次性标定: 颜色 -> 板局部坐标 ----------

def calibrate_slots(img, board):
    """开局(无遮挡)执行一次: 识别每个彩色槽中心, 换算成板局部坐标并存下。
    之后装配阶段不再重识别颜色。返回 {color: (lx,ly)}。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    exp_area = (C.TRAY_CENTER_MM * C.PX_PER_MM) ** 2
    slot_local = {}
    for color in C.COLORS:
        mask = _mask_for_color(hsv, color)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for cnt in cnts:
            area = cv2.contourArea(cnt)
            if area < exp_area * 0.4 or area > exp_area * 2.2:
                continue
            (cu, cv_), (w, h), _ = cv2.minAreaRect(cnt)
            if min(w, h) < 1 or not (0.7 < w / h < 1.4):
                continue
            if best is None or area > best[0]:
                best = (area, cu, cv_)
        if best is None:
            continue
        _, cu, cv_ = best
        xy = px_to_table_mm(cu, cv_)
        slot_local[color] = _table_to_board_local(xy, board)
    return slot_local


# ---------- 待装配区自由方块 (旋转鲁棒) ----------

def detect_blocks(img, board=None, exclude_board_margin_mm=5):
    """识别待装配区自由方块。返回 {color: dict(x,y,deg,uv)}。
    若给 board, 则排除落在板范围内的彩色块 (那是已放置/槽中心, 不该再抓)。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    exp_area = (C.BLOCK_MM * C.PX_PER_MM) ** 2
    result = {}
    for color in C.COLORS:
        mask = _mask_for_color(hsv, color)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for cnt in cnts:
            area = cv2.contourArea(cnt)
            if area < exp_area * 0.5 or area > exp_area * 1.8:
                continue
            (cu, cv_), (w, h), ang = cv2.minAreaRect(cnt)
            if min(w, h) < 1 or not (0.7 < w / h < 1.4):
                continue
            xmm, ymm = px_to_table_mm(cu, cv_)
            if board is not None and _inside_board((xmm, ymm), board, exclude_board_margin_mm):
                continue   # 落在托盘板上的彩色块不是待抓自由方块
            if best is None or area > best[0]:
                best = (area, cu, cv_, _fold90(ang))
        if best is None:
            continue
        _, cu, cv_, deg = best
        xmm, ymm = px_to_table_mm(cu, cv_)
        result[color] = {"x": xmm, "y": ymm, "deg": deg, "uv": (int(cu), int(cv_))}
    return result


def _inside_board(xy, board, margin_mm):
    lx, ly = _table_to_board_local(xy, board)
    return (abs(lx) <= C.TRAY_BOARD_W_MM / 2 + margin_mm and
            abs(ly) <= C.TRAY_BOARD_H_MM / 2 + margin_mm)


# ---------- runtime: 由板位姿+标定布局算某色槽当前位置 (不靠重识别颜色) ----------

def slot_table_pos(color, board, slot_local):
    """色槽当前台面坐标 = 板位姿 ⊕ 开局标定的板局部坐标。
    放置后颜色被遮挡、或板被挪动, 都不影响 (只要板位姿测得准)。"""
    lx, ly = slot_local[color]
    a = math.radians(board["deg"])
    ca, sa = math.cos(a), math.sin(a)
    x = board["x"] + lx * ca - ly * sa
    y = board["y"] + lx * sa + ly * ca
    u, v = x * C.PX_PER_MM, y * C.PX_PER_MM
    return {"x": x, "y": y, "deg": board["deg"], "uv": (int(u), int(v))}


# ============================================================
# Protocol 实现: 把上面的 module 级函数包成一个类
# ============================================================
# 说明: OpenCVVision 实现 interfaces.VisionModule。每个方法直接委托到本模块的
# 同名全局函数, 逻辑逐字不变。方法名与全局函数同名不会互相遮蔽 (方法体内的裸名
# detect_board_pose / detect_blocks / calibrate_slots / slot_table_pos 解析到
# module 全局作用域, 不是 self 属性, 故无递归)。类型注解可选, 仅供阅读。
import interfaces


class OpenCVVision:
    """真 OpenCV 单目视觉管线, 实现 interfaces.VisionModule。

    仅作结构化封装: 所有算法仍在本模块的 module 级函数中, 本类只做委托,
    以便 main.py 依赖抽象接口, 真机可无缝替换为标定后的实现。
    """

    def detect_board_pose(self, img: "interfaces.Image") -> "interfaces.Optional[interfaces.BoardPose]":
        return detect_board_pose(img)

    def detect_blocks(
        self, img: "interfaces.Image", board: "interfaces.Optional[interfaces.BoardPose]" = None
    ) -> "dict[interfaces.Color, interfaces.BlockPose]":
        return detect_blocks(img, board)

    def calibrate_slots(
        self, img: "interfaces.Image", board: "interfaces.BoardPose"
    ) -> "interfaces.SlotLocal":
        return calibrate_slots(img, board)

    def slot_table_pos(
        self, color: "interfaces.Color", board: "interfaces.BoardPose",
        slot_local: "interfaces.SlotLocal",
    ) -> "interfaces.SlotPose":
        return slot_table_pos(color, board, slot_local)
