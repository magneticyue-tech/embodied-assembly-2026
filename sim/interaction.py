"""
interaction.py — 交互层 · 控制台交互实现 (实现 interfaces.InteractionModule)

把原本散落在 main.py 的【时钟 / 带时间戳日志 / 语音播报 / 唤醒】逻辑集中到一个类:
ConsoleInteraction。仿真下用控制台打印 + 落盘代替真机的离线 KWS/TTS/ASR。

结构化改造原则:
- 算法/格式【逐字不变】—— 时间戳基准、tick 递增、日志行格式、TTS 话术前缀、
  落盘编码全部与 main.py 中的 now_iso / Log / speak 完全一致。
- 新增类 ConsoleInteraction 实现 interfaces.InteractionModule Protocol。
- 保留 module-level 函数与常量 (now_iso / speak / _T0 / _tick) 供向后兼容,
  类方法通过委托或复用同一逻辑调用它们。

真机换实现: 离线 KWS(如 Porcupine) + TTS(如 Piper) + ASR(如 FunASR), 主流程不变。
"""
try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime

# 类型注解可选; interfaces 不 import 任何 sim 模块, 无循环导入风险。
import interfaces  # noqa: F401


# ---- module-level 时钟 (向后兼容: 与 main.py 中的 now_iso 逐字一致) ----
_T0 = datetime.datetime(2026, 6, 17, 10, 0, 0)
_tick = [0]


def now_iso():
    _tick[0] += 1
    return (_T0 + datetime.timedelta(seconds=_tick[0])).isoformat()


def speak(log, text):
    log(f"  [语音TTS] 「{text}」")


class ConsoleInteraction:
    """
    控制台交互: 唤醒(KWS)、播报(TTS)、识别(ASR)桩、文本兜底桩、带时间戳日志 + 落盘。
    实现 interfaces.InteractionModule。
    """

    def __init__(self, log_path):
        self.path = log_path
        self.lines = []
        self._t0 = datetime.datetime(2026, 6, 17, 10, 0, 0)
        self._tick = 0

    def now(self):
        self._tick += 1
        return (self._t0 + datetime.timedelta(seconds=self._tick)).isoformat()

    def log(self, msg):
        line = f"[{self.now()}] {msg}"
        self.lines.append(line)
        print(line)

    def wake(self):
        self.log("[唤醒KWS] 检测到唤醒词「小具同学」")
        return True

    def speak(self, text):
        self.log(f"  [语音TTS] 「{text}」")

    def listen(self):
        return ""   # ASR 桩(装配指令来自读卡, 非口述)

    def text_input(self):
        return ""   # 文本兜底桩

    def flush(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines))
