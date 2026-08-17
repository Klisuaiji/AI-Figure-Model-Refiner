# AI 手办模型精修器
## Autonomous Blender Plugin Development Specification

你现在负责开发一个**可交付级 Blender 插件**：

> **AI 手办模型精修器（AI Figure Model Refinement & FDM Production Tool）**

目标是将 AI 生成的、不完美的 3D 手办模型，通过**AI 辅助 + 几何算法 + 用户确认**，自动处理为能够进入 FDM 3D 打印生产流程的模型。

这不是一次性的代码生成任务，而是一个**持续研究、开发、测试、调试、对比、迭代的完整软件工程项目**。

你必须把自己视为这个项目的：

- 软件架构师
- Blender 插件开发者
- 3D 几何算法工程师
- 3D 打印工程师
- AI/Computer Vision 工程师
- 测试工程师

项目最终要求达到**可以实际安装、运行、测试、交付**的状态，而不是只生成演示代码。

---

# 一、最高优先级原则

整个项目遵循以下原则：

### 1. 先验证，再实现

在修改代码、安装依赖、下载模型、选择第三方仓库之前，必须先检查实际环境。

禁止假设以下内容已经存在：

- Blender API
- ONNX 模型
- GitHub 仓库
- Geometry Nodes 节点组
- 3MF API
- Python 第三方库
- 测试模型
- 模板模型

如果某项能力不存在：

1. 明确记录；
2. 搜索可用替代方案；
3. 评估集成成本；
4. 再选择实现方案；
5. 在 `报告.md` 中记录决定。

**禁止伪造 API、仓库、模型、测试结果或运行结果。**

---

# 二、项目目标

最终实现：

```text
AI 生成的 3D 手办
        ↓
模型预处理
        ↓
参考图分析
        ↓
部件语义识别
        ↓
用户确认
        ↓
头发精修
        ↓
人体比例校准
        ↓
衣体分离
        ↓
布料修复
        ↓
FDM 可打印性修复
        ↓
基座计算
        ↓
最终验证
        ↓
5 个独立生产部件
        ↓
after.3mf
```

最终输出必须能够进入主流切片软件进行正常切片。

目标软件包括：

- Bambu Studio
- OrcaSlicer
- PrusaSlicer
- Cura

---

# 三、开发环境

## Blender

目标版本：

> Blender 5.2 LTS

用户 Blender 安装位置：

```text
D:\blender\
```

注意：

**不要假设 Blender 5.2 的 API 与其他 Blender 版本完全一致。**

开发开始前必须实际检查：

```text
Blender version
Python version
bpy API
3MF API
Geometry Nodes API
Sculpt API
Mesh/BMesh API
```

如果发现实际版本与需求存在差异：

> 以实际环境为准，并记录在 `报告.md`。

---

# 四、工作区

开发工作区为当前工作目录。

Blender 测试环境：

```text
D:\blender\
```

要求：

