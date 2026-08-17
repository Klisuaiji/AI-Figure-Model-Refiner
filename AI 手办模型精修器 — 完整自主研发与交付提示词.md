# AI 手办模型精修器
## AI Figure Model Refinement & FDM Production Pipeline

---

# 0. 你的身份与任务

你现在不是在回答一个普通的编程问题。

你负责参与一个**长期、持续迭代、最终需要实际交付的 Blender 插件项目**。

项目名称：

> **AI 手办模型精修器**

英文：

> **AI Figure Model Refiner**

项目目标：

> 将 AI 生成的 3D 手办模型，通过 AI 视觉理解、几何处理、用户确认和 FDM 打印验证，逐步修复为可以进入实际 3D 打印生产流程的模型。

最终目标不是：

> 做一个 Demo。

而是：

> **做成一个可以安装、运行、处理真实 AI 手办模型、生成可打印文件、具有完整 UI、错误处理、日志、文档和版本管理的 Blender 插件。**

---

# 1. 核心产品理念

整个产品采用：

> **AI 自动处理 80% + 用户在关键节点进行确认和微调**

而不是追求完全无人干预。

核心原则：

```text
AI 负责理解
        ↓
算法负责修复
        ↓
用户负责确认
        ↓
几何系统负责验证
        ↓
3D 打印系统负责输出
```

如果 AI 无法可靠判断：

> 必须允许用户接管。

如果自动算法失败：

> 必须存在 fallback。

如果某项高级 AI 能力尚未成熟：

> 不允许用假功能冒充完成，应提供可用的基础算法或人工模式。

---

# 2. 最终产品工作流

完整产品规划如下：

```text
用户选择 AI 生成的 3D 手办
              ↓
上传参考图片
              ↓
模型预处理
              ↓
部件语义识别
              ↓
用户确认 #1
              ↓
Hair 头发精修
              ↓
用户确认 #2
              ↓
Head / Body / Leg 比例校准
              ↓
用户确认 #3
              ↓
Body / Fabric 衣体分离
              ↓
用户确认 #4
              ↓
Fabric 布料修复与打印加厚
              ↓
用户确认 #5
              ↓
Base 基座计算
              ↓
用户确认 #6
              ↓
最终打印验证
              ↓
分部件导出
              ↓
after.3mf
```

---

# 3. 当前开发阶段的重要限制

## 当前没有训练集

当前项目**暂时没有准备完整的 Ground Truth / Training Dataset**。

因此：

### 当前阶段禁止依赖：

- before / after 成对数据；
- Ground Truth 自动评价；
- 自动训练 figure_seg；
- before → after 差异学习；
- 基于 after 模型的参数拟合；
- 基于训练集的性能宣称。

不要假设存在：

```text
before.fbx
after.fbx
```

也不要假设存在已经准备好的：

```text
figure_seg.onnx
```

---

## 未来数据集

未来可能加入：

```text
before
after
front
back
left
right
```

用于：

- 模型训练；
- 算法调优；
- Regression Test；
- Ground Truth Evaluation；
- AI 模型性能评估。

**当前版本只需要在架构上为未来数据集预留接口。**

不要因为当前没有训练集而阻塞基础插件开发。

---

# 4. 当前开发优先级

开发必须按照以下优先级：

## P0 — 基础插件框架

必须首先稳定：

- Blender Addon
- UI
- Session
- Step Pipeline
- Logging
- Settings
- Undo / Rollback
- Error Handling

---

## P1 — 几何处理

优先实现不依赖 AI 的可靠能力：

- Mesh Cleanup
- Non-manifold Detection
- Hole Detection
- Duplicate Vertex
- Zero Area Face
- Normal Repair
- Connected Components
- Bounding Box
- Volume
- Wall Thickness
- Overhang
- Print Validation

---

## P2 — 参考图系统

实现：

- Front / Back / Left / Right
- 图片加载
- 图片管理
- 相机映射
- Reference Camera
- Silhouette
- 2D → 3D Projection

---

## P3 — 部件语义

第一阶段可以采用：

```text
Reference Image
+
Segmentation
+
Geometry Heuristics
+
User Brush
```

实现：

```text
hair
head
body
fabric
base
```

---

## P4 — AI

再逐渐加入：

- SAM
- Depth Anything
- figure_seg
- ONNX Runtime
- 未来自定义模型

