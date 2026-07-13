# 具身智能精密装配赛 - 执行层验证清单

<!--A-->

## 代码结构检查

* [x] 执行层代码模块化存放，目录结构清晰

* [ ] Python 静态检查零错误（待在 Python 3.11 环境运行 ruff/mypy）

* [x] C 代码结构清晰，便于后续替换为真实 SDK

## 接口实现检查

* [x] AuboRobot 类正确实现 interfaces.RobotController 协议

* [x] pick() 方法签名正确（color: Color, target: BlockPose）

* [x] place() 方法签名正确（block\_color: Color, tray\_color: Color, target: SlotPose）

* [x] 保持与 SimRobot 相同的接口契约

## 坐标变换检查

* [x] 坐标变换模块能正确处理平移、旋转、缩放

* [x] 变换结果与手动计算一致

* [x] 支持配置变换参数

## 进程间通信检查

* [x] Python 端能正确发送 PICK/PLACE 指令

* [x] C 端能正确接收并解析指令（GCC 16.1 严格编译 + UDP 集成测试）

* [x] 通信异常时能正确处理并返回错误

* [x] 指令序列化/反序列化正确

## C 语言驱动检查

* [x] C 代码编译通过生成可执行文件（w64devkit GCC 16.1，`-Wall -Wextra -Werror`）

* [x] pick/place 占位桩函数能正确响应

* [x] 吸盘控制占位桩实现

* [x] 日志记录完整

## 模式切换检查

* [x] 配置文件支持 sim/real 模式切换

* [x] main.py 能根据配置选择机器人实现，并在真机前置条件未满足时阻止启动

* [ ] 真实相机链路与坐标标定完成后无需修改其他代码（待真机联调）

## 集成测试检查

* [x] python main.py 能正常运行完成两个任务（代码审查验证）

* [x] 输出日志包含完整的执行记录

* [x] 坐标数据正确传递和变换

* [x] 视觉缺失、坐标配置错误与机械臂失败均有明确终止路径

* [x] 仿真模式与真机模式接口一致

## 自动化验证记录（2026-07-13）

* [x] `python -m compileall -q code`

* [x] `python -m unittest discover -s code/tests -v`：Python 测试通过

* [x] `python code/sim/main.py --mode sim`：退出码 0

* [x] `robot_driver_test.c`：GCC 16.1 编译并执行通过

* [x] Python↔C UDP 集成：重复 `request_id` 返回同一响应且 PICK 仅执行一次

* [ ] Python 3.11 干净环境验证

## 文档检查

* [x] PRD 文档完整（spec.md）

* [x] 实现计划完整（tasks.md）

* [x] 验证清单完整（checklist.md）

