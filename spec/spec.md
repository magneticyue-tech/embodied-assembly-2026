# 具身智能精密装配赛 - 执行层代码实现 PRD

## Overview
- **Summary**: 实现执行层的机器人控制代码，包含 Python 接口层和 C 语言机器人驱动层，通过进程间通信实现仿真与真机的无缝切换。
- **Purpose**: 将当前仅打印日志的仿真机器人替换为可实际控制 AUBO-i5 机械臂的执行层代码，实现真实的抓取/放置功能。
- **Target Users**: 团队成员（B 王培如）及后续集成测试人员。

## Goals
- 实现完整的机器人控制接口（pick/place）
- 支持 C 语言 AUBO SDK 调用
- 保持与现有 interfaces.RobotController 契约兼容
- 支持仿真/真机模式切换
- 实现坐标变换（台面坐标系 → 机器人基座坐标系）
- 实现吸盘控制逻辑

## Non-Goals (Out of Scope)
- 物理动力学仿真（仍使用现有 scene.py）
- 视觉标定（属于感知层职责）
- 认知层逻辑修改
- 交互层修改
- 主流程修改（main.py）
- 硬件部署与调试

## Background & Context
- 当前执行层仅实现了 SimRobot（打印日志），无实际运动控制
- AUBO-i5 SDK 支持 C/C++/Python
- 项目采用四层架构，接口契约已定义在 interfaces.py 中
- 坐标系约定：台面坐标系（mm），图像坐标系（像素），机器人基座坐标系

## Functional Requirements
- **FR-1**: 实现 RobotController 接口的 Python 封装层
- **FR-2**: 实现 C 语言 AUBO 机器人驱动（包含占位桩实现）
- **FR-3**: 实现进程间通信协议（Python ↔ C）
- **FR-4**: 实现坐标变换模块（台面坐标 → 机器人坐标）
- **FR-5**: 实现吸盘控制逻辑
- **FR-6**: 支持仿真/真机模式配置切换

## Non-Functional Requirements
- **NFR-1**: 接口调用响应时间 < 100ms（不含运动时间）
- **NFR-2**: 代码模块化，便于后续替换为真实 SDK
- **NFR-3**: 错误处理完善，返回明确的错误信息
- **NFR-4**: 日志记录完整，便于调试

## Constraints
- **Technical**: Python 3.x, C 语言标准库
- **Dependencies**: AUBO C SDK（需后续实际集成）
- **Architecture**: 必须实现 interfaces.RobotController 协议

## Assumptions
- AUBO C SDK 接口已知（moveJ, moveL, setIO 等）
- 坐标变换参数通过配置文件提供
- 通信协议基于 UDP/TCP

## Acceptance Criteria

### AC-1: Python RobotController 接口实现
- **Given**: main.py 注入 AuboRobot 实例
- **When**: 调用 pick() 和 place() 方法
- **Then**: 方法正确调用底层 C 进程并返回执行结果
- **Verification**: `programmatic`

### AC-2: C 语言驱动层编译通过
- **Given**: C 语言驱动代码完整
- **When**: 使用 gcc 编译
- **Then**: 编译成功生成可执行文件
- **Verification**: `programmatic`

### AC-3: 进程间通信正常
- **Given**: Python 和 C 进程都在运行
- **When**: Python 发送 PICK/PLACE 指令
- **Then**: C 进程正确接收并执行指令，返回结果
- **Verification**: `programmatic`

### AC-4: 坐标变换正确
- **Given**: 提供台面坐标和变换参数
- **When**: 调用坐标变换函数
- **Then**: 返回正确的机器人基座坐标
- **Verification**: `programmatic`

### AC-5: 仿真模式与真机模式切换
- **Given**: 配置文件设置不同模式
- **When**: 运行 main.py
- **Then**: 根据配置自动切换使用 SimRobot 或 AuboRobot
- **Verification**: `human-judgment`

## Open Questions
- [ ] AUBO C SDK 的具体函数签名（需查阅官方文档）
- [ ] 坐标变换矩阵的具体参数（需实际标定）
- [ ] 通信协议的具体端口号（需确认）