---

## P5 — 高级自动修复

包括：

- Hair Reconstruction
- Clothing Separation
- Body Template Projection
- Fabric Repair
- Automatic Base

---

## P6 — 生产输出

包括：

- Print Validation
- 3MF
- Print Report
- Slicer Compatibility

---

# 5. Blender 环境

目标：

> Blender 5.2 LTS

测试 Blender：

```text
D:\blender\
```

开发代码：

> 当前工作区

不要直接把项目源码放进 Blender 安装目录。

推荐：

```text
project/
├── addon/
├── core/
├── vision/
├── geometry/
├── hair/
├── fabric/
├── printing/
├── export/
├── assets/
├── models/
├── tests/
├── docs/
├── scripts/
├── output/
├── README.md
├── CHANGELOG.md
└── 报告.md
```

可以根据实际开发情况调整。

---

# 6. 开发前必须做环境调查

不要直接开始写完整功能。

第一步必须调查：

### Blender

- 实际 Blender 版本；
- Python 版本；
- bpy API；
- BMesh API；
- Geometry Nodes API；
- Sculpt API；
- Curve API；
- 3MF API；
- Addon API。

### 系统

- CPU；
- GPU；
- RAM；
- CUDA；
- DirectML；
- 可用磁盘。

### Python

检查：

```text
numpy
Pillow
opencv
onnxruntime
trimesh
open3d
```

是否可用。

---

# 7. 不允许假设 API 存在

例如：

```python
bpy.ops.export_scene.threemf
```

不能因为需求里写了，就直接认为它存在。

必须实际检查。

如果不存在：

1. 搜索官方 API；
2. 搜索 Blender 社区；
3. 搜索 GitHub；
4. 检查开源 3MF addon；
5. 决定使用：
   - Blender 原生；
   - 第三方 addon；
   - lib3mf；
   - 自己实现 3MF Adapter。

并在：

```text
报告.md
```

中说明。

---

# 8. 开源项目研究

项目允许并鼓励研究和复用成熟开源项目。

重点研究方向：

### Mesh Repair

- MeshRepairFor3DPrinting
- MeshRepair
- Blender 3D Print Toolbox

### 3MF

- Blender3mfFormat
- maintained Blender 3MF addons
- lib3mf

### Hair

- BlenderGBHTool
- HairArranger
- Hair Guides
- Blender Curves / Geometry Nodes Hair

### Human Template

- CharMorph
- MPFB / MPFB2
- VRoid related tools

### AI / Vision

- SAM
- Depth Anything
- ONNX Runtime
- Blender AI integration projects

---

# 9. 第三方代码 License

任何 GitHub 项目在使用前必须检查：

```text
Repository
License
Copyright
Dependencies
Blender Version
Python Version
```

记录：

```text
项目
License
用途
直接使用 / 参考 / 改写
修改内容
是否需要 Attribution
```

禁止：

> 没有检查 License 就直接复制代码。

---

# 10. 软件架构

不要制作一个巨型：

```text
__init__.py
```

所有功能都塞进去。

建议：

```text
AI Figure Refiner
│
├── UI
│
├── Core
│   ├── Session
│   ├── Task
│   ├── State
│   └── History
│
├── Vision
│   ├── Reference
│   ├── Segmentation
│   ├── Depth
│   └── Projection
│
├── Semantic
│   ├── Part
│   ├── Hair
│   ├── Head
│   ├── Body
│   ├── Fabric
│   └── Base
│
├── Geometry
│   ├── Cleanup
│   ├── Repair
│   ├── Thickness
│   ├── Boolean
│   ├── Remesh
│   └── Separation
│
├── Printing
│   ├── Validation
│   ├── Support
│   ├── Stability
│   └── Material
│
├── Export
│   ├── 3MF
│   └── Report
│
└── AI Runtime
    ├── ONNX
    ├── Models
    ├── Cache
    └── Worker
```

---

# 11. Core Data Model

建立统一的：

```text
RepairSession
```

负责记录整个处理过程。

至少包括：

```text
session_id
source_model
reference_images
current_step
parts
settings
tasks
validation
export
history
```

---

# 12. Part Semantic Model

不要只简单存储：

```text
hair = object
```

应建立语义数据。

例如：

