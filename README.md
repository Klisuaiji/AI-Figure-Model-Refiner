# AI Figure Model Refiner (AI 手办模型精修器)

> 将 AI 生成的 3D 手办模型，通过 **AI 视觉理解 + 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

## 项目状态（V0.7）

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
| 11 | 3MF 导出（单 object，自研实现） | ✅ |
| 12 | AI Worker 协议（外部 Python） | ✅ |
| **V0.6** | **多对象 3MF + Voronoi 微结构 + Slicer CLI + 打包** | ✅ |
| **V0.7** | **训练数据导出 + AI Worker 端到端 + 切片端到端** | ✅ |

详见 `报告.md` 与 `CHANGELOG.md`。**37 个算子**在 N 面板，**7 个无头测试脚本全部 PASS**。

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
blender --background --python scripts/test_phases_5_to_12.py # V0.5
blender --background --python scripts/test_v0_6.py         # V0.6
blender --background --python scripts/test_v0_7.py         # V0.7
# 全部输出 "== PASS =="
```

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
12. **AI Worker** — 真实 subprocess 调用 afr_worker.py（V0.7）；用户填 ONNX 推理即生效。
13. **导出训练数据** — schema v1 manifest JSON（V0.7）。

## 架构

```
addon/ai_figure_refiner/
├── __init__.py            # 注册、Scene 属性、版本
├── core/                  # 日志、错误、会话/快照、Pipeline
├── geometry/              # 诊断、修复、可打印性
├── ui/panel.py            # N-Panel 主面板
├── operators.py           # 37 个算子
├── reference/views.py     # 4 视图 + 相机 + 背景图
├── semantic/parts.py      # 5 部件 + 启发式 + 画笔 + 投票
├── parts_ops/             # 头发/布料/底座/合并/定向/Voronoi
├── exporter/              # 3MF 单/多 object/装配
├── slicer/                # PrusaSlicer 集成 + G-code 验证
├── ai_worker/             # JSON-over-stdio 协议 + worker 查找
├── training/              # 训练数据导出 (schema v1)
└── workers/afr_worker.py  # Worker skeleton（用户填 ONNX 推理）
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

## AI 模型安装（V0.7 已实测通过骨架）

1. 准备 Python venv：`python -m venv addon/ai_figure_refiner/workers/venv`
2. 安装依赖：`workers/venv/bin/pip install onnxruntime numpy Pillow opencv-python`
3. 在 `addon/ai_figure_refiner/workers/afr_worker.py` 的 `dispatch()` 里填 ONNX 推理代码（骨架已就绪）
4. 在 Blender 中：**N 面板 → AI Worker → 调用 AI Worker** 即可

协议往返已实测：subprocess 调骨架 → ok=True / id_match / model_match。

## 已知限制

- Blender 5.2 **无原生 3MF 导入** — V0.6 自研导出（单/多/装配）；导入可在 V1.0 加。
- Blender Python **缺 onnxruntime / opencv / Pillow / trimesh / open3d** — 走外部 Python worker（V0.7 协议已通）。
- **无训练数据** — V0.7 提供 schema v1 manifest 导出工具；用户自行采集/标注。
- **Boolean Union 在极端几何上可能失败** — 通用解算器限制；建议先修水密。
- **Voronoi 微结构**：当前是 tent-pole 骨架（线段），需要切片器按线宽挤出成实体管。

## 开源依赖

**V0.7 零第三方代码依赖** — 全部用 Blender 原生 API + Python stdlib 实现。

## License

待定（V1.0 时确定）。当前所有代码为本项目原创。

## Git

- 仓库：`https://github.com/Klisuaiji/AI-Figure-Model-Refiner`
- 分支：`main`
- 提交：10 commits（V0.1-V0.7 完整链路），HEAD = `788ea65`
- 7 个回归测试脚本全部 PASS