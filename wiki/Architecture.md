# 架构 Architecture

```
addon/ai_figure_refiner/
├── __init__.py            # 注册、Scene 属性、版本（无 bpy 也可安全 import）
├── core/                  # 日志、错误、会话/快照、Pipeline
├── geometry/              # 诊断、修复、可打印性
├── ui/panel.py            # N-Panel 主面板
├── operators.py           # 核心算子（含 MCP 桥启停算子）
├── reference/views.py     # 4 视图 + 相机 + 背景图
├── semantic/parts.py      # 5 部件 + 启发式 + 画笔 + 投票（AI 输出合并点）
├── parts_ops/             # 头发/布料/底座/合并/定向/Voronoi/**凹凸连接件(connectors)**
├── exporter/              # 3MF 单/多 object/装配
├── slicer/                # PrusaSlicer 集成 + G-code 验证
└── mcp/                   # AI 智能体 MCP 接口（适配 Blender MCP）
    ├── backend.py         # Blender 后端：默认 socket localhost:9876（兼容 Blender MCP）
    ├── codegen.py         # 生成 Blender 内执行代码 + 解析 AFR_RESULT 哨兵
    ├── tools.py           # 纯领域函数（不 import bpy）
    ├── server.py          # MCP 服务器（MCPServer + 工具注册 + CLI）
    ├── bridge.py          # Blender 内 MCP 兼容 socket 桥（供智能体连接）
    ├── __init__.py        # 安全 import（不触发 bpy / 不触发 server）
    └── __main__.py        # `python -m ai_figure_refiner.mcp` 入口
```

## 设计要点

- **无本地 AI 模型（V0.9 起）**：插件本体不依赖任何推理运行时。所有"AI 部分"
  （语义识别、头发/布料/底座精修、可打印性决策）由外部 AI 智能体通过 MCP 工具完成。
- **MCP 工具 = 纯函数 + 代码生成**：`tools.py` 中的工具函数不 `import bpy`，
  它们生成一段在 Blender 内执行的代码（`codegen.py` 包装），经 `backend` 执行后
  解析 `AFR_RESULT` 哨兵返回结构化结果。
- **两种后端**：默认连接 Blender MCP socket（`localhost:9876`）；也可 `in-process`
  在同一 Blender 进程内运行，便于测试。
- **安全 import**：`__init__.py` 在无 `bpy` 的环境下被导入时仅设置 `bpy=None` 并跳过
  重量级注册，使独立 MCP 服务器能复用 `mcp` 子包。

## 脚本布局

```
scripts/
├── package_addon.py      # 打包 / 安装
├── run_mcp_server.py     # 启动独立 MCP 服务器
├── test_mcp.py           # 校验 MCP 工具注册 + 逻辑（无需 Blender）
├── test_*.py             # 各阶段回归测试（需 Blender 无头运行）
├── inspect_blend.py      # 通用 .blend 检查工具
├── list_operators.py     # 列出已注册算子
└── archive/              # 50 个一次性 / 本地模型相关实验脚本
```