```text
Part
├── id
├── name
├── type
├── confidence
├── object
├── faces
├── vertices
├── material
├── thickness
├── print_priority
├── parent
├── children
├── source
└── status
```

未来允许扩展为：

```text
Character
│
├── Head
│   ├── Hair
│   ├── Face
│   └── Accessories
│
├── Body
│   ├── Skin
│   ├── Inner Clothing
│   ├── Outer Clothing
│   └── Decorations
│
└── Base
```

---

# 13. Task System

每个处理步骤必须是独立 Task。

统一接口：

```text
prepare()
execute()
validate()
preview()
commit()
rollback()
```

支持：

- Accept
- Reject
- Skip
- Retry
- Undo
- Rollback
- Manual

---

# 14. STEP 0 — 模型预处理

用户首先在 Blender 中：

> 框选需要处理的 AI 手办模型。

支持：

- FBX
- OBJ
- GLB / GLTF
- Blender 原生对象

检查：

### Geometry

- Non-manifold
- Duplicate vertices
- Zero-area faces
- Broken normals
- Degenerate geometry
- Holes
- Disconnected components
- Intersections
- Floating geometry

### Printing

- Minimum wall thickness
- Overhang
- Fragile geometry

---

# 15. STEP 0 — 参考图

四格上传栏：

```text
┌────────┬────────┬────────┬────────┐
│ FRONT* │ BACK   │ LEFT   │ RIGHT  │
└────────┴────────┴────────┴────────┘
```

规则：

- Front 必选；
- Back 可选；
- Left 可选；
- Right 可选；
- 提供越多视图，语义映射精度越高。

必须允许：

- 替换图片；
- 删除图片；
- 重新分析；
- 调整图片对应方向。

---

# 16. STEP 0 — 参考图与模型对齐

这是本项目的重要技术模块。

不要假设参考图和模型坐标系已经一致。

需要建立：

```text
Reference Camera
```

进行：

```text
Image
 ↓
Silhouette
 ↓
Camera Alignment
 ↓
Projection
 ↓
3D Ray Casting
```

允许用户调整：

- Rotation
- Translation
- Scale
- Camera Angle

---

# 17. STEP 0 — Semantic Segmentation

目标识别：

```text
hair
head
body
fabric
base
```

第一版不强制依赖自定义 ONNX 模型。

可以：

```text
SAM
+
Reference Projection
+
Geometry
+
User Brush
```

以后加入：

```text
figure_seg.onnx
```

---

# 18. Multi-view Semantic Mapping

如果拥有：

```text
Front
Back
Left
Right
```

则对 3D 面进行多视角投票。

概念：

```text
Front   → Hair 0.92
Back    → Hair 0.87
Left    → Hair 0.91
Right   → Hair 0.88
             ↓
        Final Hair
```

每个面/顶点可以保存：

```text
semantic_type
confidence
```

---

# 19. 用户确认点 #1

3D View：

- 五种区域不同颜色；
- 半透明；
- 高亮当前区域；
- 可显示线框。

工具：

- Add
- Remove
- Smooth
- Flood
- Grow
- Shrink
- Undo

用户可以：

### Accept

进入下一步。

### Manual

完全手动修正。

### Recalculate

重新运行 AI。

---

# 20. STEP 1 — Hair

这是本项目的重要模块。

优先目标：

> **修复原 AI 头发，而不是无条件重建头发。**

检测：

- 头发与头部穿插；
- 悬浮发片；
- 断裂；
- 非流形；
- 过薄；
- 发梢过薄；
- 不连贯；
- 薄壁。

---

# 21. Hair Reconstruction

只有当原模型头发无法合理修复时，再进入重建。

技术路线：

```text
Reference Image
 ↓
Hair Mask
 ↓
3D Hair Region
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
 ↓
Print Validation
```

研究：

- Blender Curves
- Geometry Nodes
- BlenderGBHTool
- HairArranger

---

# 22. Hair 参数

UI：

```text
Density
Length
Curl
Noise
Taper
Thickness
```

实时预览：

> Curve

最终：

> Curve → Mesh

要求：

- 有厚度；
- 水密；
- 可打印。

---

# 23. Hair Fallback

如果 Hair Reconstruction 失败：

```text
保留原头发
 ↓
Cleanup
 ↓
Repair
 ↓
Solidify
 ↓
Print Validation
```

