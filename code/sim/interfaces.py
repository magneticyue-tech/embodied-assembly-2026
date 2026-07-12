"""
interfaces.py — 四层架构的抽象接口契约

本文件定义每一层 (感知/认知/执行/交互) 对外暴露的方法与输入输出数据形状。
各模块实现这些 Protocol, main.py 只依赖这些抽象, 不依赖具体实现。
更换实现 (仿真桩 <-> 真机: VLM、AUBO-i5 SDK、工业相机、离线语音) 时主流程不变;
更换后的实际行为一致性需通过联调验证。

设计说明:
- Protocol (结构化子类型): 类具备同名同签名方法即视为实现该接口, 无需显式继承。
  @runtime_checkable 允许 isinstance() 运行时校验。
- TypedDict: 描述模块间传递的数据形状 (与现有代码返回的 dict 一致, 无运行期开销)。
- 坐标契约: 所有位姿统一为台面 mm + 旋转角(度) + 像素 uv(仅可视化用), 见 config.py。

职责边界:
  RobotController 只负责运动 (抓/放), 不接触仿真 ground-truth。
  放置精度评分是仿真专属职责, 由 RingEvaluator (不属于本契约) 用 scene 真值计算。
  真机上评分改由同心环精度尺实测读出, 主流程不变。
"""
from typing import Optional, Protocol, TypedDict, runtime_checkable
import numpy as np

# ---- 基础别名 ----
Color = str                 # config.COLORS 之一: red/orange/yellow/green/blue/purple
Image = np.ndarray          # BGR, HxWx3, uint8 (相机采集或仿真渲染的一帧)


# ============================================================
# 一、模块间传递的数据契约 (TypedDict)
# ============================================================

class Pose(TypedDict):
    """统一位姿: 台面物理坐标(mm) + 旋转角(度) + 像素坐标(可视化用)。"""
    x: float
    y: float
    deg: float
    uv: tuple[int, int]


# 语义别名 — 形状相同, 命名区分用途
BoardPose = Pose            # 托盘板位姿 (由外轮廓测得)
BlockPose = Pose            # 自由方块位姿
SlotPose = Pose             # 某色槽当前位姿 = 板位姿 ⊕ 标定布局

# 颜色 -> 该色槽在板局部坐标系下的中心(mm)。开局标定一次, 之后固定。
SlotLocal = dict[Color, tuple[float, float]]


class AssemblyStep(TypedDict):
    """装配序列中的一步: 把某色方块放到某色托盘。"""
    step: int
    block_color: Color
    tray_color: Color


class AssemblyPlan(TypedDict):
    """任务二: VLM 解析装配指令的结构化输出。"""
    task: str               # "assembly"
    timestamp: str          # ISO 时间戳 (赛题要求: 解析过程带时间戳落盘)
    confidence: float
    recognized: bool
    sequence: list[AssemblyStep]


class SceneResult(TypedDict):
    """任务一: VLM 场景识别的结构化输出。"""
    task: str               # "scene_recognition"
    timestamp: str
    confidence: float
    recognized: bool
    description: str


# ============================================================
# 二、感知层 · 视觉模块接口
# ============================================================

@runtime_checkable
class VisionModule(Protocol):
    """
    单目视觉: 从一帧图像定位托盘板、自由方块, 并把像素反投影到台面 mm。
    仿真实现: OpenCVVision。真机实现使用同一接口, 更换标定后的单应矩阵 H。
    """

    def detect_board_pose(self, img: Image) -> Optional[BoardPose]:
        """由板外轮廓矩形求板位姿 (外轮廓不被 30mm 方块遮挡)。定位失败返回 None。"""
        ...

    def detect_blocks(
        self, img: Image, board: Optional[BoardPose] = None
    ) -> dict[Color, BlockPose]:
        """定位待装配区自由方块 (含旋转)。给 board 则排除落在板上的彩色块。"""
        ...

    def calibrate_slots(self, img: Image, board: BoardPose) -> SlotLocal:
        """开局(无遮挡)一次性标定: 颜色 -> 板局部坐标。之后不再重识别颜色。"""
        ...

    def slot_table_pos(
        self, color: Color, board: BoardPose, slot_local: SlotLocal
    ) -> SlotPose:
        """运行时: 某色槽当前台面位姿 = 板位姿 ⊕ 开局标定布局。"""
        ...


