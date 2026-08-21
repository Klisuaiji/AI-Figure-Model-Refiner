# AI Figure Model Refiner (AI 手办模型精修器)

> 将 AI 生成的 3D 手办模型，通过 **AI 智能体（MCP 接口）+ 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

## 项目状态（V0.13 — 工具集 UI + 多模态参考图 + GPL-3.0）

| Phase | 范围 | 状态 |
|-------|------|------|
| 0 | Technical Feasibility Audit | ✅ |
| 1 | Addon 框架（注册 / UI / Session / Logging / Settings / Undo） | ✅ |
| 2 | 网格诊断 + 基础修复 | ✅ |
| 2.b | 可打印性分析（壁厚 / 悬垂 / 悬空 / 验证） | ✅ |
| 3 | 参考图系统（4 视图 + 相机 + 轮廓） | ✅ |
| 4 | 部件语义识别（5 类 + 启发式 + 画笔） | ✅ |
| 5 | 头发精修（提取 + 加厚 + 程序化生成） | ✅ |
| 6-9 | 布料加厚 / 底座 / 合并 / 自动定向 | ✅ |
| 10 | **连接/拼接部件（凹凸连接件：圆柱 / 球窝 / 燕尾）** | ✅ |
| 11 | 3MF 导出（单 object，自研实现） | ✅ |
| 12 | AI Worker 协议（外部 Python，**V0.9 起移除**） | ⚠️ 已重构 |
| **V0.6** | **多对象 3MF + Voronoi 微结构 + Slicer CLI + 打包** | ✅ |
| **V0.7** | **训练数据导出 + AI Worker 端到端 + 切片端到端** | ✅ |
| **V0.8** | **代码审查 + 真实 ONNX 推理骨架** | ✅ |
| **V0.9** | **移除本地模型 → 改为 AI 智能体 MCP 接口（适配 Blender MCP）** | ✅ |
| **V0.10** | **凹凸连接件生成（圆柱/球窝/燕尾）+ 挖孔算子 + MCP 工具** | ✅ |
| **V0.11** | **半自动零布尔连接（凸柱 + 套筒），放弃 Boolean 求解** | ✅ |
| **V0.12** | **工具集 UI：固定工作流 → 按需工具面板** | ✅ |
| **V0.13** | **四视图参考图 → 多模态智能体辅助标注（正面必传）+ 协议改 GPL-3.0** | ✅ |

详见 `报告.md`、`CHANGELOG.md` 与 `wiki/`。N 面板为**工具集模式**（每个工具按需独立执行）；
AI 能力改由外部 AI 智能体通过 **MCP 协议**驱动本插件（Blender MCP 兼容）。

> **范式变更（V0.9）**：插件不再内置 / 依赖任何本地 AI 模型（ONNX / onnxruntime / training）。
> 所有"AI 部分"（语义识别、头发/布料/底座精修、可打印性决策）现在通过
> **MCP（Model Context Protocol）工具** 暴露给外部 AI 智能体。智能体可连接本 Blender
> 实例（Blender MCP 兼容桥）或独立运行 MCP 服务器，从而复用同一套领域工具。
>
> **半自动化（V0.11 起）**：连接件不再依赖 Boolean 求解——用户放置连接点（3D 游标），
> 插件直接生成 watertight 的**凸柱 + 凹套筒（盲孔实体）**，零布尔、可打印后装配。
> **多模态辅助（V0.13 起）**：N 面板上传四视图参考图（**正面必传**），多模态 AI 智能体
> 通过 `get_reference_images` 读图 → 视觉分析 → `set_part_labels` 写回部件标注。

## 安装

目标：Blender 5.2.0 LTS。

### 方式 A — 通过 Blender 偏好安装（推荐）

```bash
python scripts/package_addon.py    # 生成 output/ai_figure_refiner_v0.13.zip
```

然后在 Blender 中：**Edit > Preferences > Add-ons > Install…** → 选择
`output/ai_figure_refiner_v0.13.zip` → 启用 "AI Figure Model Refiner"。

> 最新可安装包也可直接从 `output/` 取（例如 `ai_figure_refiner_v0.13.zip`，
> 34 个文件 / 82KB，已用隔离配置 `addon_install + enable` 验证可安装）。

### 方式 B — 直接复制到用户目录

```python
from scripts.package_addon import install_addon
install_addon(blender_version="5.2")  # Windows / Linux / macOS 自动
```

