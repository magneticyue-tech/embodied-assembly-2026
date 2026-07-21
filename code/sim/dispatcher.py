"""
dispatcher.py — 后端调度状态机 (backend dispatch state machine)

职责 (对应 schemes/后端调度模块.txt 与 schemes/数据字典.txt 4.1):
  消费语音识别产出的 VoiceEvent (WAKE/START/RESET/RETRY), 驱动任务卡识别、
  任务一 / 任务二流程、错误三级处置 (模块级重试 / 调度级恢复 / 整任务重抽),
  向语音播报模块下发预制话术 (SpeechRequest 的 preset_id)。

对齐口径:
  本文件按数据字典的规格骨架编写 —— Pose 用手系/眼系 (m + rad)、VoiceEvent /
  Error / Result / CardType / PresetId 等。这与 code/sim 下 mm+deg+uv 的仿真接口
  (interfaces.py) 是两套类型, 桥接方式见 schemes/状态机待补清单.txt。
  各模块以 Protocol 注入; 文件内含桩实现, 可单独跑通状态流转, 真实模块接入后替换。

编写状态: 骨架。凡数据字典/需求表未定义处均以 TODO(待补) 标出, 汇总在
  schemes/状态机待补清单.txt, 待全队核对后回填, 不在此静默定死契约。
"""
# <!--D-->
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Protocol


# ============================================================
# 一、数据字典类型 (对齐 数据字典.txt 0.3/0.4/1.1/4.1/4.2)
# ============================================================

class Command(str, Enum):
    """语音识别事件命令 (数据字典 4.1)。"""
    WAKE = "WAKE"
    START = "START"
    RESET = "RESET"
    RETRY = "RETRY"


class ErrorCode(int, Enum):
    """错误码枚举 (数据字典 0.4)。"""
    COORD_INVALID = 1001        # 坐标值异常
    IK_UNREACHABLE = 1002       # 逆解无解/超限
    GRASP_FAILED = 1003         # 抓取/吸附失败
    VISION_UNRECOGNIZED = 2001  # 视觉无法识别
    LLM_FORMAT_ERROR = 3001     # 大模型无法识别/格式错误
    SPEECH_FAILED = 4001        # 合成/播放失败
    VOICE_TIMEOUT = 5001        # 唤醒/指令超时


class PresetId(str, Enum):
    """预制语音枚举 (数据字典 4.2)。"""
    READY = "READY"          # "我已就绪，请下达指令"
    TASK_DONE = "TASK_DONE"  # "任务已完成"
    ALL_DONE = "ALL_DONE"    # "两个任务均已完成"
    REDRAW = "REDRAW"  # "无法完成任务，重新抽取任务卡"
    WAIT_COMMAND = "WAIT_COMMAND"  # "指令执行完成，请确认下一条指令"


class CardTask(str, Enum):
    """任务卡分类结果 (数据字典 3.1)。"""
    TASK1 = "TASK1"
    TASK2 = "TASK2"


@dataclass
class Pose:
    """位姿 (数据字典 1.1): 手系/眼系三维位姿, 位置 m, 旋转 rad, 俯视仅用 rz。"""
    frame: str  # "hand" | "eye"
    x: float
    y: float
    z: float
    rz: float


@dataclass
class Error:
    """错误 (数据字典 0.4)。"""
    code: int
    message: str


@dataclass
class Result:
    """统一返回信封 (数据字典 0.3): 跨模块调用一律返回本类型。"""
    ok: bool
    data: Any = None
    error: Optional[Error] = None

    @staticmethod
    def good(data: Any = None) -> "Result":
        return Result(ok=True, data=data, error=None)

    @staticmethod
    def bad(code: int, message: str) -> "Result":
        return Result(ok=False, data=None, error=Error(code, message))


@dataclass
class VoiceEvent:
    """语音识别事件 (数据字典 4.1)。"""
    command: Command
    timestamp: str


# ============================================================
# 二、模块接口 (函数名对齐各 schemes/*.txt 的「函数」列)
# ============================================================

class VisionModule(Protocol):
    """视觉模块 (schemes/视觉模块需求梳理.txt)。各方法返回 Result。"""
    def capture(self) -> Result: ...                 # data: Image
    def detect_card(self, image: Any) -> Result: ...  # data: CardDetection
    def detect_blocks(self, image: Any) -> Result: ...  # data: list[BlockDetection]
    def detect_tray(self, image: Any) -> Result: ...   # data: TrayDetection
    def check_assembly(self, image: Any) -> Result: ...  # data: AssemblyCheck