- 插件代码在当前开发工作区维护；
- 插件安装/测试必须使用 `D:\blender\`；
- 不允许把整个项目直接开发在 Blender 安装目录；
- 只有测试安装时才将 addon 部署到 Blender；
- 保留开发源代码与 Blender 安装目录之间的清晰关系。

推荐结构：

```text
project/
├── addon/
├── engine/
├── models/
├── assets/
├── tests/
├── dataset/
├── scripts/
├── docs/
├── reports/
├── output/
├── README.md
├── CHANGELOG.md
└── 报告.md
```

实际结构可以根据研究结果调整。

---

# 五、真实测试数据

项目可能提供：

```text
训练集/
├── before.fbx
├── after.fbx
├── front.png
├── back.png
├── left.png
└── right.png
```

其中：

### before.fbx

代表：

> AI 生成的原始手办模型。

### after.fbx

代表：

> 人工/目标流程处理后的参考结果。

它不是简单的“答案文件”，而是本项目的：

> **Golden Reference / Ground Truth**

必须尽可能利用它进行：

- 几何差异分析；
- 部件差异分析；
- 修复效果评价；
- 参数调优；
- 回归测试。

如果这些文件实际不存在，必须报告，而不是假装已经使用。

---

# 六、第一阶段必须执行：技术可行性审计

**不要直接开始写完整插件。**

首先执行：

## Technical Feasibility Audit

检查：

### A. 环境

- Blender 版本
- Python 版本
- GPU
- CUDA / DirectML 等可用情况
- CPU
- RAM
- 磁盘空间

### B. 输入数据

检查：

- before.fbx
- after.fbx
- 参考图片
- 模型三角面数量
- 对象数量
- 材质
- UV
- 法线
- 非流形情况
- 是否存在多个 disconnected components

### C. 参考开源项目

搜索并检查：

- MeshRepairFor3DPrinting
- Blender 3D Print Toolbox
- Blender3mfFormat
- maintained 3MF Blender addon
- BlenderGBHTool
- HairArranger
- MeshRepair
- CharMorph
- MPFB
- 其他与本项目相关的项目

对每个项目记录：

```text
Repository
URL
License
Last Update
Blender Compatibility
Python Compatibility
Useful Components
Can Reuse Directly?
Need Modification?
Integration Risk
```

**特别注意 License。**

如果许可证不允许直接集成，不得复制其代码。

可以参考算法，但必须遵守许可证。

---

# 七、架构原则

不要把插件设计成一个巨大 Python 文件。

必须采用模块化结构。

推荐：

```text
AI Figure Refinement
│
├── UI Layer
│
├── Session Layer
│
├── Task Pipeline
│
├── Vision Layer
│
├── Semantic Layer
│
├── Geometry Layer
│
├── Hair Layer
│
├── Fabric Layer
│
├── Print Validation Layer
│
├── Base Generator
│
└── Export Layer
```

---

# 八、核心数据模型

必须建立独立的项目数据结构。

例如：

```text
RepairSession
│
├── ModelInput
├── ReferenceImages
├── SemanticParts
├── RepairTasks
├── ValidationResults
├── PrintSettings
├── ExportSettings
└── History
```

每个部件至少包含：

```text
Part
├── id
├── name
├── semantic_type
├── confidence
├── source
├── object_reference
├── vertex_group
├── material
├── thickness
├── print_priority
├── parent
└── repair_status
```

不要把这些信息完全依赖 Geometry Nodes。

Geometry Nodes 可以作为执行/可视化层，但：

> **Python 数据模型才是插件的 Source of Truth。**

---

# 九、任务系统

每一个处理步骤必须是独立 Task。

推荐：

```text
RepairTask
├── prepare()
├── execute()
├── validate()
├── preview()
├── commit()
└── rollback()
```

必须支持：

- Accept
- Reject
- Skip
- Retry
- Undo
- Rollback
- Manual Override

禁止把所有步骤写成一个不可中断函数。

---

# 十、处理流程

---

## STEP 0 — 模型预处理与部件语义识别

### 自动处理

1. Duplicate Vertex 清理
2. Zero Area Face 清理
3. Normal 修复
4. Non-manifold 检测
5. Hole 检测
6. Disconnected Component 分析
7. Wall Thickness 分析
8. Mesh Statistics

然后进行参考图分析。

参考图：

```text
Front     必选
Back      可选
Left      可选
Right     可选
```

---

## STEP 0.1 — Reference Analysis

不要假设参考图与模型坐标系已经对齐。

建立：

```text
Reference Camera
```

并分析：

- 相机方向
- 模型方向
- 角色中心
- Bounding Box
- silhouette
- semantic mask

---

## STEP 0.2 — 2D → 3D Semantic Mapping

核心目标：

```text
2D Reference
      ↓
Segmentation
      ↓
Camera Projection
      ↓
Ray Casting
      ↓
3D Candidate Faces
      ↓
Multi-view Voting
      ↓
Semantic Probability Field
```

例如：

```text
hair:
front = 0.95
left  = 0.81
right = 0.88
back  = 0.73

final = hair
```

不能仅根据单张图片决定 3D 部件。

---

## STEP 0.3 — 部件语义

第一版至少支持：

```text
hair
head
body
fabric
base
```

未来允许扩展：

```text
skin
face
inner_clothing
outer_clothing
sleeve
accessory
armor
shoe
weapon
etc.
```

---

# 十一、AI 模型策略

不要假设：

```text
figure_seg.onnx
```

已经存在。

如果不存在：

### V1

采用：

```text
SAM / segmentation
+
geometry heuristics
+
reference projection
+
user brush correction
```

先建立完整工作流。

### V2

再加入：

```text
figure_seg.onnx
```

自定义模型。

### V3

通过真实用户修正数据训练专用模型。

---

# 十二、AI 推理要求

AI 推理必须：

- 本地执行；
- 不上传用户模型；
- 支持 CPU；
- GPU 可选；
- 不阻塞 Blender UI；
- 支持进度反馈；
- 支持取消；
- 支持失败回退。

推荐：

```text
AI Worker
     ↓
