# Changelog

All notable changes to the **AI Figure Model Refiner** are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.9.0] — 2026-08-18 — V0.9 (Remove local models → AI-Agent MCP interface)

### Changed (paradigm shift)

- **Removed all local AI models.** The plugin no longer bundles or depends on any
  in-process AI inference (ONNX / onnxruntime / training data export). AI capability
  is now provided by an external **AI agent** over the **MCP (Model Context Protocol)**
  interface, Blender-MCP compatible.
- `bl_info` version → `(0, 9, 0)`; description updated to the AI-agent / MCP paradigm.
- Top-level `__init__.py` made safe to import **without `bpy`** (so the standalone MCP
  server can import the `mcp` subpackage); `register()`/`unregister()` guard against a
  missing `bpy`.

### Removed

- `addon/ai_figure_refiner/workers/` (incl. `afr_worker.py` + `models/*.onnx`).
- `addon/ai_figure_refiner/ai_worker/` (JSON-over-stdio protocol + launcher).
- `addon/ai_figure_refiner/training/` (schema-v1 training-data export).
- 4 operators: `AFR_OT_AIWorkerCall`, `AFR_OT_AIWorkerCheck`, `AFR_OT_AIStubTest`,
  `AFR_OT_ExportTrainingData`.
- N-Panel "AI Worker" and "训练数据导出" boxes.
- Root `models/` and `assets/` empty dirs.
- `scripts/archive/*` — 50 one-off / local-model-dependent scripts moved here
  (incl. `download_models.py`, `generate_models.py`, `test_v0_7.py`,
  `test_phases_5_to_12.py`, all `process_hair_*` experiments).

### Added

- **`addon/ai_figure_refiner/mcp/`** — AI-agent MCP interface (Blender-MCP compatible):
  - `backend.py` — Blender backend; default connects to Blender MCP socket
    `localhost:9876`, also supports `in-process` mode.
  - `codegen.py` — wraps tool bodies so they run inside Blender and emit an
    `AFR_RESULT` sentinel that is parsed back into a structured result.
  - `tools.py` — pure domain functions (no `bpy` import) covering
    diagnose / repair-manifold / printability / semantic-label / hair / fabric / base /
    merge / export / list-objects / scene-summary.
  - `server.py` — MCP server (FastMCP/MCPServer) registering all tools + CLI `main()`.
  - `bridge.py` — in-addon Blender-MCP-compatible socket bridge the agent connects to.
  - `__init__.py` (safe import), `__main__.py` (`python -m ai_figure_refiner.mcp`).
- **N-Panel "AI 智能体 (MCP)" box** + `AFR_OT_StartMCPServer` / `AFR_OT_StopMCPServer`
  operators to start/stop the in-addon bridge.
- `scripts/run_mcp_server.py` — launcher for the standalone MCP server.
- `scripts/test_mcp.py` — validates MCP tool registration + domain logic (no Blender).

### Fixed

- Latent crash bug in `operators.py`: `AFR_OT_SlicerExportINI` referenced `ps`
  before it was defined (now reads `sc.afr_print` directly). Added the missing
  `import os` (used by `os.path` in `AFR_OT_SlicerSlice3MF`).

### Verified

- `python -m py_compile` on all addon modules + mcp package — OK.
- `scripts/test_mcp.py` — **PASS** (12 MCP tools registered; tool bodies only import
  allowed stdlib / `ai_figure_refiner.*` modules; mock-backend roundtrip returns
  `AFR_RESULT`).
- `semantic/parts.py` `vote_labels` retained as the merge point for AI-agent outputs
  (dependency-free).

---

## [0.8.0] — 2026-08-17 — V0.8 (Code Review + Real ONNX Inference)

### Added

**V0.8a — Code review & fixes (`docs/CODE_REVIEW.md`)**

- 4 critical + 7 major + 12 minor issues identified and fixed.
- 全部 ImportHelper/ExportHelper 加 `bl_options = {"REGISTER", "UNDO"}` (9 算子).
- `voronoi_lattice` 加 `max_attempts = n_seeds * 200` 防 thin-bbox 死循环.
- `verify_gcode` 改流式采样（head + tail 各 100k 行），支持 200MB+ G-code.
- `protocol.call_sync` 自动给 `.py` 路径加 `sys.executable`（跨平台）.
- `protocol.mesh_to_inputs` 加 try/except，返回空 payload + error 而非 raise.
- `logging.py` 区分 `AttributeError`（吞掉）vs 其他（traceback）— 调试更友好.
- `launch_or_message` 暴露完整 `searched` 目录列表.
- `extract_part` 跳过 `len(f.verts) < 3` 的退化面.
- `panel.py` 日志顺序修正（最近在上）.
- `__init__.py` 版本 `(0, 8, 0)`.

