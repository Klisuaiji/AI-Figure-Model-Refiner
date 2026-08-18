# 安装 Installation

目标运行环境：**Blender 5.2.0 LTS**（内嵌 Python 3.13）。

## 方式 A — 打包后通过偏好安装（推荐）

生成可安装的 zip：

```bash
python scripts/package_addon.py    # 生成 output/ai_figure_refiner.zip
```

然后在 Blender 中：

**Edit › Preferences › Add-ons › Install…** → 选择 `output/ai_figure_refiner.zip`
→ 启用 **"AI Figure Model Refiner"**。

## 方式 B — 直接复制到用户目录

```python
from scripts.package_addon import install_addon
install_addon(blender_version="5.2")  # 自动识别 Windows / Linux / macOS
```

该命令会复制到：

- Windows: `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\`
- Linux/macOS: `~/.config/blender/5.2/scripts/addons/`

## 方式 C — 开发模式（仅构建 zip，不安装）

```python
from scripts.package_addon import build_addon_zip
build_addon_zip(output_path="/path/to/addon.zip")
```

## 启用后

在 3D 视图右侧 **Sidebar（N 面板）** 找到 **AI Figure Refiner** 标签页即可使用。

## AI 智能体（MCP）运行时依赖（可选）

仅当你要**在 Blender 外独立运行 MCP 服务器**时才需要：

```bash
pip install mcp
python scripts/run_mcp_server.py --host 127.0.0.1 --port 9877
```

Blender 内的 MCP 桥（N 面板 → AI 智能体 (MCP) → 启动桥）**纯用标准库**，
无需安装任何第三方包。