Result
     ↓
Blender Main Thread
```

禁止长时间推理直接阻塞 UI。

---

# 十三、用户确认点

必须存在六个主要确认节点。

---

## Confirm #1 — Semantic Parts

3D View：

- 彩色语义叠加
- 半透明显示
- 当前区域高亮

工具：

- Add Brush
- Remove Brush
- Erase
- Flood
- Accept
- Redo
- Manual Mode

---

## STEP 1 — Hair

第一版本重点不是“重新创造头发”，而是：

> **优先修复原始 AI 头发。**

处理：

- 断裂
- 悬浮
- 穿插
- 薄壁
- 非流形
- 发梢过薄
- 发束连接
- 表面平滑
- FDM 加厚

只有在原始头发无法修复时，才进入：

```text
Hair Reconstruction
```

---

## Hair Reconstruction

可研究：

- Blender Curves
- Geometry Nodes
- BlenderGBHTool
- HairArranger
- Hair Guide 系统

推荐：

```text
Reference
 ↓
Hair Mask
 ↓
Hair Flow
 ↓
Guide Curves
 ↓
Procedural Strands
 ↓
Thickness
 ↓
Mesh
```

不要尝试从图片直接生成每一根头发。

---

# 十四、STEP 2 — Head / Body / Leg 比例

引入标准人体模板。

可以研究：

- CharMorph
- MPFB
- 其他兼容 Blender 的人体模板

模板只是：

> **比例参考**

不能强行替换原始模型。

推荐：

```text
Template
 ↓
Rigid Alignment
 ↓
Scale
 ↓
Orientation
 ↓
Surface Comparison
 ↓
Optional Projection
```

用户可以：

- 切换模板；
- 调整比例；
- 使用局部 Brush；
- 接受/拒绝。

---

# 十五、STEP 3 — Body / Fabric Separation

目标：

```text
Body
Fabric
Accessories
```

自动推断：

```text
semantic probability
+
surface curvature
+
distance field
+
reference mask
+
material
+
geometry
```

形成：

```text
Clothing Probability Field
```

再生成：

```text
Clothing Boundary
```

最后：

```text
Separate
 ↓
Solidify
 ↓
Repair
 ↓
Bevel
 ↓
Validate
```

禁止假设 Boolean 本身能够完成衣体识别。

Boolean 只是后续几何操作。

---

# 十六、STEP 4 — Fabric Repair

检测：

- Broken Boundary
- Floating Pieces
- Intersections
- Non-manifold
- Thin Walls
- Sharp Fragile Edges
- Disconnected Components

默认壁厚：

```text
Outer Coat       1.2 mm
Normal Clothing  1.0 mm
Thin Fabric      0.8 mm
Hard Decoration  1.5 mm
```

这些参数必须可配置。

不要把它们硬编码。

---

# 十七、FDM Wall Thickness

默认：

```text
Nozzle = 0.4mm
Layer Height = 0.2mm
Material = PLA
```

但必须允许用户修改。

默认最低目标：

```text
0.8 mm
```

检测结果：

```text
< minimum
    → warning/error

>= minimum
    → pass
```

必须支持：

- Heatmap
- Min thickness
- Average thickness
- Distribution
- Problem region selection

---

# 十八、STEP 5 — Base

自动分析：

- Bounding Box
- Center of Mass
- Convex Hull
- Bottom Contact Area
- Stability

默认：

```text
Diameter = Model Width × 1.2
Height = 3–5mm
```

但这只是默认值。

最终必须验证：

```text
Center of Mass Projection
        ↓
Base Support Polygon
```

如果重心超出支撑区域：

```text
UNSTABLE
```

自动扩大基座。

支持：

```text
Round
Square
Custom
```

---

# 十九、STEP 6 — Production Validation

最终必须进行完整验证：

### Geometry

```text
Watertight
Manifold
No Zero Area
No Duplicate
Correct Normals
```

### Printing

```text
Wall Thickness
Overhang
Floating Geometry
Support Requirement
Fragile Features
```

### Stability

```text
Center of Mass
Base Contact
15° Tilt Test
```

---

# 二十、3MF 输出

最终：

```text
after.3mf
```

至少包含：

```text
hair
head
body
fabric
base
```

作为独立 Build Items。

但是：

**不要假设 Blender 原生 3MF API 已经能够满足全部需求。**

先验证实际 API。

如果不足：

```text
Blender Objects
       ↓
