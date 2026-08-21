# AI 手办模型精修器 — 落地计划（对照《附加提示词.md》）

> 生成日期：2026-08-21
> 目的：把《附加提示词.md》的设计要求落到当前代码库，给出可执行的里程碑计划。
> 巡检依据：已读 `__init__.py` / `operators.py` / `mcp/tools.py` / `reference/views.py` / `geometry/repair.py`，并对照 `addon/ai_figure_refiner/` 目录结构。

## 0. 结论先行（重要）

插件比 spec 假设的「仅能跑通拆分/加厚/底座/导出」**成熟得多**。以下模块在代码中**已存在**，无需从零重建：

- 四视图参考图系统（FRONT/BACK/LEFT/RIGHT 相机 + 背景图）→ spec 2.2「参考图」
- `afr.hair_generate`（曲线→加厚网格，含 count/length/curl/noise/radius）→ spec 3 程序化发型**基础版**
- `afr.repair_basic`（remove_doubles + **holes_fill** + recalc_normals）→ spec 1.2 填充闭合**基础版**
- `afr.split_by_part`（按 HAIR/HEAD/BODY/FABRIC/BASE 标注拆分）→ spec 1.1 拆分
- `mcp/tools.py` 已暴露 diagnose/repair/printability/label_parts/process_hair/process_fabric/process_base/merge_parts/export_3mf/create_connector/carve_socket → spec 6.2 MCP 工具**大部分已存在**
- 连接键（peg/hole/ball/socket/dovetail）、切片器集成（Orca/PrusaSlicer 查找+INI+G-code 校验）、Voronoi 减重微结构 → 额外已有能力

因此本计划定位为 **补缺 + 增强**，不是重建。下面先给「已实现 ↔ spec」对照表，再列缺口与里程碑。

## 1. 已实现 ↔ spec 对照

| spec 章节 | spec 要求 | 当前代码状态 | 落差 |
|---|---|---|---|
| 1.1 三状态兼容 | 自动检测 未拆/已拆未命名/已命名未填充 | `split_by_part` 仅「全拆」，无状态检测 | **缺口** |
| 1.2 拆分流程 | 半自动拆分→理解→拆开→填充闭合 | 拆分有；填充闭合仅在 `repair_basic` 全局，未接进 split 后每部件 | **缺口（部分已有）** |
| 1.2 命名 | 预设列表 hair/head/body/fabric/base/accessory | 标注即命名（PART_ID 五类） | 基本覆盖；缺 accessory |
| 2.1 多余肢体 | 顶点度检测+高亮+确认删除+断口桥接 | 无 | **缺口** |
| 2.2 身型修正 | 素体（MPFB2/Studio Human）动态参考+贴合 | `reference/views.py` 仅 2D 参考图，无 3D 素体 | **缺口（需外部资源）** |
| 3 发型修正 | 引导线/刘海间隙/中空填充/二次元笔触预设 | `hair_generate` 基础曲线生成已有 | **缺口（增强）** |
| 4 布料修正 | ray_cast 穿插检测+布尔差+Bevel+按部位厚度 | `fabric_solidify` 仅单厚度 Solidify | **缺口** |
| 5 装饰物 | 资产库 json+导入对齐合并 | 无 | **缺口** |
| 6.1 架构 | MCP Server（spec 写 9879） | `mcp/` 已存在，bridge 默认 127.0.0.1:9876（spec 写 9879，需对齐命名） | 端口命名不一致 |
| 6.2 工具表 | 10 个工具 | 已有 13+ 个，但缺 `separate_part/fix_body_proportion/remove_extra_limbs/check_intersection/replace_decoration/apply_plan_step` | **缺口（薄包装即可）** |
| 6.3 Plan Mode | JSON 计划→逐条模态确认 | 无 | **缺口** |
| 6.4 ComfyUI 贴图 | Mesh+参考图→UV 贴图 | 无 | **缺口（需 ComfyUI 运行）** |
| 8 参考清单 | 开源资源索引 | 无代码动作 | 仅文档 |

## 2. 缺口 GAP 清单（按优先级）

