"""
execution.py — 执行层 (机器人控制的仿真替身, 对应 AUBO-i5)

真实赛场: 坐标变换链 -> 运动规划 -> 吸盘抓放 (AUBO-i5)。
本仿真: 验证逻辑正确性 —— 给定视觉的台面坐标+角度, 记录抓放动作, 评估定位误差,
并以同心环精度尺的环数读出最终放置偏移 (对应托盘评分方式)。
不做物理动力学 (pybullet 未接入; 真机用 AUBO SDK / ARCS 仿真)。

误差构成: AUBO-i5 厂商标称重复定位精度 ±0.02mm; 本仿真的放置偏移
只计算视觉定位误差, 未包含机械臂误差与标定误差。

拆分 (符合 interfaces 契约):
  - SimRobot 实现 interfaces.RobotController — 只负责运动, 不接触 ground-truth。
  - AuboRobot 实现 interfaces.RobotController — AUBO-i5 真机控制器, 通过 UDP 与 C 进程通信。
  - RingEvaluator 是仿真专属评分器 (不属于任何 Protocol), 用 scene 真值计算
    定位误差与落环。
  - TransformConfig / table_to_robot / robot_to_table — 坐标变换模块。
  - RobotCommunicator — 与 C 进程的 UDP 通信协议模块。

配置说明:
  真实机器接口、IP地址、端口号、坐标变换参数等暂未确定，
  采用外部输入方式：
  1. 通过 config.py 配置文件设置默认值
  2. 通过命令行参数覆盖（见 parse_args 函数）
  3. 通过函数参数传入

"""
import math
import json
import socket
import time
import argparse
import sys
sys.path.append('../sim')
import config as C
import interfaces
from typing import TypedDict, Optional, Any


class TransformConfig(TypedDict):
    """
    坐标变换配置: 台面坐标系与机器人基座坐标系之间的仿射变换参数。

    变换顺序: 平移 -> 旋转 -> 缩放
    逆变换顺序: 逆缩放 -> 逆旋转 -> 逆平移

    参数说明:
        x_offset: X 轴平移量 (mm) — 台面原点相对于机器人基座原点的 X 偏移
        y_offset: Y 轴平移量 (mm) — 台面原点相对于机器人基座原点的 Y 偏移
        rotation_deg: 旋转角度 (度) — 台面坐标系相对于机器人基座坐标系的旋转角
        scale: 缩放因子 — 台面坐标系与机器人基座坐标系的比例尺（通常为 1.0）
    """
    x_offset: float
    y_offset: float
    rotation_deg: float
    scale: float


DEFAULT_TRANSFORM_CONFIG: TransformConfig = {
    "x_offset": 0.0,
    "y_offset": 0.0,
    "rotation_deg": 0.0,
    "scale": 1.0,
}


def table_to_robot(x: float, y: float, deg: float, config: TransformConfig) -> tuple[float, float, float]:
    """
    将台面坐标系下的位姿转换为机器人基座坐标系。

    变换顺序: 平移 -> 旋转 -> 缩放 (角度叠加旋转)。
    台面原点通常是相机视野中心或标定板原点。

    Args:
        x: 台面坐标系 X 坐标 (mm)
        y: 台面坐标系 Y 坐标 (mm)
        deg: 台面坐标系旋转角度 (度)
        config: 坐标变换配置

    Returns:
        tuple[float, float, float]: 机器人基座坐标系下的 (x, y, deg)
    """
    tx = x + config["x_offset"]
    ty = y + config["y_offset"]

    theta = math.radians(config["rotation_deg"])
    cx = math.cos(theta)
    sx = math.sin(theta)
    rx = tx * cx - ty * sx
    ry = tx * sx + ty * cx

    sx = rx * config["scale"]
    sy = ry * config["scale"]
    sdeg = deg + config["rotation_deg"]

    return sx, sy, sdeg