Intermediate Build Representation
       ↓
3MF Export Adapter
       ↓
after.3mf
```

可以研究：

- Blender3mfFormat
- maintained Blender 3MF addons
- lib3mf
- 3MF Core Specification

必须遵守相应许可证。

---

# 二十一、3MF 输出必须测试

生成后至少测试：

```text
Bambu Studio
OrcaSlicer
PrusaSlicer
Cura
```

验证：

- 能否打开；
- 是否保持部件独立；
- 坐标是否正确；
- 法线是否正确；
- 单位是否正确；
- 是否能够切片。

---

# 二十二、打印报告

生成：

```text
print_report.json
print_report.html
```

至少包含：

```text
Total Volume
Part Volume
Estimated Weight
Minimum Wall Thickness
Average Wall Thickness
Non-manifold Count
Overhang Area
Support Recommendation
Center of Mass
Base Stability
```

PLA 默认密度可以作为参数：

```text
1.24 g/cm³
```

不能硬编码为不可修改值。

---

# 二十三、UI

主界面：

```text
┌─────────────────────────────────────────────┐
│ AI FIGURE REFINER                           │
├─────────────────────────────────────────────┤
│ [Import Model] [Reference Images] [Process] │
├─────────────────────────────────────────────┤
│ Front* │ Back │ Left │ Right                │
├─────────────────────────────────────────────┤
│ Step 0 / 6                                  │
│ ████████████░░░░░░                         │
├─────────────────────────────────────────────┤
│                                             │
│             3D VIEW        │   TOOL PANEL  │
│                            │               │
│                            │   Parameters  │
│                            │               │
│                            │   Preview     │
│                            │               │
├─────────────────────────────────────────────┤
│ LOG                                         │
│ INFO / WARNING / ERROR                      │
├─────────────────────────────────────────────┤
│ [Back] [Skip] [Accept] [Next]              │
└─────────────────────────────────────────────┘
```

原则：

> 3D View 约 60%，工具面板约 40%。

---

# 二十四、错误处理

任何自动操作都必须允许失败。

例如：

```text
AI segmentation failed
```

不能直接崩溃。

必须：

```text
AI failed
 ↓
Show reason
 ↓
Fallback
 ↓
Manual Mode
```

同样：

```text
Boolean failed
Hair reconstruction failed
3MF export failed
ONNX unavailable
```

都必须存在 fallback。

---

# 二十五、日志系统

必须记录：

```text
INFO
WARNING
ERROR
DEBUG
```

例如：

```text
[INFO] Loaded model
[INFO] 842,312 triangles
[WARNING] 17 thin-wall regions detected
[INFO] Reference segmentation completed
[INFO] Hair confidence: 0.87
[WARNING] Clothing boundary uncertain
[INFO] Switched to manual correction
```

---

# 二十六、报告文件

项目根目录必须持续维护：

```text
报告.md
```

每个开发阶段都更新。

至少包含：

```text
# 当前阶段

## 已完成

## 正在开发

## 技术决策

## 使用的开源项目

## License

## 已知问题

## 测试结果

## 性能

## 下一阶段

## 风险
```

禁止只在项目结束时生成报告。

---

# 二十七、测试体系

建立：

```text
tests/
├── unit/
├── integration/
├── geometry/
├── printing/
└── regression/
```

至少测试：

### Unit

- mesh statistics
- thickness
- bounding box
- center of mass
- semantic mapping

### Integration

```text
FBX
 ↓
Repair
 ↓
Validation
 ↓
3MF
```

### Regression

每次修改后：

```text
before.fbx
 ↓
Plugin
 ↓
generated_after
 ↓
Compare with after.fbx
```

---

# 二十八、Golden Dataset

如果存在多个案例，建立：

```text
dataset/
├── case_001/
├── case_002/
├── case_003/
└── ...
```

每个案例：

```text
before
after
references
expected_parts
```

生成自动评价：

```text
Hausdorff Distance
Volume Error
Wall Thickness Compliance
Manifoldness
Part Separation Accuracy
Silhouette Similarity
```

---

# 二十九、验收指标

第一阶段不要强行要求所有 AI 功能达到最终指标。

分阶段验收。

## V0.1

必须：

- 插件可安装；
- UI 可启动；
- 模型可导入；
- 基础 Mesh 检测可运行；
- 报告生成；
- 日志正常。

## V0.2

必须：

- 参考图系统；
- 五大部件识别；
- 用户画笔修正；
- Confirm #1。

## V0.3

必须：

- Hair 修复；
- Head/Body 比例；
- Confirm #2/#3。

## V0.4

必须：

- Clothing separation；
- Fabric repair；
- Confirm #4/#5。

## V0.5

必须：

- Base；
- Print validation；
- Confirm #6。

## V0.6

必须：

- 3MF；
- Slicer validation；
- Print report。

## V1.0

目标：

```text
before.fbx
 ↓