class CognitionModule(Protocol):
    """大模型调用模块 (schemes/大模型调用模块.txt)。"""
    def classify_card(self, image: Any) -> Result: ...      # data: CardTask
    def parse_card_task1(self, image: Any) -> Result: ...   # data: Task1Card
    def parse_card_task2(self, image: Any) -> Result: ...   # data: Task2Card


class RobotModule(Protocol):
    """机械臂调用模块 (schemes/机械臂调用模块.txt)。位姿为手系 Pose。"""
    def move_to_view(self, target: Pose) -> Result: ...
    def pick(self, target: Pose) -> Result: ...
    def place(self, target: Pose) -> Result: ...
    def reset(self) -> Result: ...
    # TODO(待补): 机械臂表无"读取当前位姿"接口, 但视野解算需要当前眼位姿。
    #   见 状态机待补清单 #8。此处临时约定一个 current_pose()。
    def current_pose(self) -> Result: ...  # data: Pose(frame=hand)


class SpeechModule(Protocol):
    """语音播报模块 (schemes/语音播报模块需求梳理.txt)。"""
    def play_preset(self, preset: PresetId) -> Result: ...
    def synthesize(self, text: str) -> Result: ...


class GeometryModule(Protocol):
    """后端自身坐标/视野解算 (schemes/后端调度模块.txt)。"""
    def hand_to_eye(self, pose: Pose) -> Result: ...
    def eye_to_hand(self, pose: Pose) -> Result: ...
    def compute_card_view(self, detection: Any, eye: Pose) -> Result: ...   # data: Pose(frame=eye)
    def compute_block_view(self, detection: Any, eye: Pose) -> Result: ...  # data: Pose(frame=eye)
    def compute_tray_view(self, detection: Any, eye: Pose) -> Result: ...   # data: Pose(frame=eye)
    # 残缺行 (后端调度模块.txt 末行 "物块抓取 | 物块中心坐标/" 原文截断):
    #   本状态机需要"由物块检测 + 当前眼位姿 -> 手系抓取位姿"。见 状态机待补清单 #2。
    def plan_block_pick(self, detection: Any, eye: Pose) -> Result: ...      # data: Pose(frame=hand)
    # TODO(待补): 后端表未定义"放置位姿规划", 但放置需要手系目标位姿。见 状态机待补清单 #3。
    def plan_slot_place(self, tray: Any, slot_color: CardTask, eye: Pose) -> Result: ...  # data: Pose(frame=hand)


# ============================================================
# 三、状态与错误处置 (数据字典 0.4 三级处置)
# ============================================================

class State(Enum):
    IDLE = "idle"                # 待唤醒
    LISTENING = "listening"      # 已唤醒, 等 START/RESET/RETRY
    CARD_ID = "card_id"          # 任务卡识别中
    TASK1 = "task1"              # 任务一: 场景识别 + 播报
    TASK2 = "task2"              # 任务二: 解析 + 装配执行
    TASK_DONE = "task_done"      # 单个任务完成
    ALL_DONE = "all_done"        # 两个任务均完成 (终态)
    REDRAW = "redraw"            # 整任务重抽 (需人工, 等 RETRY)
    HALT = "halt"                # 停止 (终态)


class Disposition(Enum):
    """失败处置分级 (数据字典 0.4)。"""
    MODULE_RETRY = "module_retry"          # 同一步原地重试
    DISPATCH_RECOVER = "dispatch_recover"  # 调度自主调整策略后重试 (如抬高相机重拍/换姿态)
    TASK_REDRAW = "task_redraw"            # 需人工干预 -> 重抽任务卡


# TODO(待补 / 数据字典 0.4 决策点): 各 code 的自动重试上限与升级策略尚未定。
#   下列为占位默认值, 需与全队核对。见 状态机待补清单 #1。
MODULE_RETRY_LIMIT = 2       # 模块级原地重试次数
DISPATCH_RECOVER_LIMIT = 2   # 调度级恢复次数


# TODO(待标定 / 见 状态机待补清单 #10): 扫描(默认)姿态。
#   机械臂启动后的默认位姿, 调试时标定; 该姿态下相机视野覆盖整个工作台。
#   每次粗定位前恢复此姿态, 使 detect_card / detect_blocks / detect_tray
#   在全台视野下进行, 避免上一步 (如 pick) 残留姿态挡住待测目标。
#   下列数值为占位, 需现场标定后填入 (手系 Pose, m + rad)。
SCAN_POSE = Pose(frame="hand", x=0.0, y=0.0, z=0.5, rz=0.0)


