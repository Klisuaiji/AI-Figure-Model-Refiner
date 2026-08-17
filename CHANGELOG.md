# Changelog

All notable changes to the **AI Figure Model Refiner** are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.5.0] — 2026-08-17 — V0.5 (Hair / Fabric / Base / Merge / Orient + 3MF + AI Worker)

### Added

**Phases 5-9 — Per-part operations** (`parts_ops/hair.py` + `parts_ops/generic.py`)

- `extract_part(obj, label_id, new_name)` — copy majority-vertex label faces into a new mesh object.
- `solidify_part(obj, thickness)` / `solidify_fabric(obj, thickness)` — `bmesh.ops.solidify` to add uniform wall thickness.
- `generate_hair_curves(scene, params)` — procedural hair strands (curl/noise/taper/seed) as Blender Curves object.
- `curves_to_mesh(curves_obj, radius, segments)` — convert hair curves to a watertight mesh via `bpy.ops.object.convert`.
- `detect_intersections(hair_obj, body_obj)` — BVH ray-cast penetration check.
- `detect_floating(obj, ground_tol)` — faces above the body that don't touch the ground.
- `generate_base(scene, source_obj, radius, height)` — cylindrical base under the source bbox.
- `merge_parts(scene, objects)` — boolean UNION of mesh objects via modifiers.
- `auto_orient(obj)` — translate the object so its bbox min-Z = 0.

**Phase 11 — Self-implemented 3MF exporter** (`exporter/three_mf.py`, pure stdlib)

- Writes `[Content_Types].xml`, `_rels/.rels`, `3D/3dmodel.model` per 3MF spec.
- Uses `zipfile` + `xml.etree.ElementTree`. Triangulates (BEAUTY) and world-transforms the source mesh.
- Single-object export; unit = millimeter; namespace `http://schemas.microsoft.com/3dmanufacturing/core/2015/02`.
- Tested with `scripts/test_phases_5_to_12.py`: 24,190 verts → 50,822 triangles, 668 KB.

**Phase 12 — AI Worker protocol** (`ai_worker/protocol.py` + `ai_worker/launcher.py`)

- 5 supported models: `figure_seg` / `depth` / `normal` / `hair_dense` / `refine`.
- JSON-over-stdio wire schema v1: `make_request` / `encode_request` / `decode_response` / `call_sync` / `mesh_to_inputs`.
- `find_worker` discovers the worker in `addon/ai_figure_refiner/workers/` or on PATH.
- `stub_worker_response` placeholder for offline UX.
- `launch_or_message` diagnostic with hint for setup.

### Added — UI

- 13 new operators (Hair extract/solidify/generate, Fabric solidify, Generate base, Merge selected, Auto orient, Export 3MF, AI worker check, AI stub test).
- New N-Panel sections: 头发精修 / 布料·底座·合并·定向 / 导出 / AI Worker.

### Verified

- `scripts/test_phases_5_to_12.py` — **PASS** (13 assertions covering all phases 5-12).

---

## [0.4.0] — 2026-08-17 — V0.4 (Semantic Part Recognition)

### Added

**Phase 4 — Semantic part labeling** (`semantic/parts.py`)

- 5 canonical parts: HAIR / HEAD / BODY / FABRIC / BASE (+ UNLABELED).
- Per-vertex INT attribute `AFR_Part` (Blender-native storage) + per-vertex BYTE_COLOR overlay `AFR_PartColor`.
- `heuristics_label(obj)`: first-pass geometry heuristic (BASE = bottom 12%, HAIR/HEAD = top 40% with central cross-section split, BODY = rest, FABRIC = downward-tilting faces).
- Brush ops: `brush_apply` (Add/Overwrite/Remove) / `brush_smooth` / `brush_flood` / `brush_grow` / `brush_shrink` / `brush_undo` (per-object 30-step undo stack).
- `vote_labels(views_labels)` — multi-view majority voter (placeholder for AI segmentation input).
- 4 operators + N-Panel "部件语义识别" section.

### Verified

- `scripts/test_semantic.py` — **PASS** (6 assertions: heuristics produces BASE=63 BODY=20 HEAD=4 HAIR=1; attribute + color overlay registered; brush roundtrip; vote_labels correct).

---

## [0.3.0] — 2026-08-17 — V0.3 (Reference Image System)

### Added

**Phase 3 — Reference images** (`reference/views.py`)

- 4 fixed view slots (FRONT/BACK/LEFT/RIGHT) on `Scene.afr_ref_views`.
- `AFR_RefCam_<VIEW>` cameras with preset positions and bbox-aligned re-aiming.
- Image datablock loading + camera background attachment (subtype=BACK, alpha=0.5, FIT).
- `silhouette_edges` (analytical, camera-facing test) + `silhouette_edge_count` / `project_outline`.
- 5 operators + N-Panel "参考图系统" section.

### Verified

- `scripts/test_reference.py` — **PASS** (7 assertions: 4 slots/cameras, bbox-aligned positions, 4 PNG backgrounds, silhouette edges = 6, project_outline returns 6 points, clear works).

---

## [0.2.0] — 2026-08-17 — V0.2 (Printability Analysis)

### Added

**Phase 2.b — Printability** (`geometry/printability.py`)

- Wall thickness via BVHTree ray cast (per face -/+ normal).
- Overhang detection (downward-facing faces excluding bed bottom).
- Floating parts (connected components not touching ground).
- Print verdict with severity (ERROR/WARNING/INFO).
- Pure BMesh/BVHTree; brute-force fallback when BVH unavailable.
- `afr.run_printability` operator + `Scene.afr_print_json` + N-Panel section.

### Verified

- `scripts/test_printability.py` — **PASS** (4 assertions: solid cube printable, thin cube fails validation, cube+sphere detects floating, 60° tilted cube has overhangs).

---

## [0.1.0] — 2026-08-17 — V0.1 (First Auditable Release)

### Added

- **Phase 0 — Technical Feasibility Audit** (`报告.md`).
- **Phase 1 — Plugin Framework** (`core/session.py`, `core/logging.py`, `core/pipeline.py`, `core/errors.py`, `operators.py`, `ui/panel.py`).
- **Phase 2 (first slice) — Geometry Diagnostics & Repair** (`geometry/diagnostics.py`, `geometry/repair.py`).
- Tooling: `scripts/audit_blender_env.py`, `scripts/deploy_addon.py`, `scripts/test_smoke.py`.

### Verified

- Headless smoke test **PASS** (8/8 assertions: cube/plane/broken-mesh diagnostics, repair, rollback, settings, logs, operator registration).

---

## Project Status Summary

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Technical Feasibility Audit | ✅ Complete |
| 1 | Plugin Framework | ✅ Complete |
| 2 | Geometry Diagnostics + Repair | ✅ Complete |
| 2.b | Printability Analysis | ✅ Complete |
| 3 | Reference Image System | ✅ Complete |
| 4 | Semantic Part Recognition | ✅ Complete |
| 5 | Hair Refinement | ✅ Complete |
| 6-9 | Fabric / Base / Merge / Orient | ✅ Complete |
| 11 | 3MF Exporter (self-implemented) | ✅ Complete |
| 12 | AI Worker Protocol (external) | ✅ Complete (worker stub) |

All phases **functional and headless-tested**.