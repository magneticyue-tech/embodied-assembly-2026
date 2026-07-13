# 执行层 (Execution Layer)

## 概述

执行层负责控制 AUBO-i5 机械臂完成抓取和放置任务，是具身智能精密装配系统的核心执行单元。

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         执行层                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Python 层 (execution.py)                                      │
│   ├── SimRobot           # 仿真模式机器人控制器                   │
│   ├── AuboRobot          # 真机模式机器人控制器                   │
│   ├── RobotCommunicator  # UDP 通信协议模块                       │
│   ├── table_to_robot     # 坐标变换函数                          │
│   └── RingEvaluator      # 仿真评分器                            │
│                                                                 │
│   C 语言层 (robot_driver/)                                      │
│   └── robot_driver.c     # AUBO-i5 驱动占位桩                    │
│                                                                 │
│   通信协议: UDP + JSON                                           │
│   指令: PICK / PLACE                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 已实现功能

### 1. 坐标变换

- **`table_to_robot(x, y, deg, config)`**：台面坐标系 → 机器人基座坐标系
- **`robot_to_table(x, y, deg, config)`**：逆变换
- 支持平移、旋转、缩放变换
- 配置参数：`x_offset`、`y_offset`、`rotation_deg`、`scale`

### 2. 机器人控制器

#### SimRobot（仿真模式）
- `pick(color, target)`：模拟抓取动作，打印日志
- `place(block_color, tray_color, target)`：模拟放置动作，打印日志
- 不进行实际运动，用于验证逻辑正确性

#### AuboRobot（真机模式）
- `pick(color, target)`：坐标变换 → 发送 PICK 指令 → 接收响应
- `place(block_color, tray_color, target)`：坐标变换 → 发送 PLACE 指令 → 接收响应
- 通过 UDP 与 C 驱动进程通信
- 支持超时重试机制

### 3. 进程间通信

- **`RobotCommunicator`**：UDP 通信模块
- 协议格式：JSON
- 指令：`{"cmd": "PICK", "color": "...", "x": ..., "y": ..., "deg": ...}`
- 响应：`{"success": true/false, "message": "..."}`
- 特性：超时处理、自动重试（默认 3 次）

### 4. C 语言驱动

- **`robot_driver.c`**：AUBO-i5 驱动占位桩
- 监听 UDP 端口（默认 5000）
- 解析 PICK/PLACE 指令
- 打印执行日志
- 返回执行结果
- 支持命令行参数指定端口

### 5. 模式切换

| 模式 | 机器人实现 | 用途 |
|------|------------|------|
| `sim` | SimRobot | 仿真验证 |
| `real` | AuboRobot | 真机控制 |

### 6. 外部配置支持

#### 配置优先级
1. 命令行参数（最高）
2. `config.py` 配置文件
3. 默认值

#### 命令行参数
```bash
python main.py --mode real \
               --robot-host 192.168.1.100 \
               --robot-port 5000 \
               --x-offset 100.0 \
               --y-offset 50.0 \
               --rotation-deg 90.0 \
               --scale 1.0
```

#### 配置文件 (`config.py`)
```python
RUN_MODE = "sim"                    # 运行模式
ROBOT_HOST = "127.0.0.1"            # 机器人驱动主机
ROBOT_PORT = 5000                   # 机器人驱动端口
TRANSFORM_CONFIG = {                # 坐标变换配置
    "x_offset": 0.0,
    "y_offset": 0.0,
    "rotation_deg": 0.0,
    "scale": 1.0,
}
```

### 7. 评分模块

- **`RingEvaluator`**：仿真评分器
- `score_pick(color, det_block)`：计算抓取定位误差
- `score_place(tray_color, det_slot, pick_err)`：计算放置偏移和同心环落环
- 用于评估视觉定位精度

## 文件结构

```
code/execution/
├── execution.py          # Python 执行层主文件
├── robot_driver/         # C 语言驱动目录
│   └── robot_driver.c    # C 驱动代码（占位桩）
└── README.md             # 本文件
```

## 接口契约

执行层实现 `interfaces.RobotController` 协议：

```python
class RobotController(Protocol):
    def pick(self, color: Color, target: BlockPose) -> None:
        """抓取方块"""
        ...
    
    def place(self, block_color: Color, tray_color: Color, target: SlotPose) -> None:
        """放置方块到托盘"""
        ...
```

## 使用方式

### 编译 C 驱动
```bash
cd code/execution/robot_driver
gcc robot_driver.c -o robot_driver
```

### 运行 C 驱动
```bash
./robot_driver          # 默认端口 5000
./robot_driver -p 5001  # 指定端口
```

### 集成到主流程

主流程 `code/sim/main.py` 通过以下方式使用执行层：

```python
import execution

# 仿真模式
robot = execution.SimRobot(io)

# 真机模式
robot = execution.AuboRobot(io, host="192.168.1.100", port=5000)
```

## 待完成工作

1. **接入真实 AUBO SDK**：替换 C 驱动中的占位桩代码
2. **实际坐标标定**：在真机上标定坐标变换参数
3. **硬件联调测试**：完整流程测试


