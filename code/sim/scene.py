"""
scene.py — 仿真场景生成

模拟装配实训台俯视图:
- 6 个随机摆放(含随机旋转)的彩色方块, 散布在待装配区。
- 一整块刚性托盘板: 有自己的位姿(中心+旋转角), 板上 6 个色槽按固定布局排布,
  6 槽共享板的位姿 (随板一起平移/旋转)。
- 方块放上托盘后, 记录在 placed 中 -> 渲染时覆盖该槽彩色中心 (模拟遮挡)。

perturb() 模拟"机器人前往拍照点期间裁判再次挪动": 自由方块与托盘板均可能移动。
"""
import math
import random
import config as C


def _board_local_slots():
    """返回 6 个槽位在板局部坐标下的中心 (mm), 板中心为原点。
    仅给出 6 个固定锚点, 颜色分配在 _init_layout 中随机决定。"""
    pts = []
    x0 = -(C.TRAY_COLS - 1) * C.SLOT_PITCH_MM / 2
    y0 = -(C.TRAY_ROWS - 1) * C.SLOT_PITCH_MM / 2
    for i in range(C.TRAY_COLS * C.TRAY_ROWS):
        col, row = divmod(i, C.TRAY_ROWS)
        pts.append((x0 + col * C.SLOT_PITCH_MM, y0 + row * C.SLOT_PITCH_MM))
    return pts


def board_to_table(local_xy, board):
    """板局部坐标 -> 台面坐标, 按板位姿(中心+角度)做刚体变换。"""
    lx, ly = local_xy
    a = math.radians(board["deg"])
    ca, sa = math.cos(a), math.sin(a)
    return (board["x"] + lx * ca - ly * sa,
            board["y"] + lx * sa + ly * ca)


class Scene:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.blocks = {}     # color -> dict(x,y,deg)  自由方块
        self.board = {}      # dict(x,y,deg)  托盘板位姿
        self.slot_local = {} # color -> (lx,ly)  色槽在板局部坐标(开局固定不变)
        self.picked = set()  # 已从待装配区取走的方块
        self.placed = {}     # color -> dict(x,y,deg) 已放到托盘上的方块(用于遮挡渲染)
        self._init_layout()

    def _rand_pos(self, margin, region):
        x0, y0, x1, y1 = region
        return (self.rng.uniform(x0 + margin, x1 - margin),
                self.rng.uniform(y0 + margin, y1 - margin))

    def _init_layout(self):
        # 自由方块散布在台面左 48% 待装配区, 各自随机旋转
        region = (30, 30, C.TABLE_W_MM * 0.48, C.TABLE_H_MM - 30)
        placed = []
        for color in C.COLORS:
            for _ in range(300):
                p = self._rand_pos(C.BLOCK_MM, region)
                if all((p[0]-q[0])**2 + (p[1]-q[1])**2 > (C.BLOCK_MM*1.8)**2 for q in placed):
                    placed.append(p)
                    self.blocks[color] = {"x": p[0], "y": p[1],
                                          "deg": self.rng.uniform(-C.BLOCK_ROT_DEG, C.BLOCK_ROT_DEG)}
                    break
        # 托盘板: 位姿(中心+小角度旋转), 放在右侧装配区
        self.board = {
            "x": C.TABLE_W_MM * 0.74,
            "y": C.TABLE_H_MM * 0.5,
            "deg": self.rng.uniform(-10, 10),
        }
        # 6 色槽随机分配到 6 个板上锚点 (开局固定, 之后不变)
        anchors = _board_local_slots()
        order = list(C.COLORS)
        self.rng.shuffle(order)
        for color, local in zip(order, anchors):
            self.slot_local[color] = local

    def slot_table_pos(self, color):
        """某色槽当前台面坐标 = 板位姿 ⊕ 板局部锚点。板被挪动后按当前位姿计算。"""
        x, y = board_to_table(self.slot_local[color], self.board)
        return {"x": x, "y": y, "deg": self.board["deg"]}

    def perturb(self, max_shift_mm=12, max_rot_deg=10, board_shift_mm=8):
        """模拟裁判中途挪动: 未取走的自由方块 + 托盘板整体。"""
        for color, b in self.blocks.items():
            if color in self.picked:
                continue
            b["x"] = min(max(C.BLOCK_MM, b["x"] + self.rng.uniform(-max_shift_mm, max_shift_mm)),
                         C.TABLE_W_MM * 0.48)
            b["y"] = min(max(C.BLOCK_MM, b["y"] + self.rng.uniform(-max_shift_mm, max_shift_mm)),
                         C.TABLE_H_MM - 30)
            b["deg"] += self.rng.uniform(-max_rot_deg, max_rot_deg)
        # 托盘板整体小幅平移/转动 (位姿变, 板上布局不变)
        self.board["x"] += self.rng.uniform(-board_shift_mm, board_shift_mm)
        self.board["y"] += self.rng.uniform(-board_shift_mm, board_shift_mm)
        self.board["deg"] += self.rng.uniform(-3, 3)

    def place_block(self, color, x, y, deg):
        """方块放到托盘: 从待装配区移除, 记入 placed (渲染时覆盖槽色)。"""
        self.picked.add(color)
        self.placed[color] = {"x": x, "y": y, "deg": deg}