def classify_disposition(code: int, module_tries: int, recover_tries: int) -> Disposition:
    """
    按错误码 + 已重试次数决定当前应走的处置级别 (数据字典 0.4)。
    同一 code 随重试次数升级: 模块级 -> 调度级 -> 整任务重抽。
    TODO(待补): 分级与阈值为占位实现, 需核对。见 状态机待补清单 #1。
    """
    if code == ErrorCode.VISION_UNRECOGNIZED:
        if module_tries < MODULE_RETRY_LIMIT:
            return Disposition.MODULE_RETRY
        if recover_tries < DISPATCH_RECOVER_LIMIT:
            return Disposition.DISPATCH_RECOVER   # 视野未捕捉到 -> 抬高相机重拍
        return Disposition.TASK_REDRAW
    if code == ErrorCode.LLM_FORMAT_ERROR:
        return Disposition.MODULE_RETRY if module_tries < MODULE_RETRY_LIMIT else Disposition.TASK_REDRAW
    if code == ErrorCode.SPEECH_FAILED:
        return Disposition.MODULE_RETRY if module_tries < MODULE_RETRY_LIMIT else Disposition.TASK_REDRAW
    if code == ErrorCode.IK_UNREACHABLE:
        return Disposition.DISPATCH_RECOVER if recover_tries < DISPATCH_RECOVER_LIMIT else Disposition.TASK_REDRAW
    if code == ErrorCode.GRASP_FAILED:
        return Disposition.MODULE_RETRY if module_tries < MODULE_RETRY_LIMIT else Disposition.TASK_REDRAW
    # 1001 坐标值异常 / 5001 超时 / 其它: 默认转整任务重抽
    return Disposition.TASK_REDRAW


class RedrawRequired(Exception):
    """需整任务重抽 (人工干预) 才能继续。"""
    def __init__(self, error: Error):
        super().__init__(f"整任务重抽: [{error.code}] {error.message}")
        self.error = error


# ============================================================
# 四、调度状态机
# ============================================================