def robot_to_table(x: float, y: float, deg: float, config: TransformConfig) -> tuple[float, float, float]:
    """
    将机器人基座坐标系下的位姿逆变换回台面坐标系。

    逆变换顺序: 逆缩放 -> 逆旋转 -> 逆平移 (角度减去旋转)。

    Args:
        x: 机器人基座坐标系 X 坐标 (mm)
        y: 机器人基座坐标系 Y 坐标 (mm)
        deg: 机器人基座坐标系旋转角度 (度)
        config: 坐标变换配置

    Returns:
        tuple[float, float, float]: 台面坐标系下的 (x, y, deg)
    """
    rx = x / config["scale"]
    ry = y / config["scale"]

    theta = math.radians(-config["rotation_deg"])
    cx = math.cos(theta)
    sx = math.sin(theta)
    tx = rx * cx - ry * sx
    ty = rx * sx + ry * cx

    tx -= config["x_offset"]
    ty -= config["y_offset"]
    tdeg = deg - config["rotation_deg"]

    return tx, ty, tdeg


def offset_to_ring(offset_mm):
    """
    把放置偏移 (mm) 换算成落在第几环 (1mm/环, 每 5mm 加粗)。

    Args:
        offset_mm: 放置偏移量 (mm)

    Returns:
        tuple[int, str]: (环数, 加粗标记)
    """
    ring = int(round(offset_mm / C.RING_STEP_MM))
    bold = " (加粗环)" if ring % C.RING_BOLD_EVERY == 0 and ring > 0 else ""
    return ring, bold


class SimRobot:
    """
    实现 interfaces.RobotController: 仿真机器人控制器 (只负责运动, 不接触 ground-truth)。

    本类是仿真模式下的机器人实现，只打印执行日志，不进行实际运动。
    用于验证逻辑正确性，与 AuboRobot 接口完全一致，便于模式切换。
    """

    def __init__(self, io):
        """
        初始化仿真机器人。

        Args:
            io: 交互模块实例，用于日志记录和语音播报
        """
        self.io = io
        self.held = None

    def pick(self, color, target):
        """
        模拟抓取动作。

        Args:
            color: 方块颜色 (red/orange/yellow/green/blue/purple)
            target: 目标位姿 (BlockPose)，包含 x, y, deg, uv
        """
        self.io.log(f"  [执行] AUBO-i5 移至拍照点上方 -> 对准 {color}块 中心({target['x']:.1f},{target['y']:.1f})mm 角度{target['deg']:+.1f}° -> 吸盘抓取")
        self.held = color

    def place(self, block_color, tray_color, target):
        """
        模拟放置动作。

        Args:
            block_color: 方块颜色
            tray_color: 托盘颜色
            target: 目标位姿 (SlotPose)，包含 x, y, deg, uv
        """
        self.io.log(f"  [执行] 搬运 {block_color}块 -> {tray_color}托盘中心({target['x']:.1f},{target['y']:.1f})mm -> 释放吸盘")
        self.held = None


