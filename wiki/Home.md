# AI Figure Model Refiner — Wiki

**AI 手办模型精修器** 是一个 Blender 5.2 LTS 插件，将 AI 生成的 3D 手办模型，通过
**AI 智能体（MCP 接口）+ 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

> 当前版本 **V0.9** 已移除所有本地 AI 模型（ONNX / onnxruntime / 训练数据导出），
> 改为由外部 **AI 智能体通过 MCP 协议**驱动本插件（Blender MCP 兼容）。

## 快速导航

- [安装 Installation](Installation)
- [架构 Architecture](Architecture)
- [AI 智能体 MCP 接口](AI-Agent-MCP-Interface)
- [使用流程 Usage Workflow](Usage-Workflow)
- [API 参考 MCP Tools](API-Reference)
- [开发 Development](Development)
- [故障排查 Troubleshooting](Troubleshooting)

## 项目状态（V0.9）

| 阶段 | 范围 | 状态 |
|------|------|------|
| Phase 1 | 插件框架（注册/UI/Session/Logging/Settings/Undo） | ✅ |
| Phase 2 | 网格诊断 + 基础修复 | ✅ |
| Phase 2b | 可打印性分析（壁厚/悬垂/悬空/验证） | ✅ |
| Phase 3 | 参考图系统（4 视图 + 相机 + 轮廓） | ✅ |
| Phase 4 | 部件语义识别（5 类 + 启发式 + 画笔） | ✅ |
| Phase 5 | 头发精修（提取 + 加厚 + 程序化生成） | ✅ |
| Phase 6-9 | 布料加厚 / 底座 / 合并 / 自动定向 | ✅ |
| Phase 11 | 3MF 导出（单 object，自研实现） | ✅ |
| V0.6 | 多对象 3MF + Voronoi 微结构 + Slicer CLI + 打包 | ✅ |
| V0.7 | 训练数据导出 + AI Worker 端到端 + 切片端到端 | ✅ |
| V0.8 | 代码审查 + 真实 ONNX 推理骨架 | ✅ |
| V0.9 | 移除本地模型 → AI 智能体 MCP 接口 | ✅ |

## 许可证

本项目以 [MIT License](https://opensource.org/licenses/MIT) 发布（详见仓库根目录 `LICENSE`）。
插件本体（Blender 端）零第三方代码依赖，全部使用 Blender 原生 API + Python stdlib。