class Dispatcher:
    """
    后端调度状态机。外部语音事件驱动顶层状态; 进入执行态后同步跑模块流水线,
    落到 TASK_DONE / ALL_DONE / REDRAW。

    坐标口径: 视野解算产出眼系目标位姿, 经 eye_to_hand 转手系后交机械臂执行。
    TODO(待补): 眼系->手系换算在流水线中的落点、与仿真 mm/deg 接口的桥接见清单 #4。
    """

    def __init__(self, vision: VisionModule, cognition: CognitionModule,
                 robot: RobotModule, speech: SpeechModule, geom: GeometryModule, io):
        self.vision = vision
        self.cognition = cognition
        self.robot = robot
        self.speech = speech
        self.geom = geom
        self.io = io
        self.state = State.IDLE
        self.tasks_done: set[CardTask] = set()

    # ---- 外部事件入口 ----

    def on_voice_event(self, ev: VoiceEvent) -> State:
        """消费一个语音事件, 返回处理后的状态。"""
        self.io.log(f"[调度] 状态={self.state.value} 收到事件={ev.command.value}")

        if ev.command == Command.RESET:
            return self._handle_reset()

        if self.state == State.IDLE and ev.command == Command.WAKE:
            self.speech.play_preset(PresetId.READY)
            self.state = State.LISTENING
            return self.state

        if self.state == State.LISTENING and ev.command == Command.START:
            return self._run_one_card_cycle()

        if self.state == State.REDRAW and ev.command == Command.RETRY:
            # 人工已重抽任务卡, 重新识别
            self.state = State.LISTENING
            return self._run_one_card_cycle()

        self.io.log(f"[调度] 事件 {ev.command.value} 在状态 {self.state.value} 下无转移, 忽略")
        return self.state

    def _handle_reset(self) -> State:
        """复位: 命机械臂回零, 回到待命。
        TODO(待补): 执行中途 RESET 是否中止当前任务、是否触发重抽, 未定。见清单 #6。"""
        self.robot.reset()
        self.state = State.LISTENING if self.tasks_done or self.state != State.IDLE else State.IDLE
        return self.state

    # ---- 顶层流程 ----

    def _run_one_card_cycle(self) -> State:
        """识别一张任务卡并执行对应任务; 完成后判是否两任务均完成。"""
        try:
            self.state = State.CARD_ID
            card_type = self._recognize_card()

            if card_type == CardTask.TASK1:
                self.state = State.TASK1
                self._run_task1()
            else:
                self.state = State.TASK2
                self._run_task2()

            self.tasks_done.add(card_type)
            self.speech.play_preset(PresetId.TASK_DONE)
            self.state = State.TASK_DONE

            if {CardTask.TASK1, CardTask.TASK2} <= self.tasks_done:
                self.speech.play_preset(PresetId.ALL_DONE)
                self.state = State.ALL_DONE
            else:
                # 第二张卡靠再次语音输入触发。
                self.speech.play_preset(PresetId.WAIT_COMMAND)
                self.state = State.LISTENING
            return self.state

        except RedrawRequired as exc:
            self.io.log(f"[调度] {exc}")
            self.speech.play_preset(PresetId.REDRAW)
            self.state = State.REDRAW
            return self.state

    # ---- 模块流水线 (各步对应 schemes 表函数) ----

    def _recognize_card(self) -> CardTask:
        """任务卡识别: 恢复扫描姿态 -> 粗定位卡 -> 算最小可行视野 -> 移动 -> 重拍 -> 大模型分类。"""
        self._go_scan_pose()                             # 俯瞰全台再粗定位
        image = self._attempt("拍照", self.vision.capture)
        card_det = self._attempt("定位任务卡", lambda: self.vision.detect_card(image),
                                 recover=self._recover_rescan)
        eye = self._current_eye_pose()
        view = self._attempt("任务卡视野", lambda: self.geom.compute_card_view(card_det, eye))
        self._attempt("调整视野", lambda: self.robot.move_to_view(self._to_hand(view)),
                      recover=self._recover_change_pose)
        image2 = self._attempt("拍照", self.vision.capture)
        return self._attempt("识别任务卡", lambda: self.cognition.classify_card(image2))

    def _run_task1(self) -> None:
        """任务一: 解读场景 -> TTS 播报描述 (数据字典 3.2)。"""
        image = self._attempt("拍照", self.vision.capture)
        card = self._attempt("解读任务一", lambda: self.cognition.parse_card_task1(image))
        self._attempt("场景描述播报", lambda: self.speech.synthesize(card["description"]))

    def _run_task2(self) -> None:
        """任务二: 解析装配指令 -> 按 seq 顺序执行每条 (数据字典 3.3)。"""
        image = self._attempt("拍照", self.vision.capture)
        card = self._attempt("解读任务二", lambda: self.cognition.parse_card_task2(image))
        for ins in sorted(card["instructions"], key=lambda i: i["seq"]):
            self._exec_instruction(ins)

    def _exec_instruction(self, ins: dict) -> None:
        """执行一条装配指令: 某色物块 -> 某色托盘槽。"""
        bc, tc = ins["block_color"], ins["target_slot_color"]
        self.io.log(f"  -- 第{ins['seq']}步: {bc}块 -> {tc}槽 --")

        # 1. 恢复扫描姿态 -> 粗定位物块 -> 算视野 -> 移近 -> 精定位 -> 规划抓取位姿 -> 抓取
        self._go_scan_pose()                             # 俯瞰全台再粗定位物块
        image = self._attempt("拍照", self.vision.capture)
        blocks = self._attempt("定位物块", lambda: self.vision.detect_blocks(image),
                               recover=self._recover_rescan)
        det = self._select_block(blocks, bc)
        view = self._attempt("物块抓取视野", lambda: self.geom.compute_block_view(det, self._current_eye_pose()))
        self._attempt("调整视野", lambda: self.robot.move_to_view(self._to_hand(view)),
                      recover=self._recover_change_pose)
        image = self._attempt("拍照", self.vision.capture)
        blocks = self._attempt("定位物块", lambda: self.vision.detect_blocks(image),
                               recover=self._recover_rescan)
        det = self._select_block(blocks, bc)
        grasp = self._attempt("规划抓取位姿", lambda: self.geom.plan_block_pick(det, self._current_eye_pose()))
        self._attempt("抓取物块", lambda: self.robot.pick(grasp), recover=self._recover_change_pose)

        # 2. 放置 + 装配检查: 未精确时重放一次, 仍未精确则接受并记录。
        self._place_and_check(tc)

    def _place_once(self, tc: str) -> None:
        """恢复扫描姿态 -> 粗定位托盘 -> 算装配视野 -> 移近 -> 规划放置位姿 -> 放置。
        抓取后机械臂停在物块附近, 需先回扫描姿态使相机俯瞰托盘 (见 SCAN_POSE)。"""
        self._go_scan_pose()
        image = self._attempt("拍照", self.vision.capture)
        tray = self._attempt("定位托盘", lambda: self.vision.detect_tray(image),
                             recover=self._recover_rescan)
        tview = self._attempt("托盘装配视野", lambda: self.geom.compute_tray_view(tray, self._current_eye_pose()))
        self._attempt("调整视野", lambda: self.robot.move_to_view(self._to_hand(tview)),
                      recover=self._recover_change_pose)
        place = self._attempt("规划放置位姿", lambda: self.geom.plan_slot_place(tray, tc, self._current_eye_pose()))
        self._attempt("放置物块", lambda: self.robot.place(place), recover=self._recover_change_pose)

    def _place_and_check(self, tc: str) -> None:
        """放置并做装配检查; 未精确时重放一次后接受 (数据字典 2.4, 见清单 #7)。
        TODO(待确认): occlusion 阈值 (precise 判定) 与"重放一次"次数上限待全队核查。"""
        self._place_once(tc)
        image = self._attempt("拍照", self.vision.capture)
        check = self._attempt("装配检查", lambda: self.vision.check_assembly(image))
        if check.get("precise", False):
            return
        # 未精确: 重放一次后接受
        self.io.log(f"  [装配检查] 未精确 occlusion={check.get('occlusion_ratio')}, 重放一次")
        self._place_once(tc)
        image = self._attempt("拍照", self.vision.capture)
        check = self._attempt("装配检查", lambda: self.vision.check_assembly(image))
        if not check.get("precise", False):
            self.io.log(f"  [装配检查] 重放后仍未精确 occlusion={check.get('occlusion_ratio')}, 接受当前结果")

    # ---- 重试内核 (数据字典 0.4) ----

    def _attempt(self, label: str, action: Callable[[], Result],
                 recover: Optional[Callable[[], None]] = None) -> Any:
        """
        执行一次模块调用, 按处置分级重试; 成功返回 Result.data, 耗尽升级重试则抛 RedrawRequired。
        action/recover 均返回/无返回, action 返回 Result。
        """
        module_tries = 0
        recover_tries = 0
        while True:
            res = action()
            if res.ok:
                return res.data
            code = res.error.code
            disp = classify_disposition(code, module_tries, recover_tries)
            self.io.log(f"  [{label}] 失败 code={code} ({res.error.message}) -> {disp.value}")
            if disp == Disposition.MODULE_RETRY:
                module_tries += 1
                continue
            if disp == Disposition.DISPATCH_RECOVER:
                recover_tries += 1
                if recover:
                    recover()
                continue
            raise RedrawRequired(res.error)

    # ---- 调度级恢复动作 (占位) ----

    def _recover_rescan(self) -> None:
        """调度级恢复: 视觉未识别时, 回扫描姿态重拍 (数据字典 0.4 示例)。
        扫描姿态即俯瞰全台的最优视野, 无需单独抬高相机, 回到该姿态重新取景即可。"""
        self.io.log("  [恢复] 回扫描姿态, 重新取景")
        self._go_scan_pose()

    def _recover_change_pose(self) -> None:
        """调度级恢复: 换一个可达姿态重试 (逆解超限时)。"""
        self.io.log("  [恢复] 更换机械臂姿态重试")
        # TODO(待补): 备选姿态如何生成未定。

    # ---- 辅助 ----

    def _go_scan_pose(self) -> None:
        """恢复扫描(默认)姿态: 相机俯瞰全台, 供粗定位。见 SCAN_POSE 说明与清单 #10。
        逆解超限时走调度级恢复 (换姿态重试)。"""
        self._attempt("恢复扫描姿态", lambda: self.robot.move_to_view(SCAN_POSE),
                      recover=self._recover_change_pose)

    def _current_eye_pose(self) -> Pose:
        """当前眼系位姿 = 当前手系位姿经手眼标定换算。
        TODO(待补): 依赖机械臂 current_pose() (表中缺此接口) + hand_to_eye。见清单 #8。"""
        hand = self.robot.current_pose()
        if not hand.ok:
            raise RedrawRequired(hand.error)
        eye = self.geom.hand_to_eye(hand.data)
        if not eye.ok:
            raise RedrawRequired(eye.error)
        return eye.data

    def _to_hand(self, eye_pose: Pose) -> Pose:
        """眼系目标位姿 -> 手系, 供机械臂执行。"""
        res = self.geom.eye_to_hand(eye_pose)
        if not res.ok:
            raise RedrawRequired(res.error)
        return res.data

    def _select_block(self, blocks: list, color: str):
        """从物块列表选出目标颜色; 缺失视为视觉未识别 (2001)。"""
        for b in blocks:
            if b.get("color") == color:
                return b
        raise RedrawRequired(Error(ErrorCode.VISION_UNRECOGNIZED, f"未在视野内找到{color}块"))


