"""
config.py — 全局配置与坐标系约定

坐标系说明(正向设计核心):
- 台面坐标系 (table frame): 单位毫米 mm, 原点在台面左上角, X 向右, Y 向下。
- 图像坐标系 (image frame): 单位像素 px, 原点在图像左上角, u 向右, v 向下。
- 二者通过单应矩阵 H 关联 (见 vision.py 的 back-projection)。

本仿真用"已知台面平面 + 已知方块尺寸"破解单目无深度问题:
方块/托盘都在同一台面平面 Z=0 上, 故像素->台面是一个 2D 单应变换。

硬件已确认 (来自赛方资料):
- 机械臂 AUBO-i5: 6 自由度, 负载 5kg, 工作半径 886.5mm, 重复定位精度 ±0.02mm。
  -> 机械臂精度远高于任务需求, 真正的精度瓶颈在视觉定位, 不在机器人。
- 托盘 = 一整块刚性矩形板, 板上固定排布 6 个同心环精度尺色槽 (2列x3行)。
  6 个色槽共享同一块板的位姿; 每环 1mm, 每 5mm 加粗, 最大量程 ±20mm。
  -> 放置误差可由方块中心落在第几环直接读出, "精密"可量化。
- 方块/托盘摆放可能旋转, 边与相机画面不平行 -> 检测需旋转鲁棒。

托盘视觉策略 (解决遮挡):
- 颜色->槽位映射: 开局无遮挡时一次性标定, 固定不变 (布局相对板子是定死的)。
- 板位姿: 每步重新检测, 因为中途可能被裁判挪动; 靠板的【外轮廓矩形】
  (整块板永远不被小方块遮挡), 不靠内部彩色中心 (会被放上的方块盖住)。
- 装配时: 重测板位姿 + 开局布局 -> 算出各色槽当前位置, 不靠重识别颜色。
"""

# 6 种颜色 (赛题固定: 红橙黄绿蓝紫)
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

# 像素/毫米 比例 (本仿真相机为正射俯视, 真实赛场需手眼+单应标定得到)
PX_PER_MM = IMG_W / TABLE_W_MM  # = 1.5 px/mm

# ---- 同心环精度尺色槽 (来自 troy.png) ----
TRAY_CENTER_MM = 30.0     # 中心彩色方块边长 (与方块同尺寸: 完美放置应正好覆盖)
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