- **G1（核心）**：拆分后每部件未做「填充闭合」→ 实测 1725 边界边、非水密。直接阻断可打印。
- **G2（核心）**：无三状态输入兼容，重复跑会重复拆分/丢命名。
- **G3**：无多余肢体去除（用户原始痛点之一「头发修复」相邻）。
- **G4**：布料穿插检测+布尔+按部位厚度缺失。
- **G5**：装饰物资产库缺失。
- **G6**：身型素体参考缺失（需外部资源）。
- **G7**：发型仅基础版，缺笔触预设/刘海间隙/中空填充。
- **G8**：MCP 缺 6 个工具 + Plan Mode。
- **G9**：ComfyUI 贴图缺失（需外部资源）。
- **G0（基线）**：安装副本与源可能漂移（曾导致空白面板）；`__init__.py` version 仍 `(0,13,0)`，与已提交 V0.14 不一致；weld fix 待确认已进安装副本。

## 3. 里程碑计划（按依赖排序）

### Phase 0 — 基线对齐（必做，无外部依赖）
- 目标：安装副本 == 源；version tuple `(0,13,0)`→`(0,15,0)`；清 `__pycache__`；确认 weld fix（`extract_part` 用 `v.index` 而非 `id(v)`）已在安装副本。
- 文件：`__init__.py`、`parts_ops/hair.py`、安装目录同步脚本。
- 验证：在 Blender reload 插件后，`bpy.data.pending_deps` 无错；用 stub 调 9 面板 `draw()` 全 `DRAW OK`；对 part_0 拆分后重复顶点 = 0%。

### Phase 1 — 拆分三状态兼容 + 每部件填充闭合（核心，无外部依赖）【对应 G1/G2】
- 目标：
  1. 新增 `_detect_input_state(scene)` → `'A'`（未拆未命名）/`'B'`（已拆未命名）/`'C'`（已命名未填充）/`unknown`。
  2. `split_by_part` 改造：按状态分支——A 走 AI 拆分+命名；B 跳过拆分进命名；C 跳过前两步直接填充闭合。
  3. 拆分后对每个部件自动 `holes_fill + Solidify`（per-part 水密化），复用 `geometry/repair.py` 逻辑并抽成 `repair_part(obj)`。
- 文件：`operators.py`（`split_by_part`/`repair_basic` 改造）、`parts_ops/hair.py`（`extract_part` 增加 `fill_closed` 参数）、`semantic/parts.py`（状态判定）、`geometry/repair.py`（导出 per-part 函数）。
- 验证：用 `D:/未命名.blend` 的 part_0 跑三状态；`run_printability` 报告每部件 `watertight=True`，`boundary_edges` 趋近 0。

### Phase 2 — 去除多余肢体（无外部依赖）【对应 G3】
- 目标：遍历 `vert.link_edges` 度；度>2 标记疑似；红色半透明高亮（顶点组 + 视图着色覆盖）；算子确认删除 + `bridge_loops`/`grid_fill` 断口桥接。
- 文件：新增 `parts_ops/limbs.py` + `operators.py` 算子 + `ui/panel.py` 条目。
- 验证：合成带多余分支的测试网格，检测→删除→桥接闭环。

### Phase 3 — 布料穿插修复（无外部依赖，布尔需实测）【对应 G4】
- 目标：`ray_cast` 定位 fabric↔body 穿插；黄色高亮；Boolean Difference（先用 bpy 原生 Boolean，Solidean 作可选增强）；边界 Bevel；按部位厚度 Solidify（外袍 1.2 / 普通 1.0 / 蕾丝 0.8 / 硬装饰 1.5）。
- 文件：新增 `parts_ops/fabric.py` + `operators.py` + `ui/panel.py`。
- 验证：构造穿插样例，修复后 `ray_cast` 无穿插、壁厚达标。

### Phase 4 — 装饰物资产库（无外部依赖，资产可选）【对应 G5】
- 目标：`assets/decorations.json` 索引（标签 hair_accessory/weapon/badge/shoe/other）；删除原低精度装饰→导入高精度→边界框中心对齐+法线匹配→用户微调→合并。
- 文件：新增 `parts_ops/decoration.py` + `assets/decorations.json` 骨架 + `operators.py` + `ui/panel.py`。
- 验证：用一个内置基础网格（如圆柱）模拟资产替换流程。

