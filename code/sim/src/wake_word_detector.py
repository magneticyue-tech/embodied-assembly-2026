#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
唤醒词检测模块
借鉴小智项目的专用唤醒词引擎思路，使用 Vosk 语法约束功能，
让识别器只关注唤醒词，大幅提高准确率。
"""

import os
import sys
import time
import json
import queue
import threading

import numpy as np
import sounddevice as sd


class WakeWordDetector:
    def __init__(self):
        self.is_running = False
        self.is_paused = False  # 暂停检测（触发后暂停，等指令完成后恢复）
        self.callback = None
        self.vosk_model = None
        self.vosk_recognizer = None
        self.model_dir = None
        self.audio_queue = queue.Queue()
        self._init_detector()

    def _init_detector(self):
        try:
            from vosk import Model, KaldiRecognizer
            import tempfile
            import shutil

            model_dir_large = os.path.join(os.path.dirname(__file__), "..", "model", "vosk-model-cn-0.22")
            model_dir_small = os.path.join(os.path.dirname(__file__), "..", "model", "vosk-model-small-cn-0.22")

            if os.path.exists(model_dir_large):
                src_model_dir = model_dir_large
                print("[唤醒模块] 使用 Vosk 大模型（准确率更高）")
            elif os.path.exists(model_dir_small):
                src_model_dir = model_dir_small
                print("[唤醒模块] 使用 Vosk 小模型（速度快）")
            else:
                print("[唤醒模块] ❌ 未找到 Vosk 模型！")
                print("[唤醒模块] 请运行: python download_vosk_model.py")
                return

            print("[唤醒模块] 复制模型到临时目录（避免中文路径问题）...")
            tmp_dir = tempfile.mkdtemp(prefix='vosk_')
            self.model_dir = os.path.join(tmp_dir, 'model')
            shutil.copytree(src_model_dir, self.model_dir)
            print(f"[唤醒模块] 模型临时路径: {self.model_dir}")

            try:
                self.vosk_model = Model(self.model_dir)
            except Exception as e:
                print(f"[唤醒模块] ❌ 模型加载失败: {e}")
                import traceback
                traceback.print_exc()
                shutil.rmtree(tmp_dir)
                return

            # 借鉴小智项目的思路：专用唤醒词引擎
            # 使用 Vosk 语法约束，只识别唤醒词，不识别其他词
            # 格式：JSON 数组，包含所有允许识别的短语
            self.grammar_phrases = [
                "小具同学",
                "小菊同学",
                "小居同学",
                "小举同学",
                "小巨同学",
                "小具",
                "小菊",
                "小居",
                "小举",
                "小巨",
                "具同学",
                "菊同学",
                "居同学",
                "举同学",
                "巨同学",
                "[unk]"
            ]

            grammar_json = json.dumps(self.grammar_phrases, ensure_ascii=False)
            print(f"[唤醒模块] 尝试创建识别器...")
            try:
                self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000, grammar_json)
                self.vosk_recognizer.SetWords(True)
                print(f"[唤醒模块] ✅ 已加载 Vosk 中文语音模型")
                print(f"[唤醒模块] 🎤 使用语法约束模式（借鉴小智专用唤醒词引擎）")
                print(f"[唤醒模块] 🎤 监听唤醒词: 小具同学")
            except Exception as e:
                print(f"[唤醒模块] ❌ 创建识别器失败: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                return

        except Exception as e:
            print(f"[唤醒模块] ❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()

    def set_callback(self, callback):
        self.callback = callback

    def _check_wake_word(self, text):
        """检查识别结果是否包含唤醒词"""
        if not text:
            return False

        text = text.strip()

        # 唤醒词变体列表（防止同音字识别错误）
        keywords = [
            "小具同学", "小菊同学", "小居同学", "小举同学", "小巨同学",
            "小具", "小菊", "小居", "小举", "小巨",
            "具同学", "菊同学", "居同学", "举同学", "巨同学",
            "小聚", "小锯", "小桔", "小驹", "小锯同学"
        ]

        for keyword in keywords:
            if keyword in text:
                return True

        return False

    def _audio_callback(self, indata, frames, time_info, status):
        """音频回调函数，将音频数据放入队列"""
        self.audio_queue.put(bytes(indata))

    def _compute_energy(self, audio_data):
        """计算音频能量（用于语音活动检测 VAD）"""
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        # 归一化到 [-1, 1]
        audio_array = audio_array / 32768.0
        # 计算 RMS 能量
        energy = np.sqrt(np.mean(audio_array ** 2))
        return energy

    def detect_wake_word(self):
        """主检测循环"""
        if not self.vosk_recognizer:
            print("[唤醒模块] ❌ 识别器未初始化")
            return

        print("[唤醒模块] 🟢 开始监听唤醒词...")
        print("[唤醒模块] 请对麦克风说: 小具同学")

        sample_rate = 16000
        chunk_size = 800  # 50ms 一帧

        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='int16',
            blocksize=chunk_size,
            callback=self._audio_callback
        )

        stream.start()

        # VAD 参数
        energy_threshold = 0.01  # 能量阈值，低于此值认为是静音
        silence_timeout = 0  # 静音计数器

        while self.is_running:
            try:
                # 如果暂停了，就清空队列并跳过检测
                if self.is_paused:
                    while not self.audio_queue.empty():
                        self.audio_queue.get()
                    time.sleep(0.1)
                    continue

                # 从队列获取音频数据
                triggered = False
                while not self.audio_queue.empty():
                    audio_data = self.audio_queue.get()

                    # 计算音频能量
                    energy = self._compute_energy(audio_data)

                    if energy > energy_threshold:
                        # 有声音，喂给识别器
                        silence_timeout = 0

                        if self.vosk_recognizer.AcceptWaveform(audio_data):
                            # 完整识别结果
                            result = self.vosk_recognizer.Result()
                            result_dict = json.loads(result)
                            text = result_dict.get("text", "")

                            if text and text != "[unk]":
                                print(f"[唤醒模块] 识别到: {text}")
                                if self._check_wake_word(text):
                                    print("[唤醒模块] 🎉 检测到唤醒词！")
                                    self._trigger_wake()
                                    triggered = True
                                    break
                        else:
                            # 部分识别结果（实时反馈，提高响应速度）
                            partial = self.vosk_recognizer.PartialResult()
                            partial_dict = json.loads(partial)
                            partial_text = partial_dict.get("partial", "")

                            if partial_text and len(partial_text) > 1 and partial_text != "[unk]":
                                if self._check_wake_word(partial_text):
                                    print(f"[唤醒模块] 🎉 检测到唤醒词！(partial: {partial_text})")
                                    self._trigger_wake()
                                    triggered = True
                                    break
                    else:
                        silence_timeout += 1
                        # 长时间静音时重置识别器
                        if silence_timeout > 40:
                            self.vosk_recognizer.Reset()
                            silence_timeout = 0

                if triggered:
                    continue

                time.sleep(0.005)

            except Exception as e:
                print(f"[唤醒模块] 检测错误: {e}")
                time.sleep(0.5)

        stream.stop()
        stream.close()

    def _trigger_wake(self):
        """触发唤醒：暂停检测，清空队列，调用回调"""
        # 如果已经暂停了，直接返回（防止重复触发）
        if self.is_paused:
            return
        # 先暂停，防止重复触发
        self.is_paused = True
        # 清空音频队列（丢弃 TTS 回声等）
        while not self.audio_queue.empty():
            self.audio_queue.get()
        self.vosk_recognizer.Reset()
        # 调用回调
        if self.callback:
            self.callback()

    def pause(self):
        """暂停唤醒词检测（指令执行时调用）"""
        self.is_paused = True
        # 清空队列，避免恢复时处理旧音频
        while not self.audio_queue.empty():
            self.audio_queue.get()
        if self.vosk_recognizer:
            self.vosk_recognizer.Reset()

    def resume(self):
        """恢复唤醒词检测（指令完成后调用）"""
        self.is_paused = False

    def start(self):
        """启动唤醒词检测"""
        if not self.vosk_recognizer:
            print("[唤醒模块] ❌ 无法启动：识别器未初始化，请检查模型是否正确加载")
            return
        
        self.is_running = True
        self.is_paused = False
        self.detect_wake_word()

    def stop(self):
        """停止唤醒词检测"""
        self.is_running = False
