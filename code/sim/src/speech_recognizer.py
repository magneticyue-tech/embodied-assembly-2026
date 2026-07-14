#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
指令识别模块
使用 faster-whisper 进行指令识别，修复静音检测和音频处理逻辑。
"""

import os
import sys
import time
import json
import queue

import numpy as np
import sounddevice as sd


class SpeechRecognizer:
    def __init__(self):
        self.callback = None
        self.recognizer = None
        self.vosk_recognizer = None
        self.vosk_model = None
        self._init_recognizer()

    def _init_recognizer(self):
        try:
            from faster_whisper import WhisperModel
            self.recognizer = WhisperModel("small", device="cpu", compute_type="int8")
            print("[语音识别] 已加载 faster-whisper 语音识别模型")
        except Exception as e:
            print(f"[语音识别] faster-whisper 初始化失败: {e}")
            print("[语音识别] 回退到 Vosk")
            self._init_vosk_recognizer()

    def _init_vosk_recognizer(self):
        try:
            from vosk import Model, KaldiRecognizer

            model_dir_large = os.path.join(os.path.dirname(__file__), "..", "model", "vosk-model-cn-0.22")
            model_dir_small = os.path.join(os.path.dirname(__file__), "..", "model", "vosk-model-small-cn-0.22")

            if os.path.exists(model_dir_large):
                model_dir = model_dir_large
                print("[语音识别] 使用 Vosk 大模型")
            elif os.path.exists(model_dir_small):
                model_dir = model_dir_small
                print("[语音识别] 使用 Vosk 小模型")
            else:
                print("[语音识别] ❌ 未找到 Vosk 模型")
                return

            self.vosk_model = Model(model_dir)
            self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000)
            self.vosk_recognizer.SetWords(True)
            print("[语音识别] 已加载 Vosk 中文语音模型")

        except Exception as e:
            print(f"[语音识别] Vosk 初始化也失败: {e}")

    def set_callback(self, callback):
        self.callback = callback

    def listen(self, timeout=None):
        """监听用户指令，返回识别文本
        timeout: 超时时间（秒），超过后返回 None
        """
        if not self.recognizer and not self.vosk_recognizer:
            print("[语音识别] 识别器未初始化")
            return None

        print("[语音识别] 正在聆听指令...")
        print("[语音识别] 请说出指令（如：开始、停止、复位）")

        sample_rate = 16000
        chunk_size = 1600  # 100ms 一帧
        audio_queue = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            audio_queue.put(np.copy(indata[:, 0]))

        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            blocksize=chunk_size,
            callback=audio_callback
        )

        stream.start()

        # VAD 参数
        energy_threshold = 0.01    # 能量阈值
        silence_timeout = 0        # 静音计数
        max_silence = 20           # 静音多少帧后结束（2秒，增加容错）
        max_record_time = 150     # 最大录制帧数（15秒）
        total_frames = 0

        audio_chunks = []
        has_speech = False

        start_time = time.time()

        while True:
            try:
                # 检查超时
                if timeout is not None and (time.time() - start_time) > timeout:
                    print(f"[语音识别] 超时({timeout}秒)，未检测到语音")
                    break

                # 获取音频块
                if audio_queue.empty():
                    time.sleep(0.01)
                    continue

                chunk = audio_queue.get()
                total_frames += 1

                # 计算能量
                energy = np.sqrt(np.mean(chunk ** 2))

                if energy > energy_threshold:
                    # 有声音
                    if not has_speech:
                        print("[语音识别] 🎤 检测到声音，正在录音...")
                    audio_chunks.append(chunk)
                    silence_timeout = 0
                    has_speech = True
                else:
                    # 静音
                    if has_speech:
                        audio_chunks.append(chunk)  # 保留尾部静音
                        silence_timeout += 1

                # 结束条件：说过话后静音超过阈值，或录制时间到上限
                if (has_speech and silence_timeout >= max_silence) or total_frames >= max_record_time:
                    if has_speech:
                        print(f"[语音识别] 录音结束，共 {total_frames} 帧")
                    break

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[语音识别] 录音错误: {e}")
                break

        stream.stop()
        stream.close()

        # 处理音频
        if not audio_chunks:
            print("[语音识别] 未检测到语音")
            return None

        audio_array = np.concatenate(audio_chunks)

        # 去除前后静音
        if len(audio_array) > 0:
            # 归一化
            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                audio_array = audio_array / max_val

        # 使用 faster-whisper 识别
        if self.recognizer:
            try:
                segments, _ = self.recognizer.transcribe(
                    audio_array.astype(np.float32),
                    language="zh",
                    initial_prompt="开始,停止,复位,上料,下料,装配,检测,帮助,退出,你好"
                )
                text = " ".join([seg.text for seg in segments]).strip()
            except Exception as e:
                print(f"[语音识别] faster-whisper 识别失败: {e}")
                text = ""
        else:
            # 使用 Vosk 识别
            text = ""
            try:
                vosk_audio = (audio_array * 32767).astype(np.int16).tobytes()
                for i in range(0, len(vosk_audio), 4000):
                    chunk = vosk_audio[i:i+4000]
                    if self.vosk_recognizer.AcceptWaveform(chunk):
                        result = self.vosk_recognizer.Result()
                        result_dict = json.loads(result)
                        text += result_dict.get("text", "") + " "

                final_result = self.vosk_recognizer.FinalResult()
                final_dict = json.loads(final_result)
                text += final_dict.get("text", "")
            except Exception as e:
                print(f"[语音识别] Vosk 识别失败: {e}")
                text = ""

        text = text.strip()

        if text:
            print(f"[语音识别] ✅ 识别结果: {text}")
            return text
        else:
            print("[语音识别] ❌ 未识别到语音内容")
            return None