# ============================================================
# 五、桩实现 + 演示 (真实模块接入后替换)
# ============================================================

class _StubIO:
    def __init__(self):
        self._n = 0

    def now(self) -> str:
        self._n += 1
        return f"2026-07-16 10:00:{self._n:02d}.000"

    def log(self, msg: str) -> None:
        print(f"[{self.now()}] {msg}")


class _StubVision:
    def capture(self): return Result.good(object())
    def detect_card(self, image): return Result.good({"center": {"u": 450, "v": 300, "rotation": 0.0, "type": "oblong"}})
    def detect_blocks(self, image):
        return Result.good([{"color": c, "center": {"u": 100, "v": 100, "rotation": 0.0, "type": "square"}, "size": 45.0}
                            for c in ("red", "green", "blue")])
    def detect_tray(self, image): return Result.good({"center": {"u": 600, "v": 300, "rotation": 0.0}, "slots": []})
    def check_assembly(self, image): return Result.good({"precise": True, "occlusion_ratio": 0.95})


class _StubCognition:
    def __init__(self):
        self._seq = [CardTask.TASK2, CardTask.TASK1]  # 先任务二后任务一
        self._i = 0

    def classify_card(self, image):
        card = self._seq[min(self._i, len(self._seq) - 1)]
        self._i += 1
        return Result.good(card)

    def parse_card_task1(self, image):
        return Result.good({"items": ["杯子", "书本"], "description": "桌面有一个杯子和一本书"})

    def parse_card_task2(self, image):
        return Result.good({"instructions": [
            {"seq": 0, "block_color": "red", "target_slot_color": "red"},
            {"seq": 1, "block_color": "green", "target_slot_color": "green"},
        ]})