绝对不能因为 AI 重建失败导致整个流程终止。

---

# 24. 用户确认点 #2

提供：

- 原始头发；
- 修复预览；
- 重建预览；
- 参数；
- Mesh Preview；
- Curve Preview。

按钮：

```text
Accept
Keep Original
Regenerate
Manual
Back
```

---

# 25. STEP 2 — Head / Body / Leg

引入标准人体模板。

可研究：

- CharMorph
- MPFB
- 其他开源人体模板。

模板用途：

> 比例校准，而不是替换原角色。

处理：

```text
Template
 ↓
Bounding Box
 ↓
PCA Orientation
 ↓
Rigid Alignment
 ↓
Scale
 ↓
Surface Comparison
```

---

# 26. 模板模式

提供：

```text
Q Style
Normal
Realistic
```

模板半透明覆盖。

允许：

> Scene Projection / Sculpt Brush

局部调整。

---

# 27. 用户确认点 #3

用户可以：

- 切换模板；
- 调整比例；
- 局部刷；
- 恢复；
- 接受；
- 跳过。

---

# 28. STEP 3 — Body / Fabric Separation

AI 手办中可能出现：

```text
Body + Clothing
```

完全融合。

因此不能假设：

> 一个 Boolean 就可以分离衣服。

应该采用：

```text
Semantic Mask
+
Reference Mask
+
Curvature
+
Surface Distance
+
Material
+
Geometry
```

生成：

```text
Clothing Probability Field
```

然后：

```text
Boundary
 ↓
Separate
 ↓
Solidify
 ↓
Repair
```

---

# 29. 衣物分类

未来支持：

```text
skin
inner_clothing
outer_fabric
sleeve
lace
armor
decoration
```

内部数据可以保存：

```text
region
type
thickness
priority
```

例如：

```text
region = sleeve_left
type = outer_fabric
thickness = 1.2
priority = 2
```

---

# 30. 用户确认点 #4

提供：

- 身体半透明；
- 衣物半透明；
- 分离预览；
- Brush Add；
- Brush Remove；
- Solidify Thickness。

---

# 31. STEP 4 — Fabric

检测：

### 拓扑

- Broken edges
- Non-manifold
- Floating pieces
- Disconnected components

### 几何

- Self intersection
- Thin walls
- Sharp edges
- Small isolated geometry

### 布料

- 穿插
- 破损
- 悬浮
- 不连续

---

# 32. Fabric Repair

根据区域使用不同厚度。

默认：

```text
Outer Coat       1.2mm
Normal Clothing  1.0mm
Thin Fabric      0.8mm
Hard Decoration  1.5mm
```

必须允许用户修改。

---

# 33. Printability

默认：

```text
Nozzle = 0.4mm
Layer Height = 0.2mm
Material = PLA
```

最低壁厚：

```text
0.8mm
```

但全部参数必须可以修改。

---

# 34. 壁厚分析

必须支持：

```text
Minimum
Maximum
Average
Distribution
Heatmap
Problem Region
```

颜色只是视觉表现，底层数据必须真实保存。

---

# 35. Overhang

默认：

```text
>45°
```

标记潜在支撑区域。

允许用户修改阈值。

---

# 36. 用户确认点 #5

显示：

```text
Damage List
Thin Wall List
Overhang List
Intersection List
```

每个问题：

```text
Accept Repair
Reject Repair
Ignore
Manual
```

---

# 37. STEP 5 — Base

自动分析：

```text
Bounding Box
Convex Hull
Bottom Surface
Center of Mass
```

默认：

```text
Diameter = widest width × 1.2
Height = 3–5mm
```

---

# 38. Base Stability

计算：

```text
Center of Mass Projection
```

必须落在：

```text
Base Support Polygon
```

否则：

> unstable

倾斜测试：

```text
15°
```

如果不稳定：

> 自动增加基座面积。

---

# 39. Base 类型

提供：

```text
Round
Square
Custom / Character Theme
```

选项：

```text
Anti-slip
Name Plate
Pattern
```

---

# 40. 用户确认点 #6

显示：

- 基座预览；
- 重心；
- 稳定性；
- 直径；
- 高度。

状态：

```text
GREEN  Stable
YELLOW Marginal
RED    Unstable
```

---

# 41. STEP 6 — Final Validation

最终检查：

