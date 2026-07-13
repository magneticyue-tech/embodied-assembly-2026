---
name: collaboration-protocol
description: 四人分工(A苏朗/B王培如/C王俊涵/D王乐)、签名规范<!--X-->、简洁描述要求、git 约定
metadata:
  type: project
---

# 协作协议

<!--A-->

## 分工(来源:materials/official/团队分工.txt)

| 角色 | 成员 | 职责 | 主要目录 |
|---|---|---|---|
| A | 苏朗 | 视觉感知与大模型环境搭建:图像采集、目标检测、坐标输出 | code/sim/vision.py, camera.py, 视觉标定 |
| B | 王培如 | 虚拟机械臂控制:点位标定、抓取放置、失败安全停止 | code/execution/execution.py, code/execution/robot_driver/, ARCS 仿真程序 |
| C | 王俊涵 | 认知 Agent 与交互界面:语音交互、任务解析、业务调度 | code/sim/cognition.py, interaction.py, main.py |
| D | 王乐 | 基础平台后端:通信中转、流媒体、日志存储 | 通信/日志基础设施, interfaces.py 契约维护 |

## 签名规范

- 提交的文档与代码,贡献者在文件头部(或所改章节处)加注释签名,格式统一为 `<!--A-->` `<!--B-->` `<!--C-->` `<!--D-->`(HTML 注释,Markdown 渲染时不显示)。
- Python 文件用 `# <!--A-->`(置于 docstring 之后一行)。
- 多人合作的文件依贡献顺序并列:`<!--A--><!--C-->`。

## 工作描述要求

- 一切工作描述(提交信息、评审记录、进度说明)保持简洁:一句话说明改了什么,必要时一句话说明为何。
- 措辞遵循 [[writing-standards]]。

## Git 约定

- 远程仓库:`magneticyue-tech/embodied-assembly-2026`(公开)。协作者:Wpr-htyj、HEBE-JZH、sl3456,各自用自己的 GitHub 账号。
- **分支布局**:`main` = 新仓库(系统实现,2026-07-12 起);`ppt-phase` = 旧 PPT 答辩阶段历史(原 `master`,只读归档,不再提交);两条历史无共同祖先,不做合并。
- 日常循环:开工前 `git pull` → 改动 → `git add` → `git commit -m "说明"` → `git push`。仅在 `main` 上工作。
- **禁止** `git pull ppt-phase` 或将 `ppt-phase` 合并进 `main`(无共同祖先,合并会把旧目录结构灌回来)。查旧文件用 `git show ppt-phase:路径`。
- 首次克隆/换机后设置 `git config pull.rebase true`(避免四人并行时产生无意义 merge commit)。
- 分工到不同文件,减少冲突;二进制文件(PPT/图片/PDF)git 无法合并,改前先协调。
- 未通过评审的代码不得作为已验证成果引用(评审状态见 reviews/)。

相关: [[writing-standards]], [[dependency-versions]]
