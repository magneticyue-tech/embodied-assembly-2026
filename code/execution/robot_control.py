#!/usr/bin/env python3
"""
robot_control.py — AUBO-i5 机械臂控制脚本

本脚本提供机械臂的直接控制能力，支持：
  - 命令行模式：快速发送单个指令
  - 交互模式：交互式控制机械臂
  - 脚本模式：执行预定义的操作序列

使用示例:
  # 命令行模式 - 发送单个 PICK 指令
  python robot_control.py --host 192.168.1.100 --pick red --x 100 --y 50 --deg 0

  # 命令行模式 - 发送单个 PLACE 指令
  python robot_control.py --place red --tray blue --x 200 --y 100 --deg 90

  # 交互模式
  python robot_control.py --interactive

  # 脚本模式 - 执行预定义序列
  python robot_control.py --script sequence.json

通信协议: UDP + JSON
指令格式: {"cmd":"PICK","color":"red","x":100.0,"y":50.0,"deg":0.0,"request_id":"<uuid>"}
响应格式: {"success":true,"message":"Pick successful","request_id":"<uuid>"}
"""
import argparse
import json
import socket
import sys
import uuid
import time
import cmd
import subprocess
import os
import platform
from typing import Optional, Dict, Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_TIMEOUT = 5.0
DEFAULT_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0

DRIVER_SRC = os.path.join(os.path.dirname(__file__), "robot_driver", "robot_driver.c")
DRIVER_EXE = os.path.join(os.path.dirname(__file__), "robot_driver", "robot_driver.exe")


