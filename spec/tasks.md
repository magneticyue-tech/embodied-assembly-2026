# 具身智能精密装配赛 - 执行层实现计划

## [ ] Task 1: 坐标变换模块实现
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 实现坐标变换函数：台面坐标系 → 机器人基座坐标系
  - 支持平移、旋转、缩放变换
  - 提供配置接口，支持从配置文件读取变换参数
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic` TR-1.1: 坐标变换函数能正确处理平移、旋转、缩放
  - `programmatic` TR-1.2: 变换结果与手动计算一致（使用已知变换矩阵）
- **Notes**: 变换矩阵参数后续需实际标定，当前提供默认值

## [ ] Task 2: Python 端 AuboRobot 类实现
- **Priority**: high
- **Depends On**: Task 1, Task 3
- **Description**: 
  - 在 execution.py 中实现 AuboRobot 类，实现 interfaces.RobotController 协议
  - 封装与 C 进程的通信逻辑
  - 实现 pick() 和 place() 方法
- **Acceptance Criteria Addressed**: AC-1, AC-5
- **Test Requirements**:
  - `programmatic` TR-2.1: AuboRobot 类正确实现 interfaces.RobotController 协议
  - `programmatic` TR-2.2: pick()/place() 方法能正确发送指令并接收结果
  - `human-judgment` TR-2.3: 代码结构清晰，符合项目编码规范
- **Notes**: 保持与 SimRobot 相同的接口，便于 main.py 切换

## [ ] Task 3: 进程间通信协议实现
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 定义 Python ↔ C 通信协议格式
  - 实现 UDP/TCP 通信封装
  - 实现指令序列化/反序列化
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 通信模块能正确发送和接收 PICK/PLACE 指令
  - `programmatic` TR-3.2: 指令序列化/反序列化正确无误
  - `programmatic` TR-3.3: 网络异常时能正确处理并返回错误
- **Notes**: 使用 JSON 格式序列化指令，便于调试

## [ ] Task 4: C 语言机器人驱动实现（占位桩）
- **Priority**: high
- **Depends On**: Task 3
- **Description**: 
  - 创建 C 语言驱动层目录结构
  - 实现网络通信接收逻辑
  - 实现 pick/place 占位桩函数（打印日志，返回成功）
  - 实现吸盘控制占位桩
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-4.1: C 代码编译通过生成可执行文件
  - `programmatic` TR-4.2: C 进程能正确接收指令并返回结果
  - `human-judgment` TR-4.3: C 代码结构清晰，便于后续替换为真实 SDK
- **Notes**: 当前为占位桩实现，后续需替换为真实 AUBO SDK 调用

## [ ] Task 5: 模式切换配置实现
- **Priority**: medium
- **Depends On**: Task 2
- **Description**: 
  - 在 config.py 中添加模式配置项（sim/real）
  - 修改 main.py 支持根据配置自动切换机器人实现
  - 实现模式切换逻辑
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `human-judgment` TR-5.1: 修改 config.py 的 mode 配置后，main.py 能正确切换模式
  - `human-judgment` TR-5.2: 切换过程无需修改其他代码
- **Notes**: 最小化对 main.py 的修改

## [ ] Task 6: 错误处理与日志完善
- **Priority**: medium
- **Depends On**: Task 2, Task 4
- **Description**: 
  - 实现统一的错误处理机制
  - 完善日志记录（执行状态、错误信息、坐标数据）
  - 实现执行失败时的重试逻辑
- **Acceptance Criteria Addressed**: NFR-3, NFR-4
- **Test Requirements**:
  - `human-judgment` TR-6.1: 执行失败时能返回明确的错误信息
  - `human-judgment` TR-6.2: 日志记录完整，包含时间戳和关键数据
- **Notes**: 重试逻辑可配置最大重试次数

## [ ] Task 7: 集成测试验证
- **Priority**: high
- **Depends On**: Task 1-6
- **Description**: 
  - 运行完整仿真流程验证新代码
  - 验证 Python ↔ C 通信正常
  - 验证坐标变换正确
  - 验证模式切换功能
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-4, AC-5
- **Test Requirements**:
  - `programmatic` TR-7.1: python main.py 能正常运行完成两个任务
  - `programmatic` TR-7.2: 输出日志包含完整的执行记录
  - `human-judgment` TR-7.3: 整体流程符合预期
- **Notes**: 测试使用仿真模式，验证接口正确性