class AuboRobot:
    """
    实现 interfaces.RobotController: AUBO-i5 真机控制器, 通过 UDP 与 C 进程通信。

    本类是真机模式下的机器人实现，通过 UDP 协议与 C 语言驱动进程通信，
    将指令发送给真实的 AUBO-i5 机械臂执行。

    通信流程:
        1. 接收视觉模块的目标位姿（台面坐标系）
        2. 通过 table_to_robot() 转换为机器人基座坐标系
        3. 构造 JSON 指令，通过 RobotCommunicator 发送给 C 进程
        4. 接收 C 进程的执行结果响应
        5. 记录日志并更新 held 状态

    错误处理:
        - 通信超时自动重试（默认 3 次）
        - 连接失败记录错误日志
        - 执行失败记录错误信息
    """

    def __init__(self, io, transform_config: TransformConfig = None,
                 host: str = None, port: int = None):
        """
        初始化 AUBO-i5 真机控制器。

        参数优先顺序: 函数参数 > config.py 配置 > 默认值

        Args:
            io: 交互模块实例，用于日志记录和语音播报
            transform_config: 坐标变换配置（可选，默认使用 config.py 或 DEFAULT_TRANSFORM_CONFIG）
            host: C 驱动进程的 IP 地址（可选，默认使用 config.py 或 "127.0.0.1"）
            port: C 驱动进程的端口号（可选，默认使用 config.py 或 5000）
        """
        self.io = io

        if transform_config is None:
            if hasattr(C, 'TRANSFORM_CONFIG'):
                self.transform_config = C.TRANSFORM_CONFIG
            else:
                self.transform_config = DEFAULT_TRANSFORM_CONFIG
        else:
            self.transform_config = transform_config

        if host is None:
            if hasattr(C, 'ROBOT_HOST'):
                host = C.ROBOT_HOST
            else:
                host = DEFAULT_ROBOT_HOST

        if port is None:
            if hasattr(C, 'ROBOT_PORT'):
                port = C.ROBOT_PORT
            else:
                port = DEFAULT_ROBOT_PORT

        self.comm = RobotCommunicator(host=host, port=port)
        self.held = None

    def pick(self, color, target):
        """
        执行抓取动作。

        Args:
            color: 方块颜色
            target: 目标位姿 (BlockPose)
        """
        rx, ry, rdeg = table_to_robot(target['x'], target['y'], target['deg'], self.transform_config)
        cmd = {"cmd": "PICK", "color": color, "x": rx, "y": ry, "deg": rdeg}
        self.io.log(f"  [执行] 发送 PICK 指令 -> {color}块 (机器人坐标: ({rx:.1f},{ry:.1f})mm, 角度{rdeg:+.1f}°)")

        response = self.comm.send_command(cmd)
        if response.get("success"):
            self.io.log(f"  [执行] PICK 成功: {response.get('message', '')}")
            self.held = color
        else:
            self.io.log(f"  [执行] PICK 失败: {response.get('message', '未知错误')}")

    def place(self, block_color, tray_color, target):
        """
        执行放置动作。

        Args:
            block_color: 方块颜色
            tray_color: 托盘颜色
            target: 目标位姿 (SlotPose)
        """
        rx, ry, rdeg = table_to_robot(target['x'], target['y'], target['deg'], self.transform_config)
        cmd = {"cmd": "PLACE", "block_color": block_color, "tray_color": tray_color, "x": rx, "y": ry, "deg": rdeg}
        self.io.log(f"  [执行] 发送 PLACE 指令 -> {block_color}块 -> {tray_color}托盘 (机器人坐标: ({rx:.1f},{ry:.1f})mm, 角度{rdeg:+.1f}°)")

        response = self.comm.send_command(cmd)
        if response.get("success"):
            self.io.log(f"  [执行] PLACE 成功: {response.get('message', '')}")
            self.held = None
        else:
            self.io.log(f"  [执行] PLACE 失败: {response.get('message', '未知错误')}")

    def close(self):
        """关闭与 C 进程的通信连接。"""
        self.comm.close()


class RingEvaluator:
    """
    仿真专属评分器 (非 Protocol): 用 scene 真值计算定位误差与同心环落环。
    """

    def __init__(self, scene, io):
        self.scene = scene
        self.io = io

    def score_pick(self, color, det_block):
        t = self.scene.blocks[color]
        derr = math.dist((det_block['x'], det_block['y']), (t['x'], t['y']))
        aerr = abs(_fold90(det_block['deg'] - t['deg']))
        self.io.log(f"  [执行] 视觉定位误差 {derr:.2f}mm, 角度误差 {aerr:.1f}°")
        return derr

    def score_place(self, tray_color, det_slot, pick_err):
        true_tray = self.scene.slot_table_pos(tray_color)
        tray_err = math.dist((det_slot['x'], det_slot['y']), (true_tray['x'], true_tray['y']))
        total = pick_err + tray_err
        ring, bold = offset_to_ring(total)
        ok = total <= C.PLACE_TOLERANCE_MM
        self.io.log(f"  [评分] 放置偏移 ≈{total:.2f}mm -> 落在第 {ring} 环{bold} -> {'达标' if ok else '超差'} (预算 {C.PLACE_TOLERANCE_MM}mm)")
        return total, ring, ok