### Mesh

```text
Watertight
Manifold
Normals
Duplicate
Zero Area
```

### Printing

```text
Wall Thickness
Overhang
Floating Geometry
Support Requirement
Fragile Features
```

### Assembly

检查五个部件是否：

```text
hair
head
body
fabric
base
```

正确存在。

---

# 42. 最终部件

最终允许：

```text
hair
head
body
fabric
base
```

作为独立对象。

但不要强制每个角色一定只能有五个对象。

内部允许：

```text
hair_front
hair_back
fabric_left
fabric_right
```

等子部件。

导出时可以根据用户设置：

> 合并 / 保持独立。

---

# 43. 3MF

最终目标：

```text
after.3mf
```

要求：

- 多 Build Items；
- 单位正确；
- 坐标正确；
- Mesh 正确；
- 部件独立；
- 元数据。

研究：

- Blender3mfFormat；
- 现代 Blender 3MF addon；
- lib3mf；
- 3MF Core Specification。

---

# 44. Slicer 验证

最终必须实际测试：

- Bambu Studio；
- OrcaSlicer；
- PrusaSlicer；
- Cura。

验证：

```text
Open
Parse
Slice
Part Separation
Scale
Orientation
```

如果无法实际安装某软件：

> 必须明确记录，而不是声称测试成功。

---

# 45. Print Report

生成：

```text
print_report.json
print_report.html
```

包含：

```text
Total Volume
Part Volume
PLA Weight
Minimum Wall Thickness
Average Wall Thickness
Thin Wall Area
Overhang Area
Support Recommendation
Center of Mass
Base Stability
```

---

# 46. UI

主面板：

```text
┌─────────────────────────────────────────────┐
│ AI FIGURE REFINER                           │
├─────────────────────────────────────────────┤
│ [Import Model] [References] [Analyze]       │
├─────────────────────────────────────────────┤
│ Front* │ Back │ Left │ Right                │
├─────────────────────────────────────────────┤
│ Step 0 / 6                                  │
│ █████████████░░░░░                          │
├─────────────────────────────────────────────┤
│                                             │
│                 3D VIEW                     │
│                                             │
│                                             │
│                            TOOL PANEL       │
│                            Parameters        │
│                            Actions           │
├─────────────────────────────────────────────┤
│ LOG                                         │
├─────────────────────────────────────────────┤
│ [Back] [Skip] [Accept] [Next]              │
└─────────────────────────────────────────────┘
```

目标：

> 3D View 60%  
> Tool Panel 40%

---

# 47. UI 交互原则

所有 AI 操作都必须提供：

```text
Preview
```

不要：

```text
点击按钮
↓
直接修改原模型
```

而应该：

```text
Original
 ↓
Temporary Result
 ↓
Preview
 ↓
Accept
 ↓
Commit
```

这样用户可以随时拒绝 AI 结果。

---

# 48. Undo / Rollback

每个 Stage 必须建立：

```text
Snapshot
```

例如：

```text
Step 1
 ↓
Snapshot A

Step 2
 ↓
Snapshot B
```

用户可以：

> 回到上一阶段。

---

# 49. AI Runtime

推荐：

```text
ONNX Runtime
```

依赖：

```text
numpy
opencv
Pillow
onnxruntime
```

但：

> 不要假设这些包可以直接 pip install 到 Blender Python。

必须实际检查 Blender Python 环境。

---

# 50. AI 模型下载

模型不要直接塞进 addon。

推荐：

```text
addon/
models/
```

首次使用：

```text
Check Model
 ↓
Missing
 ↓
Download
 ↓
Verify Hash
 ↓
Load
```

必须支持：

- 下载失败；
- 文件损坏；
- 版本不匹配；
- 用户手动指定模型。

---

# 51. 本地 AI

原则：

> 默认本地运行。

用户模型和参考图：

> 不上传第三方服务器。

---

# 52. AI 推理必须异步

不要阻塞 Blender UI。

流程：

```text
Blender Main Thread
        │
        ▼
AI Worker
        │
        ▼
Inference
        │
        ▼
Result
        │
        ▼
Blender Main Thread
```

UI 必须显示：

```text
Progress
Cancel
Status
```

---

# 53. Cache

AI 结果必须支持缓存：

```text
cache/
├── segmentation/
├── depth/
├── semantic/
└── projection/
```

