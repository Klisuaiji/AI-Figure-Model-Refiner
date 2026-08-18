# API 参考 — MCP Tools

MCP 服务器（`ai_figure_refiner.mcp.server`）注册的工具如下。每个工具最终在
Blender 内执行对应领域逻辑，返回结构化 JSON 结果（经 `AFR_RESULT` 哨兵解析）。

| 工具 | 参数 | 说明 |
|------|------|------|
| `list_objects` | — | 列出场景全部物体（名称 / 类型 / 顶点数 / 面数 / bbox）。 |
| `afr_diagnose` | `object_name` | 网格诊断：水密 / 重复顶点 / 边界边 / 零面积 / 体积 / bbox / 部件数。 |
| `afr_repair` | `object_name` | 基础修复：去重 / 法线重算 / 补洞，返回快照信息。 |
| `afr_printability` | `object_name` | 可打印性分析：壁厚（BVH 射线）/ 悬垂 / 悬空 / 验证（ERROR/WARNING/INFO）。 |
| `afr_semantic_label` | `object_name` | 几何启发式语义标注 HAIR/HEAD/BODY/FABRIC/BASE，写 per-vertex 属性。 |
| `afr_optimize_hair` | `object_name`, `decimate`, `solidify_mm`, `toon` | 头发精修：提取 + 加厚 + 程序化（curl/noise/taper）。 |
| `afr_optimize_fabric` | `object_name`, `solidify_mm` | 布料加厚（保证最低壁厚）。 |
| `afr_optimize_base` | `object_name` | 底座生成 / 修整。 |
| `afr_merge_parts` | `object_names` | 合并多部件（Boolean Union），先确保水密。 |
| `afr_auto_orient` | `object_names` | 自动定向（以最小包围盒底面落地）。 |
| `afr_export_3mf` | `object_names`, `filepath` | 导出 3MF（单 / 多 object / 装配嵌套 components）。 |
| `afr_run_blender_code` | `code` | 在 Blender 内执行任意 Python 代码并返回 `AFR_RESULT` 哨兵结果。 |

## 执行模型

1. `tools.py` 中的工具体生成一段 Blender 内执行代码（仅 import 允许的 stdlib /
   `ai_figure_refiner.*` 模块）。
2. `codegen.py` 用哨兵包装：`__AFR_RESULT__ = json.dumps(result)`。
3. `backend.py` 经 socket（默认 `localhost:9876`，兼容 Blender MCP）或 `in-process`
   执行，捕获 stdout / 异常，解析 `AFR_RESULT` 返回结构化结果。
4. 调用方（AI 智能体）拿到结构化 JSON；失败时有 `error` 字段与 traceback。

## 后端配置

```python
from ai_figure_refiner.mcp import get_default_backend
backend = get_default_backend()          # 默认 "socket"
# 或显式:
backend = get_default_backend("in-process")
```
