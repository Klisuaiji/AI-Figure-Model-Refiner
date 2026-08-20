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
    print("=== connector generation test (Phase 10) ===")

    # ---- 1. round (peg + hole), with flange + chamfer ----
    r = C.create_connector(scene, kind="round", position=(0, 0, 0),
                           direction=(0, 0, 1), diameter=5.0, depth=4.0,
                           length=4.0, clearance=0.2, with_flange=True,
                           chamfer=True, name="T_round")
    assert r["male"] and r["female_cutter"], "round: missing parts"
    nm_peg = non_manifold_edges(r["male"])
    nm_hole = non_manifold_edges(r["female_cutter"])
    if nm_peg:
        fails.append("round peg non-manifold edges=%d" % nm_peg)
    if nm_hole:
        fails.append("round hole cutter non-manifold edges=%d" % nm_hole)
    print("  round: peg=%s(%d v) hole=%s(%d v) nonman=%d/%d"
          % (r["male"].name, len(r["male"].data.vertices),
             r["female_cutter"].name, len(r["female_cutter"].data.vertices),
             nm_peg, nm_hole))

    # ---- 2. ball (ball + socket) ----
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

    # ---- 3. dovetail (tab + slot) ----
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

    # ---- 4. carve_socket: cut a hole into a cube ----
    bpy.ops.mesh.primitive_cube_add(size=6.0, location=(0, 0, 3))
    target = bpy.context.active_object
    v_before = len(target.data.vertices)
    # build a hole cutter at the cube top surface
    hole = C.create_connector(scene, kind="round", position=(0, 0, 6.0),
                              direction=(0, 0, 1), diameter=3.0, depth=4.0,
                              length=4.0)["female_cutter"]
    res = C.carve_socket(scene, target, hole, apply=True)
    if not res.get("ok"):
        fails.append("carve_socket (round hole) failed: %s" % res)
    v_after = len(target.data.vertices)
    if v_after <= v_before:
        fails.append("carve_socket did not change target topology "
                     "(v %d -> %d)" % (v_before, v_after))
    print("  carve (round hole): target v %d -> %d, ok=%s"
          % (v_before, v_after, res.get("ok")))

    # ---- 5. carve_socket with ball socket into a cube ----
    bpy.ops.mesh.primitive_cube_add(size=8.0, location=(0, 20, 4))
    target2 = bpy.context.active_object
    v_before2 = len(target2.data.vertices)
    socket = C.create_connector(scene, kind="ball", position=(0, 20, 8.0),
                                direction=(0, 0, 1), diameter=8.0, depth=6.0,
                                clearance=0.2)["female_cutter"]
    res2 = C.carve_socket(scene, target2, socket, apply=True)
    if not res2.get("ok"):
        fails.append("carve_socket (ball socket) failed: %s" % res2)
    print("  carve (ball socket): target v %d -> %d, ok=%s"
          % (v_before2, len(target2.data.vertices), res2.get("ok")))

    # ---- 6. add_connector_between two parts ----
    bpy.ops.mesh.primitive_cube_add(size=3.0, location=(-6, 0, 0))
    part_a = bpy.context.active_object
    bpy.ops.mesh.primitive_cube_add(size=3.0, location=(6, 0, 0))
    part_b = bpy.context.active_object
    res = C.add_connector_between(scene, part_a, part_b, kind="round",
                                  diameter=4.0, depth=3.0, length=3.0,
                                  clearance=0.2, name="T_between")
    if not res.get("carved"):
        fails.append("add_connector_between: no carved info")
    elif not res["carved"].get("ok"):
        fails.append("add_connector_between: carve failed: %s" % res["carved"])
    print("  between: mid=%s carved_ok=%s"
          % (tuple(round(x, 2) for x in res["midpoint"]),
             res.get("carved", {}).get("ok")))

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
