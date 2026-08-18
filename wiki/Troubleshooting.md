# 故障排查 Troubleshooting

## Blender 端

**Q: 面板里没有 "AI Figure Refiner" 标签页？**
- 确认插件已启用：**Edit › Preferences › Add-ons**，搜索 "AI Figure Refiner"。
- 确认 Blender 版本为 **5.2.x LTS**（其它版本 API 不兼容）。

**Q: "AI 智能体 (MCP)" 启动桥失败？**
- 检查端口 `9876` 是否被占用；换端口需改 `mcp/bridge.py` 的 host/port 或面板算子参数。
- 桥纯用标准库，不依赖 `mcp` SDK；若失败多为端口占用或权限问题。

**Q: 导出 3MF 后切片器报错？**
- 先跑 `afr_repair_manifold` 确保水密（补洞 / 去重 / 重算法线）。
- 非 manifold 几何无法可靠导出，建议先在 Blender 内 `Remesh` 修整。

**Q: Boolean Union 失败？**
- 通用解算器限制：极端几何上可能失败。建议先修水密，再合并。

## MCP 服务器 / AI 智能体

**Q: `python -m ai_figure_refiner.mcp` 报 ImportError: No module named 'mcp'？**
- 安装：`pip install mcp`。该依赖仅 MCP 服务器运行时需要，Blender 端不需要。

**Q: 工具返回 `error` 且说连不上 Blender？**
- 若 backend 为 `socket`（默认），需先在 Blender 内启动桥（端口 `9876`）。
- 测试可用 `in-process` 后端（同一进程内运行，无需 Blender 桥）。

**Q: 工具体执行报错 "unknown import"？**
- 工具体只允许 import stdlib 与 `ai_figure_refiner.*` 模块；不要在 `tools.py`
  里引入 `bpy` 或任意第三方包。`bpy` 只在生成的 Blender 内代码中使用。

## 已知限制

- Blender 5.2 **无原生 3MF 导入** — 仅自研导出（单/多/装配）；导入可在 V1.0 加。
- **AI 推理移至外部智能体** — V0.9 起插件不再内置任何本地模型。
- **Voronoi 微结构**：当前是 tent-pole 骨架（线段），需切片器按线宽挤出成实体管。
