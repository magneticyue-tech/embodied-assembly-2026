# 评审记录 — code/sim 视觉模块

<!--A-->

| 项 | 内容 |
|---|---|
| 对象 | code/sim/(重点 vision.py;含 scene/camera/cognition/interaction/annotate/main)及 code/execution/execution.py |
| 来源 | 旧仓库 精密装配/sim,2026-07-12 迁移,注释措辞重写,算法逻辑未改动 |
| 状态 | **待评审** |
| 提交人 | A(苏朗,视觉) |
| 建议评审人 | B 或 C(非提交人本人) |

## 评审待办

1. 算法正确性:HSV 阈值表、minAreaRect 角度折叠、板位姿 90° 歧义修正、板局部坐标变换及其逆变换。
2. "定位误差 <0.5mm" 声明复核:固定噪声种子,记录样本量与统计口径(均值/最大值),给出可复现实验。
3. Python 3.11 兼容性:在 3.11 venv 下运行 `python main.py`,确认退出码 0、产物齐全。
4. 接口契约:各实现类与 interfaces.py Protocol 的 isinstance 校验。
5. 边界行为:板检测失败(返回 None)分支、方块缺失分支是否按赛题规则安全停止并提示重抽/重启。

## 结论

(待评审人填写:通过 / 有条件通过(列出问题) / 不通过(列出原因))