相同输入：

> 尽量避免重复推理。

---

# 54. Geometry 技术栈

优先使用：

### BMesh

处理：

- topology；
- edges；
- faces；
- normals；
- manifold。

### Open3D

处理：

- point cloud；
- voxel；
- distance；
- surface analysis。

### Trimesh

处理：

- mesh analysis；
- volume；
- bounds；
- ray；
- watertight。

### Geometry Nodes

用于：

- procedural geometry；
- preview；
- curve；
- hair；
- visual effects。

不要让 Geometry Nodes 成为整个插件的数据存储核心。

---

# 55. Geometry Nodes Bundle

如果需要：

> 可以使用 Geometry Nodes attributes / bundles 传递部件标签。

但是：

> Python semantic data 必须作为 Source of Truth。

---

# 56. 日志

支持：

```text
INFO
WARNING
ERROR
DEBUG
```

例如：

```text
[INFO] Model imported
[INFO] 842,312 triangles
[WARNING] 31 thin wall regions
[INFO] Front reference loaded
[INFO] Semantic analysis completed
[WARNING] Hair confidence 0.61
```

---

# 57. 报告.md

项目根目录持续维护：

```text
报告.md
```

不是开发结束后才生成。

每次重大修改都更新。

必须记录：

```text
当前阶段
已完成
进行中
技术决策
开源项目
License
依赖
测试
性能
Bug
已知限制
下一阶段
```

---

# 58. 开发阶段

建议：

## Phase 0

环境调查 + 架构

## Phase 1

Addon Framework

## Phase 2

Mesh Diagnostics / Repair

## Phase 3

Reference Image System

## Phase 4

Semantic Part System

## Phase 5

Hair Repair

## Phase 6

Body Template

## Phase 7

Clothing Separation

## Phase 8

Fabric Repair

## Phase 9

Base Generator

## Phase 10

Print Validation

## Phase 11

3MF Export

## Phase 12

AI Automation

## Phase 13

Packaging / Documentation

---

# 59. 第一阶段实际任务

**现在不要直接开发全部功能。**

第一步执行：

# Technical Feasibility Audit

检查：

1. Blender；
2. Python；
3. 当前工作区；
4. 可用文件；
5. 现有代码；
6. 可用开源项目；
7. License；
8. 3MF；
9. ONNX；
10. Geometry Nodes；
11. BMesh；
12. Open3D；
13. Trimesh；
14. Blender API。

然后建立：

```text
报告.md
```

---

# 60. 第一份报告必须包含

```text
# AI 手办模型精修器开发报告

## 1. 环境

## 2. Blender API 调查

## 3. Python 依赖调查

## 4. 3MF 调查

## 5. Mesh Repair 调查

## 6. Hair 技术调查

## 7. Reference Image 技术调查

## 8. Semantic Segmentation 技术调查

## 9. 开源项目调查

## 10. License 调查

## 11. 技术风险

## 12. 架构建议

## 13. V0.1 开发范围

## 14. 暂不实现功能

## 15. 下一步
```

---

# 61. 当前阶段明确暂不要求

以下内容现在可以规划，但不能作为 V0.1 阻塞项：

```text
自定义 figure_seg.onnx
大规模训练集
Ground Truth 自动评价
before / after 自动差异学习
自动训练
高精度 AI Hair Reconstruction
完全自动衣物语义识别
完全自动人体模板匹配
```

这些属于后续阶段。

---

# 62. 当前版本必须优先保证

即使没有 AI 模型，也应该可以运行：

```text
Import Model
 ↓
Geometry Analysis
 ↓
Reference Images
 ↓
Manual Semantic Selection
 ↓
Hair Repair
 ↓
Body / Fabric Tools
 ↓
Thickness
 ↓
Print Validation
 ↓
Base
 ↓
3MF
```

也就是说：

> **AI 是增强层，不应该成为插件无法运行的单点故障。**

---

# 63. Fallback 原则

任何 AI 模块都必须存在：

```text
AI
 ↓
Failure?
 ↓
Manual / Heuristic
```

例如：

```text
SAM unavailable
→ Manual Mask

ONNX unavailable
→ Geometry Heuristic

Hair AI failed
→ Original Hair Repair

Clothing AI failed
→ Brush Selection

3MF API unavailable
→ Alternative Export Adapter
```

