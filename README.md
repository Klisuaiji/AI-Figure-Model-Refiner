# AI Figure Model Refiner (AI 手办模型精修器)

> 将 AI 生成的 3D 手办模型，通过 **AI 视觉理解 + 几何算法 + 用户确认**，修复为可进入 FDM 3D 打印生产流程的模型。

## 项目状态

| Phase | 范围 | 状态 |
|-------|------|------|
| 0 | Technical Feasibility Audit | ✅ 完成（见 `报告.md`） |
| 1 | Addon 框架（注册 / UI / Session / Logging / Settings / Undo） | ✅ 完成 |
| 2 (首) | 网格诊断（12 项指标）+ 基础修复 + Rollback | ✅ 完成 + 无头测试通过 |

详见 `报告.md` 与 `CHANGELOG.md`。

## 安装

目标：Blender 5.2.0 LTS。

### 开发模式（推荐）

```bash
# 从仓库根目录
python scripts/deploy_addon.py
# 部署到 D:\blender\5.2\scripts\addons\ai_figure_refiner
```

然后在 Blender 中：**Edit > Preferences > Add-ons > 搜索 "AI Figure Refiner"** 启用。

> **注意**：Blender 5.2 不自动扫描 `D:/blender/5.2/scripts/addons/`。如偏好设置中找不到，请将 addon 复制到
> `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\`，或设置环境变量 `BLENDER_USER_SCRIPTS` 包含该目录。

### 测试安装

```bash
blender --background --python scripts/test_smoke.py
# 期望输出: == PASS ==
# 报告: output/test_smoke_result.json
```

## 使用方法

1. 打开 Blender 5.2。
2. 在 3D 视图右侧 **N 面板** 选择 **"AI Figure Refiner"** 选项卡。
3. 点击 **导入模型** 选择 FBX / OBJ / GLB / GLTF / STL / PLY，或 **使用当前选中对象**。
4. 点击 **运行网格诊断** — 结果显示在 UI 日志与 `Scene.afr_diag_json` 中。
5. 点击 **基础修复**（去重 / 法线 / 补洞），如不满意可 **回滚到上一步快照**。
6. 在 **FDM 打印参数** 中调整喷嘴 / 层高 / 材料 / 最低壁厚 / 密度。

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

全部可在 N 面板 **FDM 打印参数** 中修改。

## AI 模型安装

V0.1 不依赖任何 AI 模型。后续 Phase（语义分割、头发重建）将需要：

- **本地**：ONNX Runtime（MIT）— 在独立 Python 环境中通过子进程 / HTTP 与 Blender 通信。
- **模型**：SAM / Depth Anything / `figure_seg.onnx` — 首次使用自动下载到插件目录，不打包进 addon。

## 已知限制

- Blender 5.2 **无原生 3MF 导入/导出** — Phase 11 自研 ZIP + XML 导出器。
- Blender Python **缺 onnxruntime / opencv / Pillow / trimesh / open3d** — AI 阶段使用外部 worker 方案（详见 `报告.md` §11 风险 R2）。
- 无训练数据（before/after/参考图）— 当前仅验证通用网格诊断能力，未对真实 AI 手办做端到端验证。

## 开源依赖

V0.1 **零外部代码依赖**，全部用 Blender 原生 API（bpy + bmesh + numpy 内嵌）实现。
后续阶段可能引用（License 待二次确认）：

| 项目 | License | 用途 |
|------|---------|------|
| lib3mf | BSD-2-Clause | 3MF 加速（可选） |
| 3D Print Toolbox | GPL | 诊断算法参考 |
| CharMorph / MPFB | GPL-3.0 | 人体模板（Phase 6） |
| BlenderGBHTool | 待确认 | 头发重建参考（Phase 5） |

任何第三方代码复用前都会记录到 `LICENSES.md`。

## License

待定（V1.0 时确定）。当前所有代码为本项目原创。

## 贡献

详见 `报告.md` 与 `CHANGELOG.md`。