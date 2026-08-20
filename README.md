# AI Figure Model Refiner (AI 手办模型精修器)

> 将 AI 生成的 3D 手办模型，通过 **AI 智能体（MCP 接口）+ 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

## 项目状态（V0.10 — AI 智能体 / MCP 范式 + 凹凸连接件）

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

详见 `报告.md`、`CHANGELOG.md` 与 `wiki/`。N 面板保留核心算子；AI 能力改由外部 AI 智能体通过 **MCP 协议**驱动本插件（Blender MCP 兼容）。

> **范式变更（V0.9）**：插件不再内置 / 依赖任何本地 AI 模型（ONNX / onnxruntime / training）。
> 所有"AI 部分"（语义识别、头发/布料/底座精修、可打印性决策）现在通过
> **MCP（Model Context Protocol）工具** 暴露给外部 AI 智能体。智能体可连接本 Blender
> 实例（Blender MCP 兼容桥）或独立运行 MCP 服务器，从而复用同一套领域工具。

## 安装

目标：Blender 5.2.0 LTS。

### 方式 A — 通过 Blender 偏好安装（推荐，V0.6+ 提供）

```bash
python scripts/package_addon.py    # 生成 output/ai_figure_refiner.zip
```

然后在 Blender 中：**Edit > Preferences > Add-ons > Install…** → 选择
`output/ai_figure_refiner.zip` → 启用 "AI Figure Model Refiner"。

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
blender --background --python scripts/test_smoke.py        # V0.1
blender --background --python scripts/test_printability.py # V0.2
blender --background --python scripts/test_reference.py    # V0.3
blender --background --python scripts/test_semantic.py     # V0.4
blender --background --python scripts/test_v0_6.py         # V0.6
blender --background --python scripts/test_v0_8_blender.py # V0.8 算子注册校验
# 全部输出 "== PASS =="
```

> 注：V0.5 / V0.7 的回归脚本依赖已移除的本地 AI Worker / 训练数据导出，已归档至
> `scripts/archive/`，不再纳入主测试套件。新增 `scripts/test_mcp.py`（无需 Blender）
> 校验 MCP 服务器工具注册与领域逻辑。

## 使用流程（典型）

1. **导入模型** — FBX / OBJ / GLB / GLTF / STL / PLY，N 面板 → 导入 / 源对象。
2. **运行网格诊断** — 检查水密 / 重复顶点 / 边界边 / 零面积 / 体积 / bbox / 部件数。
3. **基础修复** — 去重 / 法线重算 / 补洞；不满意可回滚到上一步快照。
4. **可打印性分析** — 壁厚（BVH 射线） / 悬垂 / 悬空部件 / 验证（ERROR/WARNING/INFO）。
5. **创建 4 个参考相机** + 加载参考图（FRONT/BACK/LEFT/RIGHT） — 对齐 bbox / 切视角。
6. **应用几何启发式** 标注 HAIR/HEAD/BODY/FABRIC/BASE — 用户可手工 brush 调整。
7. **头发精修** — 提取 HAIR → 加厚 / 或程序化生成（curl/noise/taper）。
8. **Voronoi 减重** — 内部微结构降低材料消耗（V0.6）。
9. **布料加厚 / 生成底座 / 合并多部件 / 自动定向** 落地。
10. **导出 3MF** — 单 / 多 object / 装配嵌套 components（V0.6）。
11. **调用切片器** — 端到端 3MF → INI → PrusaSlicer/OrcaSlicer → G-code 校验（V0.6/V0.7）。
12. **AI 智能体（MCP）** — 启动面板中的 "AI 智能体 (MCP)" 桥，或在外部运行 MCP 服务器，
    由 AI 智能体经 Blender MCP 兼容协议驱动本插件完成语义识别 / 头发·布料·底座精修 /
    可打印性决策。

## 架构

```
addon/ai_figure_refiner/
├── __init__.py            # 注册、Scene 属性、版本（无 bpy 也可安全 import）
├── core/                  # 日志、错误、会话/快照、Pipeline
├── geometry/              # 诊断、修复、可打印性
├── ui/panel.py            # N-Panel 主面板
├── operators.py           # 核心算子（含 MCP 桥启停算子）
├── reference/views.py     # 4 视图 + 相机 + 背景图
├── semantic/parts.py      # 5 部件 + 启发式 + 画笔 + 投票（AI 输出合并点）
├── parts_ops/             # 头发/布料/底座/合并/定向/Voronoi
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

### 暴露的工具（节选）

`afr_diagnose` / `afr_repair_manifold` / `afr_printability` / `afr_semantic_label` /
`afr_optimize_hair` / `afr_optimize_fabric` / `afr_optimize_base` / `afr_merge_parts` /
`afr_export_3mf` / `afr_list_objects` / `afr_get_scene_summary`

### 依赖

- 仅 MCP 服务器运行时需要 `mcp` SDK（`pip install mcp`）。
- Blender 端桥纯用标准库（`socket` / `json` / `threading`），**零第三方依赖**。

## 已知限制

- Blender 5.2 **无原生 3MF 导入** — V0.6 自研导出（单/多/装配）；导入可在 V1.0 加。
- **AI 推理移至外部智能体** — V0.9 起插件不再内置任何本地模型；
  AI 语义识别 / 精修策略由接入的 AI 智能体（MCP 客户端）自带环境完成。
- **Boolean Union 在极端几何上可能失败** — 通用解算器限制；建议先修水密。
- **Voronoi 微结构**：当前是 tent-pole 骨架（线段），需要切片器按线宽挤出成实体管。

## 开源依赖

- **插件本体（Blender 端）零第三方代码依赖** — 全部用 Blender 原生 API + Python stdlib。
- **MCP 服务器运行时** 需 `mcp` SDK（`pip install mcp`），但这是外部进程，不影响 Blender 端。

## License

待定（V1.0 时确定）。当前所有代码为本项目原创。

## Git

- 仓库：`https://github.com/Klisuaiji/AI-Figure-Model-Refiner`
- 分支：`main`
- 版本：V0.9（移除本地模型，改为 AI 智能体 MCP 接口）
- 回归测试脚本全部 PASS；`scripts/test_mcp.py` 校验 MCP 工具注册与逻辑。