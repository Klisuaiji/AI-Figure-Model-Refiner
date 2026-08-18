# AI 智能体 MCP 接口（V0.9 新增）

插件不再内置任何本地 AI 模型。AI 能力通过 **MCP（Model Context Protocol）** 暴露给
外部 AI 智能体，智能体即可像"调用工具"一样驱动本 Blender 实例完成精修。该接口与
**Blender MCP** 协议兼容。

## 两种接入方式

### 方式 1 — 在 Blender 内启动桥（推荐，Blender MCP 兼容）

1. Blender 中：**N 面板 → AI 智能体 (MCP) → 启动桥**（默认 `localhost:9876`）。
2. 外部 AI 智能体（支持 Blender MCP 的客户端）连接该端口，复用 Blender MCP 协议。

### 方式 2 — 独立运行 MCP 服务器（无头，供任意 MCP 客户端）

```bash
# 需安装 mcp SDK: pip install mcp
python scripts/run_mcp_server.py --host 127.0.0.1 --port 9877
# 或作为 MCP stdio 服务器:
python -m ai_figure_refiner.mcp
```

服务器自动把每个工具包装为：生成在 Blender 内执行的代码 → 经后端执行 →
解析 `AFR_RESULT` 哨兵返回结构化结果。`backend` 默认指向 Blender MCP socket，
亦可设为 `in-process`（在同一 Blender 进程内运行，便于测试）。

## 模块职责

| 模块 | 职责 |
|------|------|
| `backend.py` | Blender 后端：默认 socket `localhost:9876`（兼容 Blender MCP），支持 `in-process` |
| `codegen.py` | 将工具体包装为 Blender 内执行代码，并解析 `AFR_RESULT` 哨兵 |
| `tools.py` | 纯领域函数（不 `import bpy`）：diagnose / repair / printability / label / hair / fabric / base / merge / export 等 |
| `server.py` | MCP 服务器（MCPServer）注册全部工具 + CLI `main()` |
| `bridge.py` | Blender 内 MCP 兼容 socket 桥，供智能体连接 |
| `__init__.py` | 安全 import（不触发 `bpy` / 不触发 `server`） |
| `__main__.py` | `python -m ai_figure_refiner.mcp` 入口 |

## 暴露的工具（节选）

`afr_diagnose` / `afr_repair_manifold` / `afr_printability` / `afr_semantic_label` /
`afr_optimize_hair` / `afr_optimize_fabric` / `afr_optimize_base` / `afr_merge_parts` /
`afr_export_3mf` / `afr_list_objects` / `afr_get_scene_summary` / `afr_run_blender_code`

详见 [API 参考](API-Reference)。

## 依赖

- 仅 MCP 服务器运行时需要 `mcp` SDK（`pip install mcp`）。
- Blender 端桥纯用标准库（`socket` / `json` / `threading`），**零第三方依赖**。