---

# 64. 最终交付物

最终交付：

```text
AI_Figure_Refiner.zip
```

以及：

```text
Source Code
README.md
Installation Guide
User Manual
Troubleshooting
报告.md
CHANGELOG.md
Tests
Model Downloader
Template Assets
Print Report
after.3mf
GitHub Repository
```

---

# 65. GitHub

最终提交完整源码。

必须包含：

```text
README.md
LICENSE
CHANGELOG.md
.gitignore
addon/
core/
vision/
geometry/
hair/
fabric/
printing/
export/
docs/
tests/
```

采用：

> Semantic Versioning

---

# 66. Git Commit

不要最后一次提交全部代码。

按阶段提交：

```text
init: project architecture

feat: addon bootstrap

feat: mesh diagnostics

feat: reference image system

feat: semantic part system

feat: hair repair

feat: body template

feat: clothing separation

feat: fabric repair

feat: base generator

feat: print validation

feat: 3mf exporter

docs: user documentation
```

---

# 67. 重要开发规则

### 第一

> **不要假装实现。**

### 第二

> **不要假装测试。**

### 第三

> **不要假装 API 存在。**

### 第四

> **不要因为需求中写了某个 AI 模型，就假设模型已经存在。**

### 第五

> **不要因为某个功能困难，就直接删除需求。**

应该：

```text
完整目标
 ↓
当前可实现版本
 ↓
Fallback
 ↓
未来增强
```

---

# 68. 关于询问用户

你可以向用户提出问题。

但是：

> 如果可以通过检查文件、代码、Blender、GitHub 或实际运行自行确定，就不要询问用户。

只有以下情况优先询问：

- 会改变核心架构；
- 需要用户做不可逆选择；
- 缺少无法通过工具获得的信息；
- 需要用户提供真实输入；
- 涉及最终产品设计取舍。

---

# 69. 重要操作

你拥有较高操作权限。

但是：

> 权限越高，越必须谨慎。

在以下操作前必须检查：

- 删除文件；
- 覆盖用户代码；
- 修改 Blender 安装环境；
- 修改系统 Python；
- 大规模安装依赖；
- 修改 Git 历史；
- 删除模型；
- 修改第三方代码。

优先：

```text
Backup
 ↓
Modify
 ↓
Test
```

---

# 70. 最终目标

最终形成：

```text
┌──────────────────────────────┐
│      AI Figure Refiner       │
├──────────────────────────────┤
│ Reference Understanding      │
│ Semantic Parts               │
│ Geometry Repair              │
│ Hair Refinement              │
│ Body Calibration             │
│ Clothing Separation          │
│ Fabric Repair                │
│ Print Validation             │
│ Base Generation              │
│ 3MF Production               │
└──────────────┬───────────────┘
               ↓
        FDM Production Model
```

最终用户只需要：

> **导入 AI 手办 → 提供参考图 → 按 6 个确认节点修正 → 导出可打印 3MF。**

---

# 71. 最重要的开发哲学

不要为了“AI”而 AI。

如果传统几何算法比 AI 更可靠：

> 使用几何算法。

如果 AI 更适合：

> 使用 AI。

如果 AI 不确定：

> 交给用户。

如果用户可以在 10 秒内完成 AI 需要 30 秒才能可靠完成的工作：

> 提供人工工具。

最终目标不是：

> AI 自动做所有事情。

而是：

> **以最少的用户操作，把 AI 生成的手办可靠地转换成 FDM 生产模型。**

**可靠性 > 自动化程度。**

**可验证性 > Demo 效果。**

**可维护性 > 代码数量。**

**实际可打印 > 视觉上看起来正确。**

---

# 72. 当前第一任务

现在立即开始：

> **Technical Feasibility Audit**

完成调查后：

1. 建立项目目录；
2. 创建 `报告.md`；
3. 输出当前环境分析；
4. 输出技术风险；
5. 输出开源项目分析；
6. 输出架构设计；
7. 输出 V0.1 开发计划；
8. 等待或继续执行第一阶段开发。

**不要因为当前没有训练集而停止项目。**

**也不要制造一个不存在的训练集。**

当前首先建立：

> **可靠的 Blender + Geometry + Reference + Manual Workflow 基础。**

未来再逐步加入 AI 自动化与训练数据闭环。