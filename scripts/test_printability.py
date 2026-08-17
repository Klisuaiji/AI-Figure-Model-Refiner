"""Headless test for V0.2 printability analysis.

Verifies:
- analyze_printability returns expected keys.
- Wall thickness on a cube is well above nozzle (solid block).
- A 1mm-thick shell has wall thickness ~1mm.
- A floating separate sphere above a cube is detected as floating.
- Overhang detection flags a tilted box top.
- Validation issues are categorized by severity.
"""
import json
import sys
import os

# --- ensure addon is on path & registered ------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "addon")
sys.path.insert(0, ADDON)

import bpy
import bmesh
from mathutils import Vector

# wipe scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# enable addon (path + manual fallback since Blender 5.2 won't auto-scan
# D:/blender/5.2/scripts/addons/)
USER_SCRIPTS = os.path.join(os.path.expanduser("~"), "AppData", "Roaming",
                            "Blender Foundation", "Blender", "5.2",
                            "scripts", "addons")
try:
    bpy.utils.script_path_add(USER_SCRIPTS) if not ADDON in bpy.utils.script_paths() else None
except Exception:
    pass
if ADDON not in sys.path:
    sys.path.insert(0, ADDON)
try:
    import ai_figure_refiner
    ai_figure_refiner.register()
except Exception as e:
    print("[FATAL register]", e)
    raise


def _new_cube(size=1.0, loc=(0, 0, 0), name="Cube"):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _new_sphere(radius=0.2, loc=(0, 0, 0), name="Sphere"):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc,
                                         segments=16, ring_count=8)
    obj = bpy.context.active_object
    obj.name = name
    return obj


from ai_figure_refiner.geometry import printability as geo_print


def run():
    results = []

    # --- Test 1: solid cube ----------------------------------------------
    cube = _new_cube(size=2.0, loc=(0, 0, 1.0))
    cube.name = "SolidCube"
    r = geo_print.analyze_printability(cube, min_wall_mm=0.8, nozzle_mm=0.4)
    results.append({
        "name": "solid_cube",
        "min_wall_mm": round(r["wall_thickness"]["min_mm"], 3),
        "watertight": r["diagnostics_summary"]["watertight"],
        "printable": r["validation"]["printable"],
        "floating_count": r["floating"]["floating_count"],
        "overhang_pct": round(r["overhang"]["overhang_area_pct"], 2),
    })
    assert r["wall_thickness"]["min_mm"] > 1.5, "solid cube min wall should be ~2mm, got %s" % r["wall_thickness"]["min_mm"]
    assert r["diagnostics_summary"]["watertight"] is True
    assert r["floating"]["floating_count"] == 0
    assert r["validation"]["printable"] is True, "solid cube should be printable"

    # --- Test 2: thin cube (wall 1mm vs target 1.5mm) --------------------
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    thin = _new_cube(size=1.0, loc=(0, 0, 0.5))
    thin.name = "ThinCube"
    r = geo_print.analyze_printability(thin, min_wall_mm=1.5, nozzle_mm=0.4)
    results.append({
        "name": "thin_cube",
        "min_wall_mm": round(r["wall_thickness"]["min_mm"], 3),
        "avg_wall_mm": round(r["wall_thickness"]["avg_mm"], 3),
        "below_threshold_faces": r["wall_thickness"]["below_threshold_faces"],
        "printable": r["validation"]["printable"],
        "issues": r["validation"]["issues"],
    })
    # 1mm cube casting inward → distance to opposite face ~1.0mm,
    # which is below the 1.5mm target.
    assert r["wall_thickness"]["min_mm"] < 1.1, "thin cube min wall should be ~1mm, got %s" % r["wall_thickness"]["min_mm"]
    assert r["wall_thickness"]["min_mm"] > 0.9, "thin cube min wall should be ~1mm, got %s" % r["wall_thickness"]["min_mm"]
    assert r["wall_thickness"]["below_threshold_faces"] > 0
    assert r["validation"]["printable"] is False, "thin cube under 1.5mm should fail validation"

    # --- Test 3: floating separate sphere -------------------------------
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    base = _new_cube(size=2.0, loc=(0, 0, 1.0))
    base.name = "Base"
    sphere = _new_sphere(radius=0.3, loc=(1.5, 0, 2.0))
    sphere.name = "FloatingSphere"
    # join both into one object so analyze_printability sees 2 components
    bpy.ops.object.select_all(action="DESELECT")
    base.select_set(True)
    sphere.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = "WithFloating"
    r = geo_print.analyze_printability(joined, min_wall_mm=0.8, nozzle_mm=0.4)
    results.append({
        "name": "with_floating_sphere",
        "floating_count": r["floating"]["floating_count"],
        "floating_verts": r["floating"]["floating_verts"],
        "total_components": r["floating"]["total_components"],
        "printable": r["validation"]["printable"],
        "issues": r["validation"]["issues"],
    })
    assert r["floating"]["floating_count"] == 1, "expected 1 floating component (sphere), got %d" % r["floating"]["floating_count"]
    assert r["floating"]["total_components"] == 2, "expected 2 components, got %d" % r["floating"]["total_components"]
    assert r["validation"]["printable"] is False

    # --- Test 4: tilted box - overhang detection ------------------------
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    cube = _new_cube(size=1.0, loc=(0, 0, 0.5))
    cube.name = "TiltedCube"
    # 60° around X — one side face's normal rotates into the lower
    # hemisphere (n.z ≈ -0.866), well past the 45° overhang threshold.
    cube.rotation_euler = (1.047, 0, 0)
    bpy.context.view_layer.update()
    r = geo_print.analyze_printability(cube, min_wall_mm=0.8, nozzle_mm=0.4,
                                       overhang_angle_deg=45.0)
    results.append({
        "name": "tilted_cube_60deg",
        "overhang_pct": round(r["overhang"]["overhang_area_pct"], 2),
        "overhang_faces": r["overhang"]["overhang_faces"],
        "printable": r["validation"]["printable"],
        "issues": r["validation"]["issues"],
    })
    assert r["overhang"]["overhang_faces"] > 0, "60° tilted cube should have overhang faces"

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("== PASS ==")


run()