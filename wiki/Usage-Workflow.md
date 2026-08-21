# 使用流程 Usage Workflow

典型精修流程（以 AI 生成的 3D 手办为例）：

1. **导入模型** — FBX / OBJ / GLB / GLTF / STL / PLY，
   N 面板 → 导入 / 源对象。
2. **运行网格诊断** — 检查水密 / 重复顶点 / 边界边 / 零面积 / 体积 / bbox / 部件数。
3. **基础修复** — 去重 / 法线重算 / 补洞；不满意可回滚到上一步快照。
4. **可打印性分析** — 壁厚（BVH 射线）/ 悬垂 / 悬空部件 / 验证（ERROR/WARNING/INFO）。
5. **创建 4 个参考相机** + 加载参考图（FRONT/BACK/LEFT/RIGHT）— 对齐 bbox / 切视角。
6. **应用几何启发式** 标注 HAIR/HEAD/BODY/FABRIC/BASE — 用户可手工 brush 调整。
7. **头发精修** — 提取 HAIR → 加厚 / 或程序化生成（curl/noise/taper）。
8. **Voronoi 减重** — 内部微结构降低材料消耗。
9. **布料加厚 / 生成底座 / 合并多部件 / 自动定向** 落地。
10. **部件命名（V0.15.1）** — 选中部件 → 输入中文名（如 手/脚/帽子）→「命名选中」或
    一键 L/R；或用「对称自动 L/R」批量成对命名（手→手L/手R）；也可以「导出清单 CSV」→
    填中文名 →「导入清单」批量回填。打包文件名优先使用该部件名。
11. **导出 3MF** — 单 / 多 object / 装配嵌套 components。
12. **调用切片器** — 端到端 3MF → INI → PrusaSlicer/OrcaSlicer → G-code 校验。
13. **打包（生产最后一步）** — 面板输入文件名前缀（如 PWY）→「打包 STL → zip」，
    每个部件一个二进制 STL，命名 `PWY-部件名.stl`，zip 直接交给切片/打印。
14. **AI 智能体（MCP）** — 启动面板中的 "AI 智能体 (MCP)" 桥，或在外部运行 MCP 服务器，
    由 AI 智能体经 Blender MCP 兼容协议驱动本插件完成语义识别 / 头发·布料·底座精修 /
    可打印性决策。
15. **AI 贴图（ComfyUI）** — 插件偏好设置填 ComfyUI Host/Port（默认 127.0.0.1:8188），
    选中网格 →「生成贴图」调用本地 ComfyUI。

## AI 智能体驱动示例

启动桥后，AI 智能体可依次调用（工具名见 [API 参考](API-Reference)）：

- `afr_get_scene_summary` — 了解当前场景有哪些物体、各自顶点数 / 体积。
- `afr_semantic_label` — 对选定物体做几何启发式语义标注。
- `afr_optimize_hair` / `afr_optimize_fabric` / `afr_optimize_base` — 分部件精修。
- `afr_repair_manifold` — 补洞 / 去重 / 重算法线，确保水密可打印。
- `afr_printability` — 评估壁厚 / 悬垂 / 悬空，给出是否可打印的裁决。
- `afr_export_3mf` — 导出最终 3MF 供切片。