完整工作流
 ↓
after.3mf
```

---

# 三十、最终质量目标

目标而非第一阶段硬性要求：

### Geometry

```text
Watertight = 100%
Non-manifold = 0
```

### Thickness

```text
>= 0.8mm
```

### Fabric Separation

目标：

```text
> 90%
```

边界误差目标：

```text
< 2mm
```

### Repair

目标：

```text
> 90%
```

### Volume

目标：

```text
< 5% error
```

### Stability

目标：

```text
15° tilt stable
```

### Hair

不要只使用“拓扑相似度”。

综合评价：

```text
Silhouette
Hair Coverage
Hair Flow
Volume
Visual Similarity
Printability
```

---

# 三十一、第三方开源代码使用原则

任何 GitHub 项目必须先检查：

```text
License
Copyright
Dependencies
Compatibility
```

禁止：

- 未确认 License 就复制代码；
- 删除作者版权；
- 隐藏第三方依赖；
- 将 GPL 项目代码直接塞进不兼容的闭源组件；
- 声称原创第三方算法。

报告中记录：

```text
Project
License
Usage
Modified?
Files
Attribution Required?
```

---

# 三十二、性能目标

最终目标：

```text
Step 0 basic geometry scan
< 30 seconds
```

但：

> 不允许为了满足 30 秒而牺牲正确性。

AI 推理可以异步。

大型模型必须支持：

- progress
- cancel
- cache
- incremental processing

---

# 三十三、缓存系统

AI 推理结果必须允许缓存。

例如：

```text
cache/
├── segmentation/
├── depth/
├── projection/
└── semantic/
```

如果参考图和模型没有改变：

> 不应该重复执行昂贵推理。

---

# 三十四、版本管理

采用：

```text
Semantic Versioning
```

例如：

```text
0.1.0
0.2.0
0.5.0
1.0.0
```

每个版本更新：

```text
CHANGELOG.md
```

---

# 三十五、GitHub

最终必须建立 GitHub repository。

仓库必须包含：

```text
README.md
LICENSE
CHANGELOG.md
报告.md
.gitignore
docs/
tests/
addon/
engine/
```

README 至少包含：

- 项目介绍
- 安装
- Blender 版本
- 使用方法
- AI 模型安装
- FDM 参数
- 已知限制
- 开源依赖
- License

---

# 三十六、Git 提交策略

不要最后一次提交所有代码。

按照阶段提交：

```text
init: project architecture
feat: addon bootstrap
feat: mesh diagnostics
feat: reference image system
feat: semantic segmentation
feat: hair repair
feat: clothing separation
feat: fabric repair
feat: print validation
feat: base generator
feat: 3mf exporter
test: regression dataset
docs: installation guide
```

提交必须有意义。

---

# 三十七、开发纪律

每完成一个阶段：

1. 运行代码；
2. 测试；
3. 修复错误；
4. 更新 `报告.md`；
5. Git commit；
6. 再进入下一阶段。

禁止：

> 写完整个项目后才第一次运行。

---

# 三十八、禁止行为

严禁：

### 1.

假装调用了不存在的 API。

### 2.

假装成功运行代码。

### 3.

假装读取了用户没有提供的文件。

### 4.

假装测试通过。

### 5.

用 placeholder 冒充完整功能。

### 6.

为了满足验收数字而修改测试结果。

### 7.

没有运行 Blender 就声称插件可以工作。

### 8.

没有实际生成 3MF 就声称 3MF 合规。

### 9.

没有实际测试 slicer 就声称可以切片。

---

# 三十九、遇到困难时的处理原则

如果某个功能暂时无法实现：

不要停在这里。

按照：

```text
Problem
 ↓
Research
 ↓
Alternative
 ↓
Fallback
 ↓
Implement
 ↓
Document limitation
```

例如：

```text
ONNX Runtime 无法安装
        ↓
尝试 CPU wheel
        ↓
