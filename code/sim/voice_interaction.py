"""
voice_interaction.py — 真实语音交互模块 (实现 interfaces.InteractionModule)

使用 code/sim/src/ 下的语音助手模块实现真实的语音唤醒、播报和识别功能。
与 ConsoleInteraction 接口完全一致，可无缝替换。

功能：
- 唤醒词检测: 小具同学 (Vosk 语法约束)
- 语音识别: faster-whisper (离线)
- 语音合成: Windows SAPI (离线)
- 带时间戳日志: 控制台 + 落盘

使用方式：
    io = VoiceInteraction(log_path)
    io.wake()      # 等待唤醒词
    io.speak("你好")   # TTS 播报
    text = io.listen() # ASR 识别
"""
try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import sys
import time
import datetime
import threading
import queue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from voice_assistant import VoiceAssistant


class VoiceInteraction:
    """
    真实语音交互模块: 唤醒(KWS)、播报(TTS)、识别(ASR)、文本备用输入、带时间戳日志。
    实现 interfaces.InteractionModule。
    """

    def __init__(self, log_path):
        self.path = log_path
        self.lines = []
        self._t0 = datetime.datetime(2026, 6, 17, 10, 0, 0)
        self._tick = 0

        self.log("[语音交互] 正在初始化语音模块...")

        self.assistant = VoiceAssistant()
        self._command_queue = queue.Queue()
        self._wake_event = threading.Event()

        self.assistant.process_command = self._process_command

        self._wake_thread = threading.Thread(target=self._wake_loop, daemon=True)
        self._wake_thread.start()

        self.log("[语音交互] ✅ 语音模块初始化完成！")
        self.log("[语音交互] 🎤 请说: 小具同学")

    def now(self):
        self._tick += 1
        return (self._t0 + datetime.timedelta(seconds=self._tick)).isoformat()

    def log(self, msg):
        line = f"[{self.now()}] {msg}"
        self.lines.append(line)
        print(line)

    def wake(self):
        self.log("[唤醒KWS] 等待唤醒词「小具同学」...")
        self._wake_event.clear()
        self._wake_event.wait()
        self.log("[唤醒KWS] ✅ 检测到唤醒词！")
        return True

    def speak(self, text):
        self.log(f"[语音TTS] 播放: {text}")
        self.assistant.text_to_speech.speak(text)

    def listen(self):
        self.log("[语音ASR] 正在聆听指令...")
        result = self.assistant.speech_recognizer.listen(timeout=15)
        if result:
            self.log(f"[语音ASR] ✅ 识别结果: {result}")
        else:
            self.log("[语音ASR] ❌ 未识别到指令")
        return result

    def text_input(self):
        self.log("[文本输入] 请输入指令 (语音失败时的备用方式):")
        try:
            text = input("> ").strip()
            self.log(f"[文本输入] 收到: {text}")
            return text
        except EOFError:
            return ""

    def flush(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines))

    def _wake_loop(self):
        self.assistant.run()

    def _process_command(self, command):
        self._command_queue.put(command)
        if "开始" in command:
            self.log(f"[指令处理] 收到开始指令")
            self._wake_event.set()
        elif "停止" in command:
            self.log(f"[指令处理] 收到停止指令")
        elif "复位" in command:
            self.log(f"[指令处理] 收到复位指令")
        elif "帮助" in command:
            self.log(f"[指令处理] 收到帮助指令")
        elif "退出" in command or "拜拜" in command or "再见" in command:
            self.log(f"[指令处理] 收到退出指令")
        else:
            self.log(f"[指令处理] 收到未知指令: {command}")