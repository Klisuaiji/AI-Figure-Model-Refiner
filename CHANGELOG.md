# Changelog

All notable changes to the **AI Figure Model Refiner** are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-08-17 — V0.1 (First Auditable Release)

### Added

- **Phase 0 — Technical Feasibility Audit** (`报告.md`):
  - Blender 5.2.0 LTS + Python 3.13.13 environment confirmed.
  - `bpy` operator surface enumerated; **no native 3MF** detected → self-implementation path chosen.
  - Python dependency survey: numpy / mathutils / bmesh / gpu / requests present; onnxruntime / opencv / Pillow / trimesh / open3d **absent** → external-worker fallback planned.
  - Open-source candidate list with licenses recorded.
  - 18 mandatory questions answered, V0.1 scope locked, risk matrix documented.

- **Phase 1 — Plugin Framework**:
  - `addon/ai_figure_refiner/__init__.py` — `bl_info`, class registration, Scene properties (`afr_source`, `afr_step`, `afr_log`, `afr_diag_json`, `afr_print`).
  - `core/session.py` — `RepairSession`, `Part`, `Snapshot` with full mesh rollback.
  - `core/logging.py` — Logger mirroring to `bpy.types.Scene.afr_log` + stdout.
  - `core/pipeline.py` — 7-step state machine with `advance` / `back` / `goto`.
  - `core/errors.py` — `AFRError` hierarchy + `safe_run` decorator.
  - `operators.py` — 7 operators:
    - `afr.import_model` (FBX / OBJ / GLB / GLTF / STL / PLY via native importers)
    - `afr.use_selected`
    - `afr.run_diagnostics`
    - `afr.repair_basic`
    - `afr.rollback`
    - `afr.next_step` / `afr.prev_step`
  - `ui/panel.py` — N-Panel in `View3D > Sidebar > AI Figure Refiner`.

- **Phase 2 (first slice) — Geometry Diagnostics & Repair**:
  - `geometry/diagnostics.py` — 12 metrics on transformed BMesh: vertex / edge / face counts, triangle / quad / ngon split, **non-manifold edges**, **boundary edges**, **duplicate vertices**, **zero-area faces**, **bad-normal faces**, **connected components**, **bounding box**, **volume** (divergence theorem), **watertight** flag.
  - `geometry/repair.py` — `repair_basic`: `remove_doubles` + `recalc_face_normals` + `holes_fill`.

- **Tooling**:
  - `scripts/audit_blender_env.py` — Headless Blender API audit script (reproducible Phase 0).
  - `scripts/deploy_addon.py` — Copy addon into `D:/blender/5.2/scripts/addons/`.
  - `scripts/test_smoke.py` — Headless smoke test (`blender --background --python`). Validates diagnostics on cube / plane / broken mesh, repair, rollback, settings, and logs.

### Verified

Headless smoke test (`scripts/test_smoke.py`) result: **PASS**

| Case | Assertion | Result |
|------|-----------|--------|
| Cube | watertight=True, V=8, Q=6, vol=8.0 mm³ | ✅ |
| Plane | watertight=False, boundary=4, non_manifold=4 | ✅ |
| Broken mesh (duplicate vert) | duplicate_vertices=1 | ✅ |
| Basic repair | remove_doubles + recalc_normals + holes_fill | ✅ |
| Rollback | vertex count restored to pre-repair | ✅ |
| Print settings round-trip | nozzle_mm 0.4 → 0.6 persists | ✅ |
| Log capture | 15 entries written | ✅ |
| 7 operators registered | all discoverable | ✅ |

### Known Limitations

- Blender 5.2 does not auto-scan `D:/blender/5.2/scripts/addons/` as a user addon path — `bpy.ops.preferences.addon_enable` did not complete; tests fall back to `import + register()`. Production install needs `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\` or a `BLENDER_USER_SCRIPTS` override.
- No training data (before/after/reference images) provided — end-to-end "AI figure → 3MF" pipeline not yet verifiable.
- 3MF export, AI inference, reference images, semantic segmentation, hair / fabric / base generators, and slicer validation are explicitly deferred to V0.2–V1.0 per the audit report.

[0.1.0]: #010--2026-08-17--v01-first-auditable-release