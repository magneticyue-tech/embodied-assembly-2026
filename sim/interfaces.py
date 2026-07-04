"""
interfaces.py — 四层架构的抽象接口契约 (系统的"骨架图")

本文件是整套系统的【单一契约来源】: 每一层(感知/认知/执行/交互)对外暴露什么、
输入输出是什么形状, 全部在此定义。各模块只需"实现"这些 Protocol, main.py 只依赖
这些抽象, 不依赖具体实现 —— 这样仿真桩与真实实现(Claude VLM、AUBO-i5 SDK、
工业相机、离线语音)可以【无缝互换】, 换实现不改主流程。

设计原则:
- Protocol (结构化子类型): 类只要"长得对"就算实现了接口, 无需显式继承。
  用 @runtime_checkable 允许 isinstance() 运行时校验。
- TypedDict: 描述模块间传递的数据形状 (与现有代码返回的 dict 完全一致, 零运行期开销)。
- 坐标契约: 所有位姿统一为台面 mm + 旋转角(度) + 像素 uv(仅可视化用), 见 config.py。

关键边界 (真机可插拔的命门):
  RobotController 只负责【运动】(抓/放), **不接触任何 ground-truth**。
  放置精度的评分是【仿真专属】职责, 交给 config 侧的 RingEvaluator(非本契约的一部分),
  由 scene 真值喂入。真机换上 AUBORobot 后, 评分改由同心环实测读出, 主流程不变。
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


# 语义别名 — 形状相同, 命名区分用途, 便于阅读
BoardPose = Pose            # 托盘板位姿 (靠外轮廓测得, 遮挡鲁棒)
BlockPose = Pose            # 自由方块位姿
SlotPose = Pose             # 某色槽当前位姿 = 板位姿 ⊕ 标定布局

# 颜色 -> 该色槽在【板局部坐标系】下的中心(mm)。开局标定一次, 之后固定。
SlotLocal = dict[Color, tuple[float, float]]


class AssemblyStep(TypedDict):
    """装配序列中的一步: 把某色方块放到某色托盘。"""
    step: int
    block_color: Color
    tray_color: Color


class AssemblyPlan(TypedDict):
    """任务二: VLM 解析装配指令的结构化输出。"""
    task: str               # "assembly"
    timestamp: str          # ISO 时间戳 (赛题强制: 解析过程带时间戳落盘)
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
    仿真实现: OpenCVVision (真 OpenCV 管线)。真机同一接口, 换标定后的 H。
    """

    def detect_board_pose(self, img: Image) -> Optional[BoardPose]:
        """靠板【外轮廓大矩形】求板位姿; 永不被小方块遮挡。定位失败返回 None。"""
        ...

    def detect_blocks(
        self, img: Image, board: Optional[BoardPose] = None
    ) -> dict[Color, BlockPose]:
        """定位待装配区自由方块 (旋转鲁棒)。给 board 则排除落在板上的彩色块。"""
        ...

    def calibrate_slots(self, img: Image, board: BoardPose) -> SlotLocal:
        """开局(无遮挡)一次性标定: 颜色 -> 板局部坐标。之后不再重识别颜色。"""
        ...

    def slot_table_pos(
        self, color: Color, board: BoardPose, slot_local: SlotLocal
    ) -> SlotPose:
        """runtime: 某色槽当前台面位姿 = 板位姿 ⊕ 开局标定布局 (槽色被盖也不怕)。"""
        ...


# ============================================================
# 三、认知层 · 大模型智能体接口
# ============================================================

@runtime_checkable
class CognitionModule(Protocol):
    """
    语义解析: 只做"理解", 只输出结构化 JSON, **不输出坐标**(坐标是视觉的职责)。
    仿真实现: RuleBasedCognition (规则桩)。真机: ClaudeVLMCognition (多模态读卡)。
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
        """置信度校验 (赛题强制): 不达标 -> (False, 失败话术) 触发语音提示。"""
        ...


# ============================================================
# 四、执行层 · 机器人控制接口 (真机可插拔的关键)
# ============================================================

@runtime_checkable
class RobotController(Protocol):
    """
    只负责【运动】: 按视觉给的台面坐标+角度抓取/放置。**绝不接触 ground-truth**。
    仿真实现: SimRobot (记录动作, 不做物理)。真机: AUBORobot (AUBO SDK, MoveJ/MoveL)。

    注意: 放置精度评分【不在本接口内】—— 那是仿真专属, 由 RingEvaluator 用 scene
    真值算出。真机上评分改由同心环精度尺实测读数, 主流程与本接口都不变。
    """

    def pick(self, color: Color, target: BlockPose) -> None:
        """移至目标上方 -> 下降 -> 吸盘抓取 -> 上抬。target 来自视觉, 非真值。"""
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
    取一帧图像。把"图像从哪来"与"怎么处理图像"解耦。
    仿真实现: SimCamera(scene) (正射渲染台面)。真机: IndustrialCamera (工业单目采集)。
    """

    def capture(self) -> Image:
        ...


# ============================================================
# 六、交互层 · 语音与日志接口
# ============================================================

@runtime_checkable
class InteractionModule(Protocol):
    """
    人机交互全通道: 唤醒(KWS)、播报(TTS)、识别(ASR)、文本兜底、带时间戳日志。
    仿真实现: ConsoleInteraction (控制台打印 + 落盘)。
    真机: 离线 KWS(如 Porcupine)+ TTS(如 Piper)+ ASR(如 FunASR)。
    """

    def wake(self) -> bool:
        """等待唤醒词「小具同学」; 唤醒返回 True。"""
        ...

    def speak(self, text: str) -> None:
        """TTS 播报固定/生成话术。"""
        ...

    def listen(self) -> str:
        """ASR 识别一句 (权重低: 装配指令来自读卡, 非口述)。"""
        ...

    def text_input(self) -> str:
        """文本输入兜底 (语音失败时用, 规则要求必备)。"""
        ...

    def log(self, msg: str) -> None:
        """带时间戳记录一行并落盘 (赛题强制: 解析过程存带时间戳文本)。"""
        ...