**V0.8c — Real ONNX inference pipeline**

- `addon/ai_figure_refiner/workers/afr_worker.py` 重写为真实 ONNX Runtime 推理:
  - 5 supported models (`figure_seg` / `depth` / `normal` / `hair_dense` / `refine`)
  - 自动扫描 `workers/models/*.onnx`
  - 动态读取 ONNX graph 输入名（不再硬编码）
  - 动态维度处理（batch=1 fill）
  - 无 onnxruntime 时返回 `stub=True`（协议兼容）
  - 输出 summary: shape / dtype / min / max / mean / std
- `scripts/generate_models.py`: 用 `onnx` 库生成 2 个真实 ONNX 模型 stub
  - `yolov8n-seg-stub.onnx` (20 KB, YOLOv8 I/O shape, 2 conv+relu+reduce)
  - `mnist-stub.onnx` (30 KB, 784→10 classifier)
  - `onnx.checker.check_model` 验证 + onnxruntime 跑通
- `scripts/download_models.py`: 尝试从 Ultralytics / HuggingFace 下载
  真实预训练 ONNX (v0.0.0 / Kalray)；fallback 优雅
- **依赖**: `onnx` (1.22.0) + `onnxruntime` (1.28.0)，纯 `pip install`

### Verified

- `scripts/test_v0_8.py` — **PASS** (6 用例)
  - `real_onnx_worker_subprocess`: 跑通 `yolov8n-seg-stub`, elapsed=0.024s, output shape (1,160,160)
  - 5 个 supported models 全部 dispatch OK
- `scripts/test_v0_8_blender.py` — **PASS**
  - 36 算子 / 9 file-dialog 全部带 REGISTER,UNDO / version (0,8,0)
- 全部 7 个原有测试脚本 PASS（smoke / printability / reference / semantic / phases_5_12 / v0_6 / v0_7）

---

## [0.7.0] — 2026-08-17 — V0.7 (Training data + AI worker subprocess + Slicer e2e)

### Added

**V0.7 — Training data export** (`training/export.py`)

- Schema v1 manifest JSON for AI training pipelines.
- Per-mesh item with: vertices / faces / part_labels / ref_views /
  print_settings / diagnostics / printability.
- Forward-compatible (consumers can ignore unknown fields).

**V0.7 — Slicer end-to-end**

- `slicer_slice_3mf` operator: 3MF → INI → subprocess slice → G-code verify.
- `verify_gcode` now detects both `E<0` retractions AND `;retract` comment markers.

**V0.7 — AI Worker real subprocess**

- `ai_worker_call` operator: actually invokes the worker via subprocess.
- `afr_worker.py` skeleton tested end-to-end with protocol roundtrip
  (`ok=True`, `id_match=true`, `model_match=true`).
- User only needs to fill the `dispatch()` function with real ONNX
  inference — no Blender-side changes needed.

### Verified

- `scripts/test_v0_7.py` — **PASS** (7 assertions, including real subprocess worker invocation).
- All 7 regression test scripts pass.

---

## [0.6.0] — 2026-08-17 — V0.6 (Multi-object 3MF + Voronoi + Slicer CLI + Addon zip)

### Added

**V0.6 — Multi-object 3MF exporter** (`exporter/three_mf_multi.py`)

- `export_multi_3mf`: per-mesh `<object id='N'>` resources with per-build-item translation.
- `export_assembly_3mf`: nested `<components>` grouping.
- `identity_transform` / `translate_transform` helpers (12-number 3MF row-major matrix).
- De-duplicates by Blender data-block identity.

**V0.6 — Voronoi lightweight lattice** (`parts_ops/voronoi.py`)

- Rejection-sampling of N seed points inside the mesh (BVH ray cast for inside-test).
- Surface-vertex assignment to nearest seed (Euclidean).
- "Tent-pole" polyline skeleton: seed vertex → all cell boundary vertices.
- Slicer-friendly for thin lattice printing.

**V0.6 — Slicer CLI integration** (`slicer/integration.py`)

- `find_slicer` / `find_all_slicers`: detects PrusaSlicer, OrcaSlicer, SuperSlicer, Slic3r, Cura.
- `generate_ini_profile`: Slic3r/PrusaSlicer INI from our FDM settings (4 sections).
- `slice_model`: subprocess wrapper (`--export-gcode --load <ini>`).
- `verify_gcode`: parses G1/G0 moves, retractions, support markers, layer changes.

**V0.6 — Addon packaging** (`scripts/package_addon.py`)

