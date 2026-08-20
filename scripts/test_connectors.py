"""Headless test for the connector/joint generation feature (Phase 10).

Run with:
    blender --background --python scripts/test_connectors.py

Validates:
  * all three kinds (round / ball / dovetail) generate a male + female_cutter
  * generated meshes are manifold (no non-manifold edges)
  * carve_socket cuts a cavity into a target mesh (Boolean DIFFERENCE)
  * add_connector_between places a connector and carves into the 2nd part
"""
import os
import sys

# make the addon importable as a package
ADDON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "addon"))
sys.path.insert(0, ADDON_DIR)

import bpy
import bmesh
from ai_figure_refiner.parts_ops import connectors as C


def non_manifold_edges(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def main():
    scene = fresh_scene()
    fails = []
    print("=== connector generation test (V0.11: semi-auto, solver-free) ===")

    # ---- 1. round (peg + socket cup) — the default joint ----
    r = C.create_connector(scene, kind="round", position=(0, 0, 0),
                           direction=(0, 0, 1), diameter=5.0, depth=4.0,
                           length=4.0, clearance=0.2, with_flange=True,
                           chamfer=True, socket_wall_mm=1.2, name="T_round")
    assert r["male"] and r["female_socket"], "round: missing peg/socket"
    nm_peg = non_manifold_edges(r["male"])
    nm_soc = non_manifold_edges(r["female_socket"])
    if nm_peg:
        fails.append("round peg non-manifold edges=%d" % nm_peg)
    if nm_soc:
        fails.append("round socket cup non-manifold edges=%d" % nm_soc)
    print("  round: peg=%s(%d v) socket=%s(%d v) nonman=%d/%d"
          % (r["male"].name, len(r["male"].data.vertices),
             r["female_socket"].name, len(r["female_socket"].data.vertices),
             nm_peg, nm_soc))

    # ---- 2. round must NOT emit a cutter by default (solver-free) ----
    if r.get("female_cutter") is not None:
        fails.append("round should not emit a cutter by default")
    print("  round: female_cutter=None (solver-free) -> %s"
          % (r.get("female_cutter") is None))

    # ---- 3. ball (ball + socket cutter, legacy path) ----
    r = C.create_connector(scene, kind="ball", position=(12, 0, 0),
                           direction=(0, 0, 1), diameter=8.0, depth=6.0,
                           clearance=0.2, opening_ratio=0.7, name="T_ball")
    assert r["male"] and r["female_cutter"], "ball: missing parts"
    nm_soc = non_manifold_edges(r["female_cutter"])
    if nm_soc:
        fails.append("ball socket non-manifold edges=%d" % nm_soc)
    print("  ball: ball=%s socket=%s(%d v) nonman=%d"
          % (r["male"].name, r["female_cutter"].name,
             len(r["female_cutter"].data.vertices), nm_soc))

    # ---- 4. dovetail (tab + slot cutter, legacy path) ----
    r = C.create_connector(scene, kind="dovetail", position=(24, 0, 0),
                           direction=(0, 0, 1), diameter=6.0, depth=5.0,
                           length=5.0, clearance=0.2, name="T_dovetail")
    assert r["male"] and r["female_cutter"], "dovetail: missing parts"
    nm_tab = non_manifold_edges(r["male"])
    nm_slot = non_manifold_edges(r["female_cutter"])
    if nm_tab:
        fails.append("dovetail tab non-manifold edges=%d" % nm_tab)
    if nm_slot:
        fails.append("dovetail slot non-manifold edges=%d" % nm_slot)
    print("  dovetail: tab=%s(%d v) slot=%s(%d v) nonman=%d/%d"
          % (r["male"].name, len(r["male"].data.vertices),
             r["female_cutter"].name, len(r["female_cutter"].data.vertices),
             nm_tab, nm_slot))

    # ---- 5. optional legacy carve: round hole into a cube (manifold target) ----
    bpy.ops.mesh.primitive_cube_add(size=6.0, location=(0, 0, 3))
    target = bpy.context.active_object
    v_before = len(target.data.vertices)
    hole = C.create_connector(scene, kind="round", position=(0, 0, 6.0),
                              direction=(0, 0, 1), diameter=3.0, depth=4.0,
                              length=4.0, legacy_cutter=True)["female_cutter"]
    res = C.carve_socket(scene, target, hole, apply=True)
    if not res.get("ok"):
        fails.append("carve_socket (round hole) failed: %s" % res)
    v_after = len(target.data.vertices)
    if v_after <= v_before:
        fails.append("carve_socket did not change target topology "
                     "(v %d -> %d)" % (v_before, v_after))
    print("  carve (round hole, legacy): target v %d -> %d, ok=%s"
          % (v_before, v_after, res.get("ok")))

    # ---- 6. add_connector_between two parts (solver-free, parented) ----
    bpy.ops.mesh.primitive_cube_add(size=3.0, location=(-6, 0, 0))
    part_a = bpy.context.active_object
    bpy.ops.mesh.primitive_cube_add(size=3.0, location=(6, 0, 0))
    part_b = bpy.context.active_object
    res = C.add_connector_between(scene, part_a, part_b, kind="round",
                                  diameter=4.0, depth=3.0, length=3.0,
                                  clearance=0.2, socket_wall_mm=1.2,
                                  name="T_between")
    if res.get("male") is None or res.get("female_socket") is None:
        fails.append("add_connector_between: missing peg/socket")
    if res.get("parented_to") != (part_a.name, part_b.name):
        fails.append("add_connector_between: wrong parenting %s"
                     % (res.get("parented_to"),))
    if res.get("carved") is not None:
        fails.append("add_connector_between must NOT carve (solver-free)")
    print("  between: mid=%s parented_to=%s"
          % (tuple(round(x, 2) for x in res["midpoint"]),
             res.get("parented_to")))

    # ---- 7. preset sanity ----
    p = C.preset_from_nozzle(0.4)
    assert abs(p["clearance"] - 0.2) < 1e-6, "0.4mm nozzle preset wrong"
    print("  preset(0.4mm): clearance=%.2f diameter=%.1f depth=%.1f"
          % (p["clearance"], p["diameter"], p["depth"]))

    if fails:
        print("\nFAILURES:")
        for f in fails:
            print("  - " + f)
        raise SystemExit(1)
    print("\n== PASS ==")


if __name__ == "__main__":
    main()
