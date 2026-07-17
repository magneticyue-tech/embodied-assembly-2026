---
name: dependency-versions
description: 依赖版本约束 — Python 3.11 统一;numpy/opencv/pillow 及理由;旧代码 3.14 迁移注意
metadata:
  type: project
---

# 依赖版本约束

<!--A-->

## 语言运行时

- **Python 3.11**(全队统一)。选择理由:生态兼容性好(机器人 SDK、语音库、边缘平台常见支持上限);当前未发现需要更高版本的依赖。
- 注意:旧仓库 sim 代码开发环境为 Python 3.14(numpy 2.4.4 / opencv 4.13 / pillow 12)。迁移到 3.11 后**尚未运行验证**,首次运行需确认无 3.12+ 专有语法(初查未发现,以实际运行为准)。

## Python 包

| 包 | 版本约束 | 用途 |
|---|---|---|
| numpy | >=1.26,<3 | 数组运算 |
| opencv-python | >=4.9 | 视觉管线 |
| pillow | >=10 | 图像工具 |

以 `code/requirements.txt` 中的版本约束为准;新增依赖先在此登记,注明用途,再进 requirements。

## 环境搭建

```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r code/requirements.txt
```

## 其他工具链版本

- 机器人仿真:ARCS / AUBOPE(VMware 部署,版本以赛方发放为准)。
- AUBO SDK:当前仓库为 Python 接口层 + C 驱动占位桩;真实 C SDK 的版本与函数签名待设备联调后登记。「待确认」
- 大模型 API / 语音引擎:选型未定(见 schemes/正向设计方案.md §4-5),定型后在此登记版本。

相关: [[collaboration-protocol]], [[project-facts]]