### 方式 C — 开发模式

```python
from scripts.package_addon import build_addon_zip
build_addon_zip(output_path="/path/to/addon.zip")
```

### 测试安装

```bash
blender --background --python scripts/test_smoke.py            # V0.1
blender --background --python scripts/test_printability.py     # V0.2
blender --background --python scripts/test_reference.py        # V0.3
blender --background --python scripts/test_semantic.py         # V0.4
blender --background --python scripts/test_v0_6.py             # V0.6
blender --background --python scripts/test_v0_8_blender.py     # V0.8 算子注册校验
blender --background --python scripts/test_connectors.py       # V0.10/V0.11 连接件
blender --background --python scripts/test_toolset_v012.py     # V0.12 工具集
blender --background --python scripts/test_toolset_v013.py     # V0.13 参考图+MCP
# 全部输出 "== PASS =="
```

> 注：V0.5 / V0.7 的回归脚本依赖已移除的本地 AI Worker / 训练数据导出，已归档至
> `scripts/archive/`，不再纳入主测试套件。`scripts/test_mcp.py`（无需 Blender）
> 校验 MCP 服务器工具注册与领域逻辑。

## 使用流程（工具集模式，V0.12 起）

1. **导入模型** — FBX / OBJ / GLB / GLTF / STL / PLY（N 面板 → 源对象）。
2. **上传参考图（V0.13）** — 主面板 4 槽位（前/后/左/右）上传参考图，**正面（前）必须上传**；
   图片供多模态 AI 智能体辅助部件标注（也可 Ctrl+Alt+Q 开 Quad View 对照）。
3. **拆分部件** — 语义标注（启发式）→ `afr.split_by_part` 按标注拆成独立对象。
4. **头发修正 / 布料修正** — 提取 + 加厚 / 程序化生成；布料 Solidify。
5. **人物修正** — 网格诊断 → 基础修复 → 自动定向 / 合并 → 回滚。
6. **连接/拼接部件（V0.11）** — 移动 3D 游标到接缝 → 生成 凸柱+套筒（零布尔）。
7. **打印计算** — FDM 参数 + 可打印性分析（壁厚/悬垂/悬空）+ 底座 / Voronoi 减重。
8. **导出调试** — 3MF 导出（单/多/装配）→ 切片器（INI / G-code 校验 / 端到端切片）→ 日志。
9. **AI 智能体（MCP）** — 启动桥或外部运行 MCP 服务器，智能体经协议驱动本插件；
   多模态智能体用 `get_reference_images` 读参考图 → `label_parts(method='vision')` /
   `set_part_labels` 完成视觉辅助标注。

## 架构

```
addon/ai_figure_refiner/
├── __init__.py            # 注册、Scene 属性、版本（无 bpy 也可安全 import）
├── core/                  # 日志、错误、会话/快照、Pipeline
├── geometry/              # 诊断、修复、可打印性
├── ui/panel.py            # N-Panel 工具集（主面板 + 8 可折叠子面板 + 参考图槽位）
├── operators.py           # 核心算子（含 MCP 桥启停 / 连接件 / 按标注拆分）
├── reference/views.py     # 4 视图参考图 + 相机 + 背景图 + 轮廓
├── semantic/parts.py      # 5 部件 + 启发式 + 画笔 + 投票（AI 输出合并点）
├── parts_ops/             # 头发/布料/底座/合并/定向/Voronoi + 连接件(connectors.py)
├── exporter/              # 3MF 单/多 object/装配
├── slicer/                # PrusaSlicer 集成 + G-code 验证
└── mcp/                   # AI 智能体 MCP 接口（适配 Blender MCP）
    ├── backend.py         # Blender 后端：默认 socket localhost:9876（兼容 Blender MCP）
    ├── codegen.py         # 生成 Blender 内执行代码 + 解析 AFR_RESULT 哨兵
    ├── tools.py           # 纯领域函数（不 import bpy）
    ├── server.py          # MCP 服务器（FastMCP/MCPServer + 工具注册 + CLI）
    ├── bridge.py          # Blender 内 MCP 兼容 socket 桥（供智能体连接）
    ├── __init__.py        # 安全 import（不触发 bpy / 不触发 server）
    └── __main__.py        # `python -m ai_figure_refiner.mcp` 入口
```

## Blender 版本

