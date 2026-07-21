#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音助手主类
协调唤醒词检测、指令识别和语音合成三个模块。
"""

import os
import sys
import time
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wake_word_detector import WakeWordDetector
from speech_recognizer import SpeechRecognizer
from text_to_speech import TextToSpeech


class VoiceAssistant:
    def __init__(self):
        self.is_running = True
        self.is_awake = False
        self.wake_lock = threading.Lock()

        print("[系统] 正在初始化各模块...")
        print()

        self.wake_word_detector = WakeWordDetector()
        self.speech_recognizer = SpeechRecognizer()
        self.text_to_speech = TextToSpeech()

        self.wake_word_detector.set_callback(self.on_wake_word_detected)
        self.speech_recognizer.set_callback(self.on_speech_recognized)

        print()
        print("[系统] 所有模块初始化完成！")

    def on_wake_word_detected(self):
        """唤醒词检测回调"""
        with self.wake_lock:
            if self.is_awake:
                return
            self.is_awake = True

        print()
        print("=" * 40)
        print("[系统] 检测到唤醒词！")
        print("=" * 40)

        # 语音回应（只说一次！）
        self.text_to_speech.speak("我已就绪，请下达指令")

        # 在新线程中监听指令
        threading.Thread(target=self.listen_for_command, daemon=True).start()

    def listen_for_command(self):
        """监听用户指令（循环监听，支持连续下达多个指令）"""
        print()
        print("=" * 40)
        print("[系统] 进入指令模式")
        print("[系统] 支持指令: 开始、停止、复位、帮助、退出")
        print("[系统] 说 '退出' 返回唤醒模式")
        print("=" * 40)
        print()

        while self.is_awake:
            recognized_text = self.speech_recognizer.listen(timeout=10)

            if recognized_text:
                print()
                print(f"{'='*20}")
                print(f"[用户] {recognized_text}")
                print(f"{'='*20}")
                self.process_command(recognized_text)

                # 如果是退出指令，结束循环
                if "退出" in recognized_text or "拜拜" in recognized_text or "再见" in recognized_text:
                    break

                print()
                print("[系统] 请继续下达指令...")
            else:
                # 超时未说话，继续等待，不退出
                print("[系统] 未检测到语音，请再说一次")
                print()

        with self.wake_lock:
            self.is_awake = False

        # 延迟恢复唤醒词检测（等待 TTS 播放完全结束，防止回声）
        print("[系统] 等待 TTS 播放结束...")
        time.sleep(3)

        # 恢复唤醒词检测
        self.wake_word_detector.resume()

        print()
        print("[系统] 返回唤醒监听模式...")
        print("[系统] 请说: 小具同学")

    def on_speech_recognized(self, text):
        """语音识别回调"""
        print(f"[识别结果] {text}")

    def process_command(self, command):
        """处理用户指令"""
        command = command.strip()

        if not command:
            return

        response = self.generate_response(command)
        print(f"[机器人] {response}")
        self.text_to_speech.speak(response)

    def generate_response(self, command):
        """根据指令生成回复"""
        command_lower = command.lower()

        if "你好" in command_lower or "hello" in command_lower:
            return "你好！我是小具同学，很高兴为你服务。"
        elif "开始" in command_lower or "启动" in command_lower or "开始执行" in command_lower:
            return "好的，开始执行装配任务。"
        elif "停止" in command_lower or "停下" in command_lower or "暂停" in command_lower:
            return "已停止当前任务。"
        elif "复位" in command_lower or "复位" in command_lower or "归位" in command_lower or "回零" in command_lower or "重置" in command_lower or "复位" in command_lower:
            return "正在复位机器人位置。"
        elif "帮助" in command_lower or "指令" in command_lower or "能做什么" in command_lower:
            return "我可以执行装配任务，支持的指令有：开始、停止、复位、上料、下料、装配。"
        elif "上料" in command_lower or "取料" in command_lower:
            return "正在执行上料操作。"
        elif "下料" in command_lower or "放料" in command_lower:
            return "正在执行下料操作。"
        elif "装配" in command_lower or "组装" in command_lower:
            return "正在执行装配操作。"
        elif "检测" in command_lower or "检查" in command_lower:
            return "正在进行质量检测。"
        elif "退出" in command_lower or "拜拜" in command_lower or "再见" in command_lower:
            return "好的，返回唤醒模式。"
        else:
            return f"收到指令：{command}，正在执行中。"

    def text_input_mode(self):
        """文本输入模式（语音识别失败时使用，需裁判同意）"""
        print()
        print("=" * 50)
        print("          文本输入模式（需裁判同意）")
        print("=" * 50)
        print("请输入指令（输入 'q' 退出文本模式）：")
        print()

        try:
            import sys
            line = sys.stdin.readline()
            if line:
                text = line.strip()
                if text.lower() == 'q':
                    print("[系统] 退出文本输入模式")
                elif text:
                    print(f"[用户] {text}")
                    self.process_command(text)
        except Exception as e:
            print(f"[系统] 文本输入出错: {e}")

    def run(self):
        """主运行循环"""
        print()
        print("[系统] 启动语音助手...")

        if not self.wake_word_detector.vosk_recognizer:
            print("[系统] ❌ 唤醒词检测器未初始化，无法启动语音助手")
            print("[系统] ⚠️ 请检查 Vosk 模型是否正确下载和配置")
            print("[系统] ⚠️ 将进入文本输入模式")
            while self.is_running:
                self.text_input_mode()
                time.sleep(0.5)
            return

        # 启动唤醒词检测线程（非 daemon，防止程序退出）
        wake_thread = threading.Thread(target=self.wake_word_detector.start)
        wake_thread.daemon = False
        wake_thread.start()

        print()
        print("[系统] 语音助手已启动！")
        print("[系统] 请对麦克风说: 小具同学")
        print("[系统] 按 Ctrl+C 退出程序")
        print()

        try:
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print()
            print("[系统] 正在退出...")

        self.is_running = False
        self.wake_word_detector.stop()

        # 等待唤醒线程结束
        wake_thread.join(timeout=2)

        print("[系统] 语音助手已停止")
