# AI Figure Model Refiner (AI 手办模型精修器)

> 将 AI 生成的 3D 手办模型，通过 **AI 视觉理解 + 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

## 项目状态

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
| 11 | 3MF 导出（自研实现，Blender 5.2 无原生支持） | ✅ |
| 12 | AI Worker 协议（外部 Python，stub fallback） | ✅ |

详见 `报告.md` 与 `CHANGELOG.md`。**28 个算子**在 N 面板。

## 安装

目标：Blender 5.2.0 LTS。

### 开发模式（推荐）

```bash
python scripts/deploy_addon.py
```

然后在 Blender 中：**Edit > Preferences > Add-ons > 搜索 "AI Figure Refiner"** 启用。

> **注意**：Blender 5.2 不自动扫描 `D:/blender/5.2/scripts/addons/`。请将 addon 复制到
> `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\`，或设置环境变量 `BLENDER_USER_SCRIPTS` 包含该目录。

### 测试安装

```bash
blender --background --python scripts/test_smoke.py        # V0.1
blender --background --python scripts/test_printability.py # V0.2
blender --background --python scripts/test_reference.py    # V0.3
blender --background --python scripts/test_semantic.py     # V0.4
blender --background --python scripts/test_phases_5_to_12.py # V0.5
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
8. **布料加厚 / 生成底座 / 合并多部件 / 自动定向** 落地。
9. **导出 3MF**（自研 ZIP+XML，规格合法）。
10. **AI Worker**（外部）— 检查 worker 状态 / Stub 测试。

## 架构

```
addon/ai_figure_refiner/
├── __init__.py            # 注册、Scene 属性、版本
├── core/                  # 日志、错误、会话/快照、Pipeline
├── geometry/              # 诊断、修复、可打印性
├── ui/panel.py            # N-Panel 主面板
├── operators.py           # 28 个算子
├── reference/views.py     # 4 视图 + 相机 + 背景图
├── semantic/parts.py      # 5 部件 + 启发式 + 画笔 + 投票
├── parts_ops/             # 头发/布料/底座/合并/定向
├── exporter/three_mf.py   # 自研 3MF（ZIP+XML）
└── ai_worker/             # JSON-over-stdio 协议 + worker 查找
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

## AI 模型安装

V0.5 已落地协议（Phase 12），但 worker 进程需用户自行配置：

1. 准备 Python venv：`python -m venv workers/venv`
2. 安装依赖：`workers/venv/bin/pip install onnxruntime opencv-python numpy Pillow`
3. 在 `addon/ai_figure_refiner/workers/afr_worker.py` 放 worker 脚本（协议参见 `ai_worker/protocol.py`）
4. 在 Blender 中点击 **N 面板 → AI Worker → 检查 AI Worker 状态**，确认 ok=true。

## 已知限制

- Blender 5.2 **无原生 3MF 导入/导出** — V0.5 已自研导出器（单 object）；导入与多 object 导出 V0.6 再做。
- Blender Python **缺 onnxruntime / opencv / Pillow / trimesh / open3d** — 走外部 Python worker（Phase 12）。
- **无训练数据** — 当前启发式 + 算法已可工作；真实 AI 模型需用户自行训练或下载。
- **Boolean Union 在极端几何上可能失败** — 通用解算器限制；建议先修水密。

## 开源依赖

**V0.5 零第三方代码依赖** — 全部用 Blender 原生 API + Python stdlib 实现。
后续阶段可能引用 `lib3mf` (BSD-2)、3D Print Toolbox (GPL) 等。任何第三方代码复用前都会记录到 `LICENSES.md`。

## License

待定（V1.0 时确定）。当前所有代码为本项目原创。

## Git

- 仓库：`https://github.com/Klisuaiji/AI-Figure-Model-Refiner`
- 分支：`main`
- 提交：7 commits（V0.1-V0.5 完整链路）