def _fold90(deg):
    return ((deg + 45) % 90) - 45


DEFAULT_ROBOT_HOST = "127.0.0.1"
DEFAULT_ROBOT_PORT = 5000
DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0


class RobotCommunicator:
    """与 C 进程的 UDP 通信协议模块。"""

    def __init__(self, host: str = DEFAULT_ROBOT_HOST, port: int = DEFAULT_ROBOT_PORT, 
                 timeout: float = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_MAX_RETRIES,
                 retry_delay: float = DEFAULT_RETRY_DELAY):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.socket: Optional[socket.socket] = None

    def _create_socket(self):
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(self.timeout)

    def _generate_request_id(self) -> str:
        import uuid
        return str(uuid.uuid4())[:8]

    def send_command(self, cmd_dict: dict[str, Any], retry_on_fail: bool = True) -> dict[str, Any]:
        self._create_socket()

        request_id = self._generate_request_id()
        cmd_with_id = dict(cmd_dict, request_id=request_id)

        last_error = None
        retries = self.max_retries if retry_on_fail else 1

        for attempt in range(retries):
            try:
                data = json.dumps(cmd_with_id, separators=(',', ':')).encode("utf-8")
                self.socket.sendto(data, (self.host, self.port))
                response_data, _ = self.socket.recvfrom(4096)
                response = json.loads(response_data.decode("utf-8"))
                
                if response.get("request_id") != request_id:
                    last_error = f"请求ID不匹配: 发送 {request_id}, 收到 {response.get('request_id')}"
                    continue
                
                return response

            except socket.timeout:
                last_error = f"通信超时 (>{self.timeout}s)"
            except ConnectionRefusedError:
                last_error = f"连接被拒绝: {self.host}:{self.port}"
            except OSError as e:
                last_error = f"网络错误: {str(e)}"
            except json.JSONDecodeError:
                last_error = "响应格式错误, 无法解析 JSON"
            except Exception as e:
                last_error = f"未知错误: {str(e)}"

            if attempt < retries - 1:
                time.sleep(self.retry_delay)

        return {"success": False, "message": last_error}

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def __del__(self):
        self.close()


def parse_args():
    """解析命令行参数，支持外部配置。"""
    parser = argparse.ArgumentParser(description="AUBO-i5 机械臂控制器 - 执行层")

    parser.add_argument("--mode", type=str, choices=["sim", "real"],
                        help="运行模式: sim (仿真) / real (真机)")

    parser.add_argument("--robot-host", type=str,
                        help="机器人驱动主机地址 (默认: 127.0.0.1)")
    parser.add_argument("--robot-port", type=int,
                        help="机器人驱动端口号 (默认: 5000)")

    parser.add_argument("--x-offset", type=float,
                        help="X 轴平移量 (mm)")
    parser.add_argument("--y-offset", type=float,
                        help="Y 轴平移量 (mm)")
    parser.add_argument("--rotation-deg", type=float,
                        help="旋转角度 (度)")
    parser.add_argument("--scale", type=float,
                        help="缩放因子")

    return parser.parse_args()


def apply_args_to_config(args):
    """将命令行参数应用到全局配置。"""
    config = {}

    if args.mode:
        config["RUN_MODE"] = args.mode

    if args.robot_host:
        config["ROBOT_HOST"] = args.robot_host
    if args.robot_port:
        config["ROBOT_PORT"] = args.robot_port

    transform_config = dict(DEFAULT_TRANSFORM_CONFIG)
    if args.x_offset is not None:
        transform_config["x_offset"] = args.x_offset
    if args.y_offset is not None:
        transform_config["y_offset"] = args.y_offset
    if args.rotation_deg is not None:
        transform_config["rotation_deg"] = args.rotation_deg
    if args.scale is not None:
        transform_config["scale"] = args.scale

    if transform_config != DEFAULT_TRANSFORM_CONFIG:
        config["TRANSFORM_CONFIG"] = transform_config

    return config