def find_compiler():
    import winreg

    devcpp_paths = [
        "C:/Program Files (x86)/Dev-Cpp/MinGW64/bin/gcc.exe",
        "C:/Dev-Cpp/MinGW64/bin/gcc.exe",
        "C:/Program Files/Dev-Cpp/MinGW64/bin/gcc.exe",
        "C:/Program Files (x86)/Dev-Cpp/mingw/bin/gcc.exe",
        "C:/Dev-Cpp/mingw/bin/gcc.exe",
        "D:/Dev-Cpp/MinGW64/bin/gcc.exe",
        "D:/Program Files (x86)/Dev-Cpp/MinGW64/bin/gcc.exe",
    ]

    for gcc_path in devcpp_paths:
        if os.path.exists(gcc_path):
            desc = "Dev-C++ MinGW"
            cmd = [gcc_path, "-std=c11", "-Wall", "-Wextra", DRIVER_SRC, "-lws2_32", "-o", DRIVER_EXE]
            return desc, cmd

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Dev-C++")
        install_path = winreg.QueryValueEx(key, "InstallPath")[0]
        winreg.CloseKey(key)
        gcc_path = os.path.join(install_path, "MinGW64", "bin", "gcc.exe")
        if os.path.exists(gcc_path):
            desc = "Dev-C++ MinGW (注册表)"
            cmd = [gcc_path, "-std=c11", "-Wall", "-Wextra", DRIVER_SRC, "-lws2_32", "-o", DRIVER_EXE]
            return desc, cmd
    except:
        pass

    compilers = [
        ("cl", "MSVC", ["cl", "/EHsc", "/Fe:" + DRIVER_EXE, DRIVER_SRC]),
        ("gcc", "MinGW GCC", ["gcc", "-std=c11", "-Wall", "-Wextra", DRIVER_SRC, "-lws2_32", "-o", DRIVER_EXE]),
        ("g++", "MinGW G++", ["g++", "-std=c++11", "-Wall", "-Wextra", DRIVER_SRC, "-lws2_32", "-o", DRIVER_EXE]),
    ]

    for name, desc, cmd in compilers:
        try:
            result = subprocess.run([name, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return desc, cmd
        except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
            pass

        try:
            result = subprocess.run([name, "/?"], capture_output=True, timeout=5)
            if result.returncode == 0 or result.returncode == 1:
                return desc, cmd
        except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
            pass

    return None, None


def compile_driver(force=False):
    if os.path.exists(DRIVER_EXE) and not force:
        print(f"  驱动已存在: {DRIVER_EXE}")
        return True

    if not os.path.exists(DRIVER_SRC):
        print(f"  错误: 源码文件不存在: {DRIVER_SRC}")
        return False

    print("  查找编译器...")
    compiler_desc, compile_cmd = find_compiler()

    if not compiler_desc:
        print("  错误: 未找到可用的编译器 (cl/gcc/g++)")
        print("        请安装 MinGW 或 Visual Studio")
        return False

    print(f"  使用编译器: {compiler_desc}")
    print(f"  编译命令: {' '.join(compile_cmd)}")

    try:
        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"  ✓ 编译成功")
            return True
        else:
            print(f"  ✗ 编译失败")
            print(f"    错误信息:\n{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("  ✗ 编译超时")
        return False
    except Exception as e:
        print(f"  ✗ 编译异常: {e}")
        return False


def start_driver(port=DEFAULT_PORT):
    if not os.path.exists(DRIVER_EXE):
        print("  错误: 驱动程序不存在，请先编译")
        return None

    print(f"  启动驱动程序 (端口: {port})...")
    try:
        process = subprocess.Popen(
            [DRIVER_EXE, "-p", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        time.sleep(1)
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            print(f"  ✗ 驱动启动失败: {output}")
            return None
        print("  ✓ 驱动启动成功")
        return process
    except Exception as e:
        print(f"  ✗ 驱动启动异常: {e}")
        return None


class RobotClient:
    """AUBO-i5 机械臂客户端"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 timeout: float = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_RETRY,
                 retry_delay: float = DEFAULT_RETRY_DELAY):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._socket: Optional[socket.socket] = None

    def _create_socket(self):
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.settimeout(self.timeout)

    def _generate_request_id(self) -> str:
        return uuid.uuid4().hex

    def send_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """发送指令并接收响应"""
        self._create_socket()

        request_id = self._generate_request_id()
        cmd_with_id = dict(cmd_dict, request_id=request_id)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                data = json.dumps(cmd_with_id, separators=(',', ':')).encode("utf-8")
                self._socket.sendto(data, (self.host, self.port))
                response_data, _ = self._socket.recvfrom(4096)
                response = json.loads(response_data.decode("utf-8"))

                if response.get("request_id") != request_id:
                    last_error = f"请求ID不匹配"
                    continue

                return response

            except socket.timeout:
                last_error = f"通信超时 ({self.timeout}s)"
            except ConnectionRefusedError:
                last_error = f"连接被拒绝: {self.host}:{self.port}"
            except OSError as e:
                last_error = f"网络错误: {str(e)}"
            except json.JSONDecodeError:
                last_error = "响应格式错误"
            except Exception as e:
                last_error = f"未知错误: {str(e)}"

            if attempt < self.max_retries - 1:
                print(f"  重试 {attempt + 1}/{self.max_retries}...")
                time.sleep(self.retry_delay)

        return {"success": False, "message": last_error, "request_id": request_id}

    def pick(self, color: str, x: float, y: float, deg: float) -> Dict[str, Any]:
        """发送抓取指令"""
        cmd = {"cmd": "PICK", "color": color, "x": x, "y": y, "deg": deg}
        print(f"发送 PICK 指令: {color}块 @ ({x:.1f}, {y:.1f})mm, {deg:.1f}°")
        return self.send_command(cmd)

    def place(self, block_color: str, tray_color: str,
              x: float, y: float, deg: float) -> Dict[str, Any]:
        """发送放置指令"""
        cmd = {"cmd": "PLACE", "block_color": block_color, "tray_color": tray_color,
               "x": x, "y": y, "deg": deg}
        print(f"发送 PLACE 指令: {block_color}块 -> {tray_color}托盘 @ ({x:.1f}, {y:.1f})mm, {deg:.1f}°")
        return self.send_command(cmd)

    def close(self):
        """关闭连接"""
        if self._socket is not None:
            self._socket.close()
            self._socket = None


class RobotShell(cmd.Cmd):
    """机械臂交互命令行"""

    intro = """
==========================================
  AUBO-i5 机械臂交互控制终端
==========================================

可用命令:
  pick     - 抓取方块  (pick <color> <x> <y> <deg>)
  place    - 放置方块  (place <block> <tray> <x> <y> <deg>)
  test     - 测试连接
  status   - 显示当前配置
  quit     - 退出

示例:
  pick red 100 50 0
  place red blue 200 100 90

==========================================
"""
    prompt = "robot> "

    def __init__(self, client: RobotClient):
        super().__init__()
        self.client = client
        self.valid_colors = ["red", "orange", "yellow", "green", "blue", "purple"]

    def do_pick(self, arg):
        """抓取方块: pick <color> <x> <y> <deg>"""
        args = arg.strip().split()
        if len(args) != 4:
            print("用法: pick <color> <x> <y> <deg>")
            print(f"  color: {', '.join(self.valid_colors)}")
            return

        color = args[0]
        try:
            x, y, deg = float(args[1]), float(args[2]), float(args[3])
        except ValueError:
            print("错误: 坐标必须为数字")
            return

        if color not in self.valid_colors:
            print(f"错误: 无效颜色, 可选: {', '.join(self.valid_colors)}")
            return

        response = self.client.pick(color, x, y, deg)
        self._print_response(response)

    def do_place(self, arg):
        """放置方块: place <block_color> <tray_color> <x> <y> <deg>"""
        args = arg.strip().split()
        if len(args) != 5:
            print("用法: place <block_color> <tray_color> <x> <y> <deg>")
            print(f"  color: {', '.join(self.valid_colors)}")
            return

        block_color, tray_color = args[0], args[1]
        try:
            x, y, deg = float(args[2]), float(args[3]), float(args[4])
        except ValueError:
            print("错误: 坐标必须为数字")
            return

        if block_color not in self.valid_colors:
            print(f"错误: 无效方块颜色, 可选: {', '.join(self.valid_colors)}")
            return

        if tray_color not in self.valid_colors:
            print(f"错误: 无效托盘颜色, 可选: {', '.join(self.valid_colors)}")
            return

        response = self.client.place(block_color, tray_color, x, y, deg)
        self._print_response(response)

    def do_test(self, arg):
        """测试连接"""
        print(f"测试连接到 {self.client.host}:{self.client.port}...")
        response = self.client.send_command({"cmd": "PICK", "color": "red", "x": 0, "y": 0, "deg": 0})
        if response.get("success"):
            print("  ✓ 连接成功")
        else:
            print(f"  ✗ 连接失败: {response.get('message', '未知错误')}")

    def do_status(self, arg):
        """显示当前配置"""
        print(f"主机地址: {self.client.host}")
        print(f"端口号: {self.client.port}")
        print(f"超时时间: {self.client.timeout}s")
        print(f"重试次数: {self.client.max_retries}")
        print(f"重试间隔: {self.client.retry_delay}s")
        print(f"有效颜色: {', '.join(self.valid_colors)}")

    def do_quit(self, arg):
        """退出"""
        self.client.close()
        print("退出机械臂控制终端")
        return True

    def do_exit(self, arg):
        """退出"""
        return self.do_quit(arg)

    def _print_response(self, response):
        success = response.get("success")
        message = response.get("message", "")
        request_id = response.get("request_id", "")[:8]

        if success:
            print(f"  ✓ 成功: {message} (ID: {request_id})")
        else:
            print(f"  ✗ 失败: {message} (ID: {request_id})")


def run_script(client: RobotClient, script_path: str):
    """执行脚本文件"""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sequence = json.load(f)
    except Exception as e:
        print(f"错误: 无法读取脚本文件: {e}")
        return

    if not isinstance(sequence, list):
        print("错误: 脚本必须是指令序列数组")
        return

    print(f"执行脚本: {script_path}")
    print(f"共 {len(sequence)} 条指令\n")

    success_count = 0
    for i, item in enumerate(sequence, 1):
        cmd_type = item.get("cmd", "").upper()
        print(f"--- 指令 {i}/{len(sequence)}: {cmd_type} ---")

        if cmd_type == "PICK":
            response = client.pick(
                item.get("color", ""),
                item.get("x", 0),
                item.get("y", 0),
                item.get("deg", 0)
            )
        elif cmd_type == "PLACE":
            response = client.place(
                item.get("block_color", ""),
                item.get("tray_color", ""),
                item.get("x", 0),
                item.get("y", 0),
                item.get("deg", 0)
            )
        elif cmd_type == "WAIT":
            seconds = item.get("seconds", 1.0)
            print(f"等待 {seconds} 秒...")
            time.sleep(seconds)
            response = {"success": True, "message": f"等待 {seconds}s 完成"}
        else:
            print(f"未知指令: {cmd_type}")
            continue

        if response.get("success"):
            success_count += 1
            print(f"  ✓ 成功")
        else:
            print(f"  ✗ 失败: {response.get('message', '')}")

        time.sleep(item.get("delay", 0.5))
        print()

    print(f"执行完成: {success_count}/{len(sequence)} 成功")


def main():
    parser = argparse.ArgumentParser(description="AUBO-i5 机械臂控制脚本")

    # 连接配置
    parser.add_argument("--host", type=str, default=DEFAULT_HOST,
                        help=f"机器人驱动主机地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"机器人驱动端口号 (默认: {DEFAULT_PORT})")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"通信超时时间 (默认: {DEFAULT_TIMEOUT}s)")
    parser.add_argument("--retry", type=int, default=DEFAULT_RETRY,
                        help=f"最大重试次数 (默认: {DEFAULT_RETRY})")

    # 命令行模式 - PICK
    parser.add_argument("--pick", type=str,
                        help="发送 PICK 指令, 指定方块颜色")
    parser.add_argument("--x", type=float, default=0.0,
                        help="X 坐标 (mm)")
    parser.add_argument("--y", type=float, default=0.0,
                        help="Y 坐标 (mm)")
    parser.add_argument("--deg", type=float, default=0.0,
                        help="旋转角度 (度)")

    # 命令行模式 - PLACE
    parser.add_argument("--place", type=str,
                        help="发送 PLACE 指令, 指定方块颜色")
    parser.add_argument("--tray", type=str,
                        help="托盘颜色 (与 --place 配合使用)")

    # 交互模式
    parser.add_argument("--interactive", action="store_true",
                        help="进入交互模式")

    # 脚本模式
    parser.add_argument("--script", type=str,
                        help="执行脚本文件")

    # 编译和启动选项
    parser.add_argument("--compile", action="store_true",
                        help="编译 C 驱动程序")
    parser.add_argument("--force-compile", action="store_true",
                        help="强制重新编译")
    parser.add_argument("--start", action="store_true",
                        help="启动 C 驱动程序")
    parser.add_argument("--auto", action="store_true",
                        help="自动编译并启动驱动，然后进入交互模式")

    args = parser.parse_args()

    driver_process = None

    if args.compile or args.force_compile:
        print("=" * 50)
        print("编译 C 驱动程序")
        print("=" * 50)
        if compile_driver(force=args.force_compile):
            print("编译完成")
        else:
            sys.exit(1)

    if args.start:
        print("\n" + "=" * 50)
        print("启动 C 驱动程序")
        print("=" * 50)
        driver_process = start_driver(port=args.port)
        if not driver_process:
            sys.exit(1)
        time.sleep(1)

    if args.auto:
        print("=" * 50)
        print("自动模式: 编译 + 启动 + 交互")
        print("=" * 50)

        print("\n[1/3] 编译驱动程序...")
        if not compile_driver():
            sys.exit(1)

        print("\n[2/3] 启动驱动程序...")
        driver_process = start_driver(port=args.port)
        if not driver_process:
            sys.exit(1)
        time.sleep(1)

        print("\n[3/3] 进入交互模式...\n")
        args.interactive = True

    client = RobotClient(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        max_retries=args.retry
    )

    try:
        if args.interactive:
            shell = RobotShell(client)
            shell.cmdloop()
        elif args.script:
            run_script(client, args.script)
        elif args.pick:
            response = client.pick(args.pick, args.x, args.y, args.deg)
            if response.get("success"):
                print(f"✓ PICK 成功: {response.get('message', '')}")
            else:
                print(f"✗ PICK 失败: {response.get('message', '')}")
                sys.exit(1)
        elif args.place:
            if not args.tray:
                print("错误: --place 需要配合 --tray 指定托盘颜色")
                sys.exit(1)
            response = client.place(args.place, args.tray, args.x, args.y, args.deg)
            if response.get("success"):
                print(f"✓ PLACE 成功: {response.get('message', '')}")
            else:
                print(f"✗ PLACE 失败: {response.get('message', '')}")
                sys.exit(1)
        else:
            parser.print_help()
    finally:
        client.close()
        if driver_process:
            print("\n清理: 停止驱动程序...")
            driver_process.terminate()
            driver_process.wait()
            print("驱动程序已停止")


if __name__ == "__main__":
    main()