# ============================================================
# 三、认知层 · 大模型智能体接口
# ============================================================

@runtime_checkable
class CognitionModule(Protocol):
    """
    语义解析: 只输出结构化 JSON, 不输出坐标 (坐标是视觉模块的职责)。
    仿真实现: RuleBasedCognition (规则桩)。真机实现: VLM 多模态读卡。
    """

    def parse_card1(self, scene_desc: str, now_iso: str) -> SceneResult:
        """任务一: 场景识别 -> 结构化描述 + 置信度 + 时间戳。"""
        ...

    def parse_card2(self, card: str, now_iso: str) -> AssemblyPlan:
        """任务二: 装配指令(文本/图) -> {方块色->托盘色, 顺序} + 置信度 + 时间戳。"""
        ...

    def check_confidence(
        self, parsed: SceneResult | AssemblyPlan, threshold: float = 0.6
    ) -> tuple[bool, Optional[str]]:
        """置信度校验 (赛题要求): 不达标 -> (False, 失败话术) 触发语音提示。"""
        ...


# ============================================================
# 四、执行层 · 机器人控制接口
# ============================================================

@runtime_checkable
class RobotController(Protocol):
    """
    只负责运动: 按视觉给出的台面坐标+角度执行抓取/放置。不接触仿真 ground-truth。
    仿真实现: SimRobot (记录动作, 不做物理)。真机实现: AUBO SDK (MoveJ/MoveL)。

    放置精度评分不在本接口内: 仿真中由 RingEvaluator 用 scene 真值计算;
    真机上由同心环精度尺实测读数。两种情形下主流程与本接口不变。
    """

    def pick(self, color: Color, target: BlockPose) -> None:
        """移至目标上方 -> 下降 -> 吸盘抓取 -> 上抬。target 来自视觉检测, 非真值。"""
        ...

    def place(self, block_color: Color, tray_color: Color, target: SlotPose) -> None:
        """移至托盘目标槽上方 -> 下降到放置高度 -> 释放吸盘 -> 上抬。"""
        ...


# ============================================================
# 五、感知层 · 相机采集接口
# ============================================================

@runtime_checkable
class CameraSource(Protocol):
    """
    取一帧图像。将"图像来源"与"图像处理"解耦。
    仿真实现: SimCamera(scene) (正射渲染台面)。真机实现: 工业单目相机采集。
    """

    def capture(self) -> Image:
        ...


# ============================================================
# 六、交互层 · 语音与日志接口
# ============================================================

@runtime_checkable
class InteractionModule(Protocol):
    """
    人机交互通道: 唤醒(KWS)、播报(TTS)、识别(ASR)、文本备用输入、带时间戳日志。
    仿真实现: ConsoleInteraction (控制台打印 + 落盘)。
    真机候选: 离线 KWS(如 Porcupine) + TTS(如 Piper) + ASR(如 FunASR), 未定型。
    """

    def wake(self) -> bool:
        """等待唤醒词「小具同学」; 唤醒返回 True。"""
        ...

    def speak(self, text: str) -> None:
        """TTS 播报固定/生成话术。"""
        ...

    def listen(self) -> str:
        """ASR 识别一句 (装配指令来自相机读卡, ASR 仅用于唤醒后交互)。"""
        ...

    def text_input(self) -> str:
        """文本输入 (语音失败时的备用方式, 赛题要求必备)。"""
        ...

    def log(self, msg: str) -> None:
        """带时间戳记录一行并落盘 (赛题要求: 解析过程存带时间戳文本)。"""
        ...