失败
        ↓
使用 subprocess 独立 Python runtime
        ↓
仍失败
        ↓
Fallback 到非 AI segmentation
```

最终必须保持整个工作流可运行。

---

# 四十、重要：不要过早追求“AI 全自动”

项目核心原则：

> **可靠的半自动工具 > 不可靠的全自动工具。**

如果 AI 无法可靠判断：

```text
让用户确认。
```

如果 AI 无法可靠分离：

```text
提供 Brush。
```

如果 AI 无法重建头发：

```text
保留原头发并修复。
```

---

# 四十一、最终产品形态

最终用户体验应该类似：

```text
① 导入 AI 手办

② 上传 Front / Back / Left / Right

③ 点击 Analyze

④ AI 识别部件

⑤ 用户确认

⑥ AI 修复 Hair

⑦ 用户确认

⑧ AI 校准 Body

⑨ 用户确认

⑩ AI 分离 Fabric

⑪ 用户确认

⑫ AI 修复打印问题

⑬ 用户确认

⑭ 自动生成 Base

⑮ 最终 Print Validation

⑯ Export after.3mf
```

最终：

```text
after.3mf
```

可以直接进入 3D 打印工作流。

---

# 四十二、你的第一项任务

**现在不要直接开发完整插件。**

第一阶段只做：

# Technical Feasibility Audit

必须：

1. 检查当前开发环境；
2. 检查 Blender；
3. 检查工作区；
4. 查找训练集；
5. 检查 before.fbx；
6. 检查 after.fbx；
7. 检查参考图片；
8. 分析 before / after 几何差异；
9. 搜索并检查相关开源项目；
10. 检查许可证；
11. 验证 Blender 5.2 API；
12. 验证 3MF 导出能力；
13. 验证 Python 依赖；
14. 给出技术风险矩阵；
15. 提出 V0.1 架构；
16. 创建/更新 `报告.md`。

**完成上述审计之前，不要开始实现完整业务功能。**

---

# 四十三、第一次报告必须回答的问题

`报告.md` 至少回答：

```text
1. 当前 Blender 版本是什么？

2. Python 版本是什么？

3. before.fbx 是否存在？

4. after.fbx 是否存在？

5. 模型三角面数量是多少？

6. before / after 有哪些几何差异？

7. 参考图片是否存在？

8. 哪些开源项目可以复用？

9. 每个项目是什么 License？

10. 哪些代码可以直接使用？

11. 哪些功能必须自己实现？

12. Blender 5.2 是否支持目标 3MF 工作流？

13. ONNX Runtime 是否可用？

14. SAM 是否可用？

15. 当前最大技术风险是什么？

16. V0.1 应该实现什么？

17. 哪些功能应该推迟到 V0.2/V0.3？

18. 预计的模块架构是什么？
```

---

# 四十四、最终交付物

最终必须交付：

```text
1. Blender Addon ZIP

2. Source Code

3. AI Model Assets / Model Downloader

4. Blender Template Assets

5. README

6. Installation Guide

7. User Manual

8. Troubleshooting Guide

9. 报告.md

10. CHANGELOG.md

11. Tests

12. Golden Dataset Evaluation

13. after.3mf

14. Print Report

15. GitHub Repository
```

---

# 四十五、最终验收

最终不要只回答：

> “开发完成。”

必须实际展示：

```text
before.fbx
       ↓
Plugin
       ↓
Step 0
       ↓
Confirm
       ↓
Hair
       ↓
Confirm
       ↓
Body
       ↓
Confirm
       ↓
Fabric
       ↓
Confirm
       ↓
Base
       ↓
Validation
       ↓
after.3mf
```

并提供：

```text
测试日志
几何统计
打印验证
3MF 验证
性能数据
已知问题
```

如果某项没有完成，必须明确标记：

```text
NOT IMPLEMENTED
```

而不是将 placeholder 或 mock 结果描述为完成。

---

# 项目核心理念

最终请始终记住：

> **这个项目不是为了生成一个“看起来能工作的 Blender 插件 Demo”。**

目标是建立一个真正能够处理：

```text
AI Generated Figure
        ↓
Semantic Understanding
        ↓
Geometry Repair
        ↓
Human Verification
        ↓
FDM Validation
        ↓
Production-ready 3D Model
```

的生产工具。

**可靠性、可验证性、可维护性优先于功能数量。**

**先做能运行的 V0.1，再逐步加入 AI 自动化能力。**