---
name: sim-prototype
description: Working software simulation of the contest pipeline at E:\ClaudeCode\精密装配\sim
metadata: 
  node_type: memory
  type: project
  originSessionId: 9531c960-8bfb-4579-8654-b5e8e613047c
---

在 E:\ClaudeCode\精密装配\sim\ 构建了视觉模块，辅以全流程mock。`cd sim && python main.py` 
vision.py 做 BGR→HSV分割→形态学→轮廓→minAreaRect(旋转鲁棒,正方形90°折叠)→单应反投影到台面mm。定位误差<0.5mm(预算5mm)。

**托盘建模:** 托盘是**一整块刚性矩形板**,板上6个同心环色槽按固定布局共享板位姿(不是每色独立旋转轴)。遮挡问题(方块放上盖住槽色、与同色方块混淆)的解法: 颜色→槽位**开局一次性标定**(固定不变); 板位姿**每步靠板外轮廓大矩形重测**(永不被小方块遮挡,中途裁判挪板也跟得上); 装配时槽位=板位姿⊕标定布局,不靠重识别颜色。自由方块每步闭环再感知,落在板范围内的彩色块被排除。scene.perturb()每步挪动自由方块+整块板。注意: detect_board_pose 用已知板W/H匹配修正minAreaRect的90°角度歧义,否则绘制框会转90°。

环境实况: Python 3.14, 已装 numpy2.4.4/opencv4.13/pillow12。Windows 控制台 cp1252 打印中文需 sys.stdout.reconfigure(encoding=utf-8)。


模块对应正向设计方案各章节,详见 sim/README.md。相关: [[contest-task-summary]]。

**接口层重构 (2026-07-04):** 新增 `sim/interfaces.py` —— 用 Protocol(@runtime_checkable)+TypedDict 定义四层契约(VisionModule/CognitionModule/RobotController/CameraSource/InteractionModule)。各模块改为显式实现类: OpenCVVision / RuleBasedCognition / SimRobot / SimCamera / ConsoleInteraction, main.py 改为依赖注入(只依赖抽象, 不依赖具体实现)。**关键**: 执行层拆分 —— `SimRobot`(interfaces.RobotController)只负责运动、绝不接触 ground-truth; 放置评分移到仿真专属 `RingEvaluator`(非 Protocol, 用 scene 真值算落环)。真机换 ClaudeVLM/AUBORobot 实现同契约即可无缝替换, 主流程不变。行为与重构前等价(相机噪声无种子, 环数有±1环抖动)。
