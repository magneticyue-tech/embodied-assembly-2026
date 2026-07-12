"""
config.py — 全局配置与坐标系约定

坐标系约定:
- 台面坐标系 (table frame): 单位毫米 mm, 原点在台面左上角, X 向右, Y 向下。
- 图像坐标系 (image frame): 单位像素 px, 原点在图像左上角, u 向右, v 向下。
- 二者通过单应矩阵 H 关联 (见 vision.py 的反投影)。

单目深度处理方式: 方块/托盘均位于同一台面平面 Z=0 上,
像素坐标到台面坐标为 2D 单应变换, 结合已知方块尺寸约束检测。

硬件参数 (来源: 赛方资料):
- 机械臂 AUBO-i5: 6 自由度, 负载 5kg, 工作半径 886.5mm, 重复定位精度 ±0.02mm (厂商标称)。
- 托盘: 一整块刚性矩形板, 板上固定排布 6 个同心环精度尺色槽 (2列x3行),
  6 个色槽共享同一块板的位姿; 每环 1mm, 每 5mm 加粗, 最大量程 ±20mm。
  放置误差按方块中心落在第几环读出。
- 方块/托盘摆放可能旋转, 边不一定与相机画面平行。

托盘视觉策略:
- 颜色->槽位映射: 开局无遮挡时一次性标定, 之后固定 (布局相对板体固定)。
- 板位姿: 每步重新检测 (中途可能被裁判挪动); 检测依据为板的外轮廓矩形,
  不依据内部彩色中心 (内部中心会被放上的方块覆盖)。
- 装配时: 重测板位姿 + 开局标定布局 -> 计算各色槽当前位置, 不重新识别颜色。
"""

# 6 种颜色 (赛题给定: 红橙黄绿蓝紫)
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

# 颜色的 BGR 渲染值 (仅用于生成仿真图像; 真实场景由相机采集)
COLOR_BGR = {
    "red":    (40, 40, 220),
    "orange": (30, 130, 240),
    "yellow": (40, 220, 230),
    "green":  (60, 150, 60),
    "blue":   (220, 70, 40),
    "purple": (150, 40, 130),
}

# 台面物理尺寸 (mm)
TABLE_W_MM = 600.0
TABLE_H_MM = 400.0

# 方块物理尺寸 (mm) — 赛题给定 30mm 正方体
BLOCK_MM = 30.0

# 图像分辨率 (px)
IMG_W = 900
IMG_H = 600

# 像素/毫米 比例 (本仿真相机为正射俯视; 真实赛场由手眼+单应标定得到)
PX_PER_MM = IMG_W / TABLE_W_MM  # = 1.5 px/mm

# ---- 同心环精度尺色槽 (参数来源: troy.png) ----
TRAY_CENTER_MM = 30.0     # 中心彩色方块边长 (与方块同尺寸, 放置无偏移时正好覆盖)
RING_STEP_MM = 1.0        # 每环 1mm
RING_BOLD_EVERY = 5       # 每 5mm 加粗
RING_MAX_MM = 20.0        # 最大量程 ±20mm
SLOT_PITCH_MM = TRAY_CENTER_MM + 2 * RING_MAX_MM + 10  # 槽间距 = 80mm
TRAY_SLOT_MM = TRAY_CENTER_MM + 2 * RING_MAX_MM        # 单槽精度尺总尺寸 = 70mm

# ---- 整块托盘板 (6 槽 2列x3行 固定排布) ----
TRAY_COLS = 2
TRAY_ROWS = 3
TRAY_MARGIN_MM = 18.0     # 板边缘留白
TRAY_BOARD_W_MM = TRAY_COLS * SLOT_PITCH_MM + 2 * TRAY_MARGIN_MM - (SLOT_PITCH_MM - TRAY_SLOT_MM)
TRAY_BOARD_H_MM = TRAY_ROWS * SLOT_PITCH_MM + 2 * TRAY_MARGIN_MM - (SLOT_PITCH_MM - TRAY_SLOT_MM)
TRAY_BOARD_BGR = (205, 205, 205)   # 板底色 (浅灰)
TRAY_BOARD_EDGE_BGR = (120, 120, 120)

# 方块随机旋转范围 (度) — 模拟摆放不与画面对齐
BLOCK_ROT_DEG = 35.0

# 抓取/放置精度预算 (mm) — 用于评估定位误差是否可接受
PLACE_TOLERANCE_MM = 5.0

OUTPUT_DIR = "output"
