#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音合成模块
使用 Windows SAPI（本地语音引擎，不需要网络，最稳定）
每次播放时重新创建 COM 对象，避免跨线程问题
"""

import win32com.client
import pythoncom


class TextToSpeech:
    def __init__(self):
        print("[语音合成] ✅ 已初始化语音合成引擎")

    def speak(self, text):
        """播放文本（每次都重新创建 COM 对象，避免跨线程问题）"""
        try:
            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")

            speaker.Rate = 0
            speaker.Volume = 100

            print(f"[语音合成] 播放: {text}")
            speaker.Speak(text)
            print(f"[语音合成] ✅ 播放完成")

            pythoncom.CoUninitialize()
        except Exception as e:
            print(f"[语音合成] ❌ 播放失败: {e}")
            try:
                pythoncom.CoUninitialize()
            except:
                pass

    def stop(self):
        """停止播放"""
        try:
            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak("", 2)
            pythoncom.CoUninitialize()
        except:
            pass
