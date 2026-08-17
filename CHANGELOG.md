# Changelog

All notable changes to the **AI Figure Model Refiner** are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

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

## Project Status (V0.7)

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
| Phase 12 — AI Worker Protocol | ✅ |
| V0.6    — Multi-object 3MF + Voronoi + Slicer CLI + Addon zip | ✅ |
| V0.7    — Training data + AI worker subprocess + Slicer e2e | ✅ |

**10 commits on `main`**, 7 regression test scripts all PASS, 37 operators in N-Panel.