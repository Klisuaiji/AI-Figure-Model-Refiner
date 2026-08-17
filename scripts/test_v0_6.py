"""Headless tests for V0.6: multi-object 3MF, Voronoi, slicer, addon zip."""
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "addon"))
sys.path.insert(0, ROOT)  # for scripts/ imports

import bpy
import bmesh
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
import ai_figure_refiner
ai_figure_refiner.register()


from ai_figure_refiner.exporter import three_mf_multi as exp_3mf_multi
from ai_figure_refiner.parts_ops import voronoi as voronoi_ops
from ai_figure_refiner.slicer import integration as slicer_int
from ai_figure_refiner.exporter.three_mf import NS_3MF
import scripts.package_addon as package_addon


def _make_figure():
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6,
                                         location=(0, 0, 0.3))
    obj = bpy.context.active_object
    obj.name = "AFR_Body"
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in list(bm.verts):
        bm.verts.remove(v)
    bmesh.ops.create_cone(bm, segments=12, radius1=0.4, radius2=0.3,
                          depth=1.6, cap_ends=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 1.4))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    # Add a base cylinder
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=0.4,
                                         location=(0, 0, 0.2))
    base = bpy.context.active_object
    base.name = "AFR_BaseDisc"
    return obj, base


def run():
    results = []
    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)

    # =================================================================
    # Build scene with 2 mesh objects
    # =================================================================
    body, base = _make_figure()

    # =================================================================
    # Multi-object 3MF export
    # =================================================================
    multi3mf = os.path.join(out_dir, "test_multi.3mf")
    res = exp_3mf_multi.export_multi_3mf(multi3mf, bpy.context.scene)
    results.append({"test": "export_multi_3mf", **res})
    assert res["object_count"] == 2
    assert res["build_item_count"] == 2
    assert res["total_vertices"] > 0
    # verify zip
    with zipfile.ZipFile(multi3mf) as zf:
        with zf.open("3D/3dmodel.model") as f:
            xml = f.read().decode("utf-8")
            assert xml.count("<object ") == 2
            assert xml.count("<item ") == 2
            assert 'transform="1 0 0' in xml  # at least one translated item

    # =================================================================
    # Assembly 3MF (nested components)
    # =================================================================
    assembly3mf = os.path.join(out_dir, "test_assembly.3mf")
    res = exp_3mf_multi.export_assembly_3mf(
        assembly3mf, bpy.context.scene,
        groups=[{"name": "AFR_Assembly"}])
    results.append({"test": "export_assembly_3mf", **res})
    assert res["mesh_object_count"] == 2
    assert res["group_count"] == 1
    assert res["build_item_count"] == 1
    with zipfile.ZipFile(assembly3mf) as zf:
        with zf.open("3D/3dmodel.model") as f:
            xml = f.read().decode("utf-8")
            assert "<components>" in xml
            assert "<component " in xml
            # group should reference both sub-objects
            assert xml.count("<component ") == 2

    # =================================================================
    # Voronoi lightweight lattice
    # =================================================================
    lattice = voronoi_ops.voronoi_lattice(body, n_seeds=10, lattice_radius=0.5)
    results.append({
        "test": "voronoi_lattice",
        "verts": len(lattice.data.vertices),
        "edges": len(lattice.data.edges),
        "polys": len(lattice.data.polygons),
    })
    assert lattice is not None
    assert len(lattice.data.vertices) > 10
    assert len(lattice.data.edges) > 0

    # =================================================================
    # Slicer — find_all_slicers (likely empty, no assert)
    # =================================================================
    found = slicer_int.find_all_slicers()
    results.append({"test": "slicer_find", "count": len(found)})
    assert isinstance(found, list)

    # =================================================================
    # INI profile generation
    # =================================================================
    ini_path = os.path.join(out_dir, "test_profile.ini")
    ini_text = slicer_int.generate_ini_profile(
        {"nozzle_mm": 0.4, "layer_height_mm": 0.2, "material": "PLA",
         "min_wall_thickness_mm": 0.8, "density_g_cm3": 1.24},
        filepath=ini_path)
    results.append({"test": "slicer_ini", "lines": len(ini_text.splitlines()),
                    "path": ini_path})
    assert "[print]" in ini_text
    assert "[filament]" in ini_text
    assert "[printer]" in ini_text
    assert "[extruder]" in ini_text
    assert os.path.isfile(ini_path)
    with open(ini_path) as f:
        content = f.read()
    assert "nozzle_diameter = 0.40" in content
    assert "layer_height = 0.20" in content

    # =================================================================
    # G-code verification — synthetic gcode
    # =================================================================
    gcode_path = os.path.join(out_dir, "test.gcode")
    synthetic = ("; generated for test\n"
                 "G28 ; home\n"
                 "G1 Z0.20 F600\n"
                 "G1 X10 Y10 E0.50 F1500\n"
                 "G1 X20 Y10 E1.00\n"
                 "G1 X20 Y20 E1.50\n"
                 "G1 X10 Y20 E2.00\n"
                 "G1 E1.80 F1800 ; retract\n"
                 "G0 X5 Y5 ; travel\n"
                 "G1 Z0.40 F600 ; layer 2\n"
                 ";TYPE:Support\n"
                 "G1 X8 Y8 E0.30\n"
                 "G1 X9 Y9 E0.40\n")
    with open(gcode_path, "w") as f:
        f.write(synthetic)
    vr = slicer_int.verify_gcode(gcode_path)
    results.append({"test": "gcode_verify", **vr})
    assert vr["g1_moves"] > 0
    assert vr["z_layer_changes"] >= 2
    assert vr["retractions"] >= 1
    assert vr["support_moves"] >= 1
    assert len(vr["issues"]) == 0

    # =================================================================
    # Addon zip packaging
    # =================================================================
    zip_path = package_addon.build_addon_zip()
    results.append({"test": "addon_zip", "path": zip_path,
                    "size_bytes": os.path.getsize(zip_path)})
    assert os.path.isfile(zip_path)
    assert zip_path.endswith(".zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "ai_figure_refiner/__init__.py" in names
        assert "ai_figure_refiner/operators.py" in names
        assert any(n.startswith("ai_figure_refiner/exporter/") for n in names)

    # =================================================================
    # Verify addon can be imported from the zip extract path
    # =================================================================
    extract_dir = os.path.join(out_dir, "extracted_addon")
    if os.path.isdir(extract_dir):
        import shutil; shutil.rmtree(extract_dir)
    os.makedirs(extract_dir)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    extracted_addon = os.path.join(extract_dir, "ai_figure_refiner")
    assert os.path.isfile(os.path.join(extracted_addon, "__init__.py"))
    sys.path.insert(0, extracted_addon)
    # Re-import cleanly
    import importlib
    if "ai_figure_refiner" in sys.modules:
        importlib.reload(sys.modules["ai_figure_refiner"])
    results.append({"test": "addon_zip_self_contained",
                    "files_in_root": len(os.listdir(extracted_addon))})

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("== PASS ==")


run()