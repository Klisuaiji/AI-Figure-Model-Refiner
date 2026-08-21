# AI Figure Model Refiner — Wiki

**AI 手办模型精修器** 是一个 Blender 5.2 LTS 插件，将 AI 生成的 3D 手办模型，通过
**AI 智能体（MCP 接口）+ 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

> 当前版本 **V0.15.1**（全功能工具集模式）：不按固定流程，用户自主编排工作流；
> 打包（每部件 STL → zip）是生产**最后一步**；零散小功能归入末尾「工具集（杂项）」。
> 架构上已移除所有本地 AI 模型（ONNX），改为由外部 **AI 智能体通过 MCP 协议**驱动本插件
> （Blender MCP 兼容）；另接 **ComfyUI** 本地服务做 AI 贴图。

## 快速导航

- [安装 Installation](Installation)
- [架构 Architecture](Architecture)
- [AI 智能体 MCP 接口](AI-Agent-MCP-Interface)
- [使用流程 Usage Workflow](Usage-Workflow)
- [API 参考 MCP Tools](API-Reference)
- [开发 Development](Development)
- [故障排查 Troubleshooting](Troubleshooting)

## 面板 10 段（工具集模式，按需执行）

1. 拆分部件（语义标注 / 拆分 / 填充闭合水密化 / **部件命名**）
2. 头发修正（提取 / 加厚 / 程序化生成）
3. 布料修正（加厚 / 穿插检测与修复）
4. 人物修正（诊断 / 修复 / 多余肢体 / 定向 / 合并 / 装饰物库）
5. 打印计算（FDM 参数 / 可打印性 / 底座 / Voronoi 减重）
6. 连接/拼接部件（圆柱 / 球窝 / 燕尾，零布尔）
7. AI 智能体（MCP 桥）
8. AI 贴图（ComfyUI）
9. **打包导出**（每部件 STL → zip，生产最后一步）
10. **工具集（杂项）**（测量 / 统计 / 水密 / 法线 / 清理 / 对称 / 重命名）

## 项目状态（V0.15.1）

| 阶段 | 范围 | 状态 |
|------|------|------|
| Phase 1-9 | 插件框架 / 诊断 / 可打印性 / 参考图 / 语义识别 / 头发 / 布料 / 底座 / 连接件 / 3MF | ✅ |
| V0.9 | 移除本地模型 → AI 智能体 MCP 接口 | ✅ |
| V0.11 | 半自动零布尔连接（凸柱 + 套筒） | ✅ |
| V0.12 | 工具集 UI（拆分/头发/布料/人物/打印/导出） | ✅ |
| V0.13 | 参考图→多模态智能体 + 协议改 GPL-3.0 | ✅ |
| V0.15 | 10 段面板重排 + 打包(STL+zip) + 工具集杂项 + 程序化发型修复 + ComfyUI 贴图接入 | ✅ |
| V0.15.1 | **部件命名链路**：afr_part_name + 对称 L/R 自动命名 + 命名清单 CSV 导入导出 | ✅ |

## 验收基线（before.fbx → after.zip）

参考素材为「调试案例」：让 `before.fbx` 经插件处理后**持续逼近** `after.zip` 的拆件契约
（命名 `{前缀}-{中文部件名}.stl`，如 `PWY-底座.stl`、`fu-头.stl`）。迭代闭环：
导入 → 部件命名（清单 CSV 或手动）→ 填充闭合 → 打包 STL → zip → 与 after.zip 对照覆盖率。

## 许可证

本项目以 [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html) 发布（详见仓库根目录 `LICENSE`，
全部源码文件带 SPDX 头）。插件本体（Blender 端）零第三方代码依赖，全部使用 Blender 原生 API + Python stdlib；
MCP 服务器运行时需 `mcp` SDK（外部进程）。GPL 许可证下可与 SnapSplit 等 GPL 开源代码互操作引用。