class _StubRobot:
    def move_to_view(self, target): return Result.good()
    def pick(self, target): return Result.good()
    def place(self, target): return Result.good()
    def reset(self): return Result.good()
    def current_pose(self): return Result.good(Pose("hand", 0.0, 0.0, 0.4, 0.0))


class _StubSpeech:
    def play_preset(self, preset): print(f"          [播报/预制] {preset.value}"); return Result.good()
    def synthesize(self, text): print(f"          [播报/TTS] {text}"); return Result.good()


class _StubGeometry:
    def hand_to_eye(self, pose): return Result.good(Pose("eye", pose.x, pose.y, pose.z, pose.rz))
    def eye_to_hand(self, pose): return Result.good(Pose("hand", pose.x, pose.y, pose.z, pose.rz))
    def compute_card_view(self, detection, eye): return Result.good(Pose("eye", 0.0, 0.0, 0.3, 0.0))
    def compute_block_view(self, detection, eye): return Result.good(Pose("eye", 0.05, 0.05, 0.25, 0.0))
    def compute_tray_view(self, detection, eye): return Result.good(Pose("eye", 0.1, 0.0, 0.3, 0.0))
    def plan_block_pick(self, detection, eye): return Result.good(Pose("hand", 0.05, 0.05, 0.02, 0.0))
    def plan_slot_place(self, tray, slot_color, eye): return Result.good(Pose("hand", 0.1, 0.0, 0.02, 0.0))


def _demo() -> None:
    io = _StubIO()
    d = Dispatcher(_StubVision(), _StubCognition(), _StubRobot(), _StubSpeech(),
                   _StubGeometry(), io)
    # 演示: 唤醒 -> 启动(任务二) -> 再启动(任务一) -> 两任务完成
    for cmd in (Command.WAKE, Command.START, Command.START):
        d.on_voice_event(VoiceEvent(cmd, io.now()))
    print(f"\n最终状态: {d.state.value}; 已完成: {sorted(t.value for t in d.tasks_done)}")


if __name__ == "__main__":
    _demo()