- **Blender 5.2.0 LTS**（build 2026-07-14，hash `fbe6228777e7`）
- **Python 3.13.13**（Blender 内嵌）

## FDM 默认参数

| 项 | 默认 |
|----|------|
| 喷嘴直径 | 0.4 mm |
| 层高 | 0.2 mm |
| 材料 | PLA |
| 最低壁厚 | 0.8 mm |
| PLA 密度 | 1.24 g/cm³ |

## AI 智能体（MCP 接口，V0.9 新增）

插件不再内置任何本地 AI 模型。AI 能力通过 **MCP 协议** 暴露给外部 AI 智能体，
智能体即可像"调用工具"一样驱动本 Blender 实例完成精修。

### 两种接入方式

**方式 1 — 在 Blender 内启动桥（推荐，Blender MCP 兼容）**

1. Blender 中：**N 面板 → AI 智能体 (MCP) → 启动桥**（默认 `localhost:9876`）。
2. 外部 AI 智能体（如支持 Blender MCP 的客户端）连接该端口，复用 Blender MCP 协议。

**方式 2 — 独立运行 MCP 服务器（无头，供任意 MCP 客户端）**

```bash
# 需安装 mcp SDK: pip install mcp
python scripts/run_mcp_server.py --host 127.0.0.1 --port 9877
# 或: python -m ai_figure_refiner.mcp  (作为 MCP stdio 服务器)
```

服务器自动把每个工具包装为：生成在 Blender 内执行的代码 → 经后端执行 →
解析 `AFR_RESULT` 哨兵返回结构化结果。`backend` 默认指向 Blender MCP socket，
亦可设为 `in-process`（在同一 Blender 进程内运行，便于测试）。

### 暴露的工具（V0.13，共 16 个）

`list_objects` / `diagnose` / `repair` / `printability` / `label_parts`（`method='heuristics' |
'flood_body' | 'vision'/'multimodal'，后者要求 FRONT 参考图已上传）/ `set_part_labels`（视觉
标注写回）/ `get_reference_images`（多模态智能体读参考图）/ `process_hair` / `process_fabric` /
`process_base` / `merge_parts` / `auto_orient` / `export_3mf` / `create_connector` /
`carve_socket` / `run_blender_code`

**多模态辅助标注链路（V0.13）**：

```
get_reference_images  → 多模态视觉分析（前/后/左/右四张图）
                      → set_part_labels(逐顶点标签) 或 label_parts(method='vision')
```

### 依赖

- 仅 MCP 服务器运行时需要 `mcp` SDK（`pip install mcp`）。
- Blender 端桥纯用标准库（`socket` / `json` / `threading`），**零第三方依赖**。

## 已知限制

- Blender 5.2 **无原生 3MF 导入** — V0.6 自研导出（单/多/装配）；导入可在 V1.0 加。
- **AI 推理移至外部智能体** — V0.9 起插件不再内置任何本地模型；
  AI 语义识别 / 精修策略由接入的 AI 智能体（MCP 客户端）自带环境完成。
- **AI 生成网格通常非流形** — Rodin 等工具产出的开放壳无法直接 Boolean 挖孔（会塌缩/静默失败）；
  因此 V0.11 连接件采用**零布尔**（凸柱+套筒独立实体），Boolean 仅限流形网格使用。
- **Voronoi 微结构**：当前是 tent-pole 骨架（线段），需要切片器按线宽挤出成实体管。

## 开源依赖

- **插件本体（Blender 端）零第三方代码依赖** — 全部用 Blender 原生 API + Python stdlib。
- **MCP 服务器运行时** 需 `mcp` SDK（`pip install mcp`），但这是外部进程，不影响 Blender 端。

## License

**GPL-3.0-or-later**（详见仓库根目录 `LICENSE`）。全部源码文件均带 SPDX 头。

本项目允许且鼓励基于 GPL 许可证互操作与引用其他 GPL 开源代码（例如
[SnapSplit](https://github.com/Betakontext/snapsplit) 等 3D 打印连接件工具），
引用时须保留其版权声明并遵守 GPL 条款。

## Git

- 仓库：`https://github.com/Klisuaiji/AI-Figure-Model-Refiner`
- 分支：`main`
- 版本：V0.13（工具集 UI + 四视图参考图 → 多模态智能体辅助标注，协议 GPL-3.0）
- 回归测试脚本全部 PASS；`scripts/test_mcp.py` 校验 MCP 工具注册与逻辑。