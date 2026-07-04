"""
cognition.py — 认知层 (大模型智能体的仿真替身)

真实赛场: 多模态 VLM 读任务卡图片 -> 输出结构化 JSON。
本仿真: 用规则解析器模拟该行为, 把任务卡 2 的中文指令文本解析为
{block_color -> tray_color, order}, 并附置信度与时间戳, 落盘日志(赛题强制要求)。

核心原则: 大模型只做语义解析, 不输出坐标。坐标由 vision.py 负责。
"""
import re
import json
import datetime

import interfaces  # 契约来源; 不 import 任何 sim 模块, 无循环导入 (注解可选)

# 任务卡 2 示例指令 (来自任务书原文)
SAMPLE_CARD2 = (
    "先把红色方块放到黄色托盘上，再把绿色方块放到红色托盘上，"
    "接着把橙色方块放到蓝色托盘上，然后把蓝色方块放到紫色托盘上，"
    "再把黄色方块放到橙色托盘上，最后把紫色方块放到绿色托盘上"
)

CN2EN = {"红": "red", "橙": "orange", "黄": "yellow",
         "绿": "green", "蓝": "blue", "紫": "purple"}


def parse_card2(text, now_iso):
    """模拟 VLM 解析装配指令 -> 结构化 JSON。"""
    pat = re.compile(r"([红橙黄绿蓝紫])色方块放到([红橙黄绿蓝紫])色托盘")
    seq = []
    for i, (blk, tray) in enumerate(pat.findall(text), 1):
        seq.append({"step": i, "block_color": CN2EN[blk], "tray_color": CN2EN[tray]})
    ok = len(seq) == 6
    return {
        "task": "assembly",
        "timestamp": now_iso,
        "confidence": 0.97 if ok else 0.4,
        "recognized": ok,
        "sequence": seq,
    }


def parse_card1(scene_desc, now_iso):
    """模拟 VLM 场景识别 (任务一)。"""
    return {
        "task": "scene_recognition",
        "timestamp": now_iso,
        "confidence": 0.95,
        "recognized": True,
        "description": scene_desc,
    }


def check_confidence(parsed, threshold=0.6):
    """识别失败校验 -> 触发语音提示 (赛题强制)。"""
    if not parsed.get("recognized") or parsed.get("confidence", 0) < threshold:
        return False, "任务卡识别失败，请确认任务卡位置"
    return True, None


class RuleBasedCognition:
    """
    认知层的规则桩实现 (interfaces.CognitionModule)。

    只做语义解析, 不输出坐标。所有逻辑委托给本模块的 module-level 函数,
    行为与原函数逐字一致; 本类只提供"符合 Protocol 的类"外壳。
    真机换上 ClaudeVLMCognition 时接口不变, 主流程零改动。
    """

    def parse_card1(
        self, scene_desc: str, now_iso: str
    ) -> "interfaces.SceneResult":
        """任务一: 场景识别 -> 结构化描述 + 置信度 + 时间戳。"""
        return parse_card1(scene_desc, now_iso)

    def parse_card2(
        self, card: str, now_iso: str
    ) -> "interfaces.AssemblyPlan":
        """任务二: 装配指令 -> {方块色->托盘色, 顺序} + 置信度 + 时间戳。"""
        return parse_card2(card, now_iso)

    def check_confidence(self, parsed, threshold: float = 0.6):
        """置信度校验 (赛题强制): 不达标 -> (False, 失败话术)。"""
        return check_confidence(parsed, threshold)
