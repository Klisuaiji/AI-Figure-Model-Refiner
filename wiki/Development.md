# 开发 Development

## 仓库脚本布局

```
scripts/
├── package_addon.py      # 打包 / 安装 addon
├── run_mcp_server.py     # 启动独立 MCP 服务器
├── test_mcp.py           # 校验 MCP 工具注册 + 逻辑（无需 Blender）
├── test_smoke.py         # V0.1 冒烟测试
├── test_printability.py  # V0.2 可打印性
├── test_reference.py     # V0.3 参考图
├── test_semantic.py      # V0.4 语义
├── test_v0_6.py          # V0.6 多对象 3MF + Voronoi + Slicer
├── test_v0_8_blender.py  # V0.8 算子注册校验
├── inspect_blend.py      # 通用 .blend 检查
├── list_operators.py     # 列出已注册算子
├── audit_blender_env.py  # Blender 环境自检
└── archive/              # 50 个一次性 / 本地模型相关实验脚本（不纳入主测试）
```

> V0.5 / V0.7 的回归脚本依赖已移除的本地 AI Worker / 训练数据导出，已归档至
> `scripts/archive/`，不再纳入主测试套件。

## 运行测试

### MCP 接口测试（无需 Blender）

```bash
pip install mcp
python scripts/test_mcp.py
# 校验 12 个工具注册、工具体仅 import 允许的模块、AFR_RESULT 往返正确
```

### Blender 无头回归测试

```bash
blender --background --python scripts/test_smoke.py
blender --background --python scripts/test_printability.py
blender --background --python scripts/test_reference.py
blender --background --python scripts/test_semantic.py
blender --background --python scripts/test_v0_6.py
blender --background --python scripts/test_v0_8_blender.py
# 全部输出 "== PASS =="
```

## 独立运行 MCP 服务器

```bash
python scripts/run_mcp_server.py --host 127.0.0.1 --port 9877
# 或作为 stdio MCP 服务器:
python -m ai_figure_refiner.mcp
```

## 代码规范

- 插件本体（Blender 端）**零第三方依赖**，只用 Blender 原生 API + Python stdlib。
- 所有 ImportHelper / ExportHelper 派生类必须加 `bl_options = {"REGISTER", "UNDO"}`。
- `mcp/tools.py` 中的函数**不得 `import bpy`**（它们生成在 Blender 内执行的代码）。
- 提交前确保所有 `addon/**/*.py` 通过 `python -m py_compile`。
