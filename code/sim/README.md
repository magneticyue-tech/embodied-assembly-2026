# sim — 赛题全流程软件仿真

<!--A-->

状态: **未通过人工评审**(评审待办见 `../../reviews/sim-vision-review.md`)。
迁移自旧仓库 `精密装配/sim`,迁移时仅重写了注释措辞,算法逻辑未改动。

## 模块

| 文件 | 内容 |
|---|---|
| `config.py` | 坐标系约定 + 硬件参数(AUBO-i5、同心环托盘) |
| `interfaces.py` | 四层架构接口契约(Protocol + TypedDict) |
| `scene.py` `camera.py` | 仿真台面与相机采集(旋转方块 + 同心环托盘) |
| `vision.py` | 视觉:HSV 分割 → minAreaRect → 单应反投影(实现 VisionModule) |
| `cognition.py` | 认知层规则桩(后续替换为真实 VLM 调用) |
| `execution.py` | 执行层动作桩 + 仿真专属 RingEvaluator 评分 |
| `interaction.py` | 交互层控制台桩(带时间戳日志落盘) |
| `annotate.py` | 可视化标注(识别框/坐标/当前步骤高亮) |
| `main.py` | 双任务状态机,依赖注入各模块 |

## 算法要点

- 方块识别:BGR→HSV 分割 → 形态学 → 轮廓 → minAreaRect(中心+角度)→ 单应反投影到台面 mm。
- 旋转处理:minAreaRect 取朝向;正方形 90° 对称,角度折叠到 [-45°,45°)。
- 托盘为一整块刚性板,6 色槽布局相对板体固定:
  - 颜色→槽位映射:开局无遮挡时一次性标定,之后固定。
  - 板位姿:每步由板外轮廓矩形重新检测(外轮廓不被 30mm 方块遮挡)。
  - 目标槽位置 = 板位姿 ⊕ 标定布局,不重新识别颜色。
  - `detect_board_pose` 用已知板宽高比修正 minAreaRect 的 90° 角度歧义。
- `scene.perturb()`:每步装配前模拟裁判挪动自由方块与整块托盘板。

## 仿真边界

- 视觉为 OpenCV 实算;认知为规则桩;执行无物理动力学;交互为控制台桩。
- 时间戳为固定基准的仿真时钟,非真实时间。
- 置信度为桩的固定值,非真实模型输出。
- 放置偏移只包含视觉定位误差,未包含机械臂误差与标定误差。
- 相机噪声无固定种子,环数读数存在 ±1 环抖动。

## 运行

```bash
cd code/sim
python main.py
```

依赖版本见 `../../memory/dependency-versions.md`(Python 3.11;旧仓库开发环境为
Python 3.14,迁移后尚未在 3.11 下运行验证)。

产物(output/,已被 .gitignore 忽略):

| 文件 | 内容 |
|---|---|
| `00_initial_scene.png` | 初始场景:自由方块 + 托盘板外轮廓框 + 6 色槽标定 |
| `task1_scene.png` | 任务一:方块旋转框+坐标、托盘板外轮廓、各色槽标注 |
| `task2_step{1-6}_*.png` | 任务二每步:板位姿重检测、当前步骤高亮 |
| `parse_log_*.txt` | 带时间戳全流程日志(赛题要求),含每步放置偏移与落环数 |