- `build_addon_zip()`: zips `addon/ai_figure_refiner/` as installable .zip.
- `install_addon(blender_version, user_scripts_root)`: copies to
  `%APPDATA%/Blender Foundation/Blender/<ver>/scripts/addons/` on Windows
  or `~/.config/blender/<ver>/scripts/addons/` on Linux/macOS.

### Verified

- `scripts/test_v0_6.py` — **PASS** (8 assertions).

---

## [0.5.0] — 2026-08-17 — V0.5 (Hair / Fabric / Base / Merge / Orient + 3MF + AI Worker)

### Added

**Phases 5-9 — Per-part operations** (`parts_ops/hair.py` + `parts_ops/generic.py`)

- `extract_part`, `solidify_part`, `solidify_fabric`.
- `generate_hair_curves` (procedural strands) + `curves_to_mesh`.
- `detect_intersections` / `detect_floating`.
- `generate_base`, `merge_parts` (boolean union), `auto_orient`.

**Phase 11 — Self-implemented 3MF exporter** (`exporter/three_mf.py`)

- ZIP + 3 XML files per spec; pure stdlib.

**Phase 12 — AI Worker protocol** (`ai_worker/`)

- 5 supported models, JSON-over-stdio schema v1, subprocess wrapper.
- `find_worker` discovery + `stub_worker_response` placeholder.
- `workers/afr_worker.py` example skeleton.

### Verified

- `scripts/test_phases_5_to_12.py` — **PASS** (13 assertions).

---

## [0.4.0] — 2026-08-17 — V0.4 (Semantic Part Recognition)

### Added

**Phase 4 — Semantic part labeling** (`semantic/parts.py`)

- 5 canonical parts + UNLABELED.
- Per-vertex INT attribute + per-vertex BYTE_COLOR overlay.
- Geometry heuristic (BASE/HEAD/HAIR/BODY/FABRIC).
- Brush ops (Apply/Smooth/Flood/Grow/Shrink/Undo).
- Multi-view `vote_labels`.

### Verified

- `scripts/test_semantic.py` — **PASS** (6 assertions).

---

## [0.3.0] — 2026-08-17 — V0.3 (Reference Image System)

### Added

**Phase 3 — Reference images** (`reference/views.py`)

- 4 fixed view slots + 4 cameras + bbox-aligned framing.
- Image datablock loading + camera background attachment.
- Analytical silhouette edges + project_outline.

### Verified

- `scripts/test_reference.py` — **PASS** (7 assertions).

---

## [0.2.0] — 2026-08-17 — V0.2 (Printability Analysis)

### Added

**Phase 2.b — Printability** (`geometry/printability.py`)

- BVHTree wall thickness (per face ±normal ray cast).
- Overhang detection (downward faces excluding bed bottom).
- Floating parts detection.
- Print verdict with severity (ERROR/WARNING/INFO).

### Verified

- `scripts/test_printability.py` — **PASS** (4 assertions).

---

## [0.1.0] — 2026-08-17 — V0.1 (First Auditable Release)

### Added

- **Phase 0 — Technical Feasibility Audit** (`报告.md`).
- **Phase 1 — Plugin Framework** (`core/session.py`, `core/logging.py`,
  `core/pipeline.py`, `core/errors.py`, `operators.py`, `ui/panel.py`).
- **Phase 2 (first slice) — Geometry Diagnostics & Repair**
  (`geometry/diagnostics.py`, `geometry/repair.py`).

### Verified

- Headless smoke test **PASS** (8 assertions).

---

## Project Status (V0.9)

| Phase / Milestone | Status |
|------------------|--------|
| Phase 0  — Technical Feasibility Audit | ✅ |
| Phase 1  — Plugin Framework | ✅ |
| Phase 2  — Mesh Diagnostics + Repair | ✅ |
| Phase 2b — Printability Analysis | ✅ |
| Phase 3  — Reference Image System | ✅ |
| Phase 4  — Semantic Part Recognition | ✅ |
| Phase 5  — Hair Refinement | ✅ |
| Phase 6-9 — Fabric / Base / Merge / Orient | ✅ |
| Phase 11 — 3MF Exporter (single) | ✅ |
| Phase 12 — AI Worker Protocol (V0.7) → **重构为 MCP 接口 (V0.9)** | ✅ |
| V0.6    — Multi-object 3MF + Voronoi + Slicer CLI + Addon zip | ✅ |
| V0.7    — Training data + AI worker subprocess + Slicer e2e | ✅ |
| V0.8    — Code review + real ONNX inference skeleton | ✅ |
| V0.9    — Remove local models → AI-Agent MCP interface | ✅ |

**V0.9 on `main`** — core operators retained; AI capability now via MCP; regression
test scripts PASS; `scripts/test_mcp.py` validates the MCP interface.