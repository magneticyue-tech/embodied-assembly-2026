# CLAUDE.md — 项目上下文

## 项目

2026 中国大学生机械工程创新创意大赛 · 具身智能精密装配赛。方案论证已完成,当前阶段:系统实现。
赛题、评分细则、硬件参数见 `memory/project-facts.md`;原始文件在 `materials/official/`。

## 目录结构

```
memory/      规范与事实:写作规范、协作协议、依赖版本、项目事实(入口 MEMORY.md)
code/        实现代码;sim/ 为全流程软件仿真(未通过人工评审,见 reviews/)
schemes/     设计方案:正向设计方案.md、数据流程-手绘.png、数据流程图.pptx
materials/   official/ 官方文件 | aubo/ 赛方 PDF | reference/ 旧答辩文稿(仅参考)
reviews/     评审记录;未通过评审的代码不得作为已验证成果引用
```

## 约定

- 写作:遵循 `memory/writing-standards.md`(禁绝对化、事实与判断分离、性能结论要数据)。
- 协作:A 苏朗(视觉)/ B 王培如(机械臂)/ C 王俊涵(认知与交互)/ D 王乐(平台后端);签名 `<!--A-->` 等,详见 `memory/collaboration-protocol.md`。
- 环境:Python 3.11 + `code/requirements.txt`,详见 `memory/dependency-versions.md`。
- 远程仓库:`magneticyue-tech/embodied-assembly-2026`(私有);开工前 pull,二进制文件改前协调。

## 运行仿真

```bash
cd code/sim && python main.py
```