### Phase 5 — 身型修正 / 素体参考（需外部依赖）【对应 G6】
- 目标：导入素体（MPFB 2 / Blender Studio Human）作为动态参考；Shrinkwrap / Surface Deform 局部贴合手办身体；OpenPose→Rigify 自动摆姿（可选增强）。
- 外部依赖：**MPFB 2 插件 或 Blender Studio Human .blend（当前未安装）**；OpenPose/ROMP（可选）。
- 文件：新增 `parts_ops/body.py` + `operators.py` + UI。先做「手动摆姿 + 局部贴合」框架，OpenPose 自动摆姿作为后续增强。
- 验证：导入一个素体，对手办身体做局部 Shrinkwrap 贴合。

### Phase 6 — 程序化发型增强（无外部依赖）【对应 G7】
- 目标：在现有 `hair_generate` 上增强——二次元笔触预设（双马尾/呆毛等）、刘海间隙噪波、中空填充（Fill Cap + Root Pin 顶点组）、引导线生成。
- 文件：`parts_ops/hair.py`（`generate_hair_curves`/`curves_to_mesh` 增强）+ UI 参数。
- 验证：生成双马尾/呆毛预设，检查中空区域已填充。

### Phase 7 — MCP 工具补全 + Plan Mode（无外部依赖）【对应 G8】
- 目标：
  1. 补全缺失工具：`separate_part`/`fix_body_proportion`/`remove_extra_limbs`/`check_intersection`/`fix_fabric`/`replace_decoration`/`apply_plan_step`（薄包装，复用现有 domain 函数）。
  2. Plan Mode：AI 生成步骤计划 JSON → 逐条模态确认面板（3D 预览+参数）→ 用户可中断/回退。
- 文件：`mcp/tools.py` 扩展 + 新增 `mcp/plan.py` + `operators.py` + UI 模态。
- 验证：用 MCP 桥跑 `separate_part`/`remove_extra_limbs`；Plan Mode 生成计划并能逐条执行。

### Phase 8 — ComfyUI 贴图（需外部依赖）【对应 G9】
- 目标：导出前可选调用 ComfyUI HTTP API（Mesh+参考图→UV 贴图），生成后应用到模型再导出 3MF（含颜色/材质元数据）。
- 外部依赖：**ComfyUI 本地服务运行 + Hunyuan3D-2.1 Texgen / MV-Adapter 工作流**（当前可能未运行）。
- 文件：新增 `mcp/comfyui_client.py` 或 `exporter/texturing.py` + UI 开关。
- 验证：ComfyUI 在线时跑通一次贴图→应用到模型→导出。

## 4. 外部依赖汇总

| 依赖 | 用于 | 当前状态 | 阻塞的 Phase |
|---|---|---|---|
| MPFB 2 / Blender Studio Human | 素体参考（2.2/5） | 未安装 | Phase 5 |
| OpenPose / ROMP / PIXIE | 2D→3D 姿态（2.2） | 未安装（可选增强） | Phase 5（自动摆姿部分） |
| Solidean 插件 | 鲁棒布尔（4） | 未安装（可选，原生 Boolean 可替代） | Phase 3（增强） |
| ComfyUI + Texgen/MV-Adapter | 贴图（6.4） | 可能未运行 | Phase 8 |
| SAM | 发型区域分割（3） | 未安装（可选，可用参考图遮罩替代） | Phase 6（增强） |

## 5. 建议首刀

**Phase 0 + Phase 1**（基线对齐 + 三状态拆分 + 每部件填充闭合）：
- 无外部依赖、风险低、直接解决我们实测出的「非水密 / 1725 边界边」核心问题；
- 建立在已修好的焊接（weld fix）基础上；
- 是后续所有部件级修正（头发/布料/肢体）的前置。

Phase 2（去除多余肢体）紧随其后，因它直接对应你最初的「头发修复」相关痛点。

**待你确认**：是否从 Phase 0 + Phase 1 开始动手？或调整优先级（例如先把 MCP 工具/Plan Mode 补齐、或先做 Phase 2 多余肢体）？确认后我按「单 Phase 完成 → 无头回归 EXIT=0 → 审计 → 清理」的节奏推进，并本地提交。
