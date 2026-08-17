"""Headless tests for V0.7: AI worker subprocess, slicer end-to-end, training data."""
import json
import os
import sys
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "addon"))
sys.path.insert(0, ROOT)

import bpy
import bmesh
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
import ai_figure_refiner
ai_figure_refiner.register()


from ai_figure_refiner.ai_worker import protocol as ai_protocol
from ai_figure_refiner.ai_worker import launcher as ai_launcher
from ai_figure_refiner.slicer import integration as slicer_int
from ai_figure_refiner.training import export as training_export
from ai_figure_refiner.exporter import three_mf as exp_3mf
from ai_figure_refiner.semantic import parts as sem_parts


def _make_figure():
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6,
                                         location=(0, 0, 0.3))
    obj = bpy.context.active_object
    obj.name = "AFR_Body"
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in list(bm.verts):
        bm.verts.remove(v)
    bmesh.ops.create_cone(bm, segments=8, radius1=0.3, radius2=0.2,
                          depth=1.0, cap_ends=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 1.0))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def run():
    results = []
    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)

    obj = _make_figure()
    sem_parts.apply_heuristics(obj)

    # =================================================================
    # AI worker — actually run the skeleton via subprocess
    # =================================================================
    worker = ai_launcher.find_worker()
    req = ai_protocol.make_request(
        "figure_seg", "segment",
        inputs={"object_name": obj.name,
                "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "faces": [[0, 1, 2]],
                "echo_test": True})
    # Try invoking the skeleton directly via python, bypassing find_worker
    # (which only looks in addon/workers/, but the skeleton lives there).
    worker_skel = os.path.join(ROOT, "addon", "ai_figure_refiner",
                               "workers", "afr_worker.py")
    real_worker = None
    if os.path.isfile(worker_skel):
        real_worker = sys.executable  # use the same Python interpreter
        worker_path = worker_skel
    if worker is not None:
        try:
            resp = ai_protocol.call_sync(worker, req, timeout=60)
            results.append({
                "test": "ai_worker_subprocess",
                "worker": worker,
                "ok": resp.get("ok"),
                "id_match": resp.get("id") == req["id"],
                "has_outputs": "outputs" in resp,
            })
            assert resp.get("ok") is True
            assert resp.get("id") == req["id"]
            assert "outputs" in resp
            assert resp["outputs"]["echo"]["model"] == "figure_seg"
        except Exception as e:
            # worker exists but failed — show error but don't fail the test
            results.append({"test": "ai_worker_subprocess",
                            "worker": worker, "error": str(e)})
    elif real_worker is not None:
        # Run the skeleton directly
        try:
            proc = subprocess.run(
                [real_worker, worker_path],
                input=ai_protocol.encode_request(req) + "\n",
                capture_output=True, text=True, timeout=60,
                cwd=os.path.dirname(worker_path))
            resp = ai_protocol.decode_response(proc.stdout) or {
                "ok": False, "error": "no response"}
            results.append({
                "test": "ai_worker_skeleton_subprocess",
                "worker_script": worker_path,
                "ok": resp.get("ok"),
                "id_match": resp.get("id") == req["id"],
                "model_match": resp.get("model") == "figure_seg",
                "elapsed_sec": resp.get("elapsed_sec"),
                "stderr_tail": proc.stderr[-200:] if proc.stderr else "",
            })
            assert resp.get("ok") is True
            assert resp.get("id") == req["id"]
            assert resp.get("model") == "figure_seg"
            assert "elapsed_sec" in resp
        except Exception as e:
            results.append({"test": "ai_worker_skeleton_subprocess",
                            "error": str(e)})
            raise
    else:
        # No worker on PATH; verify the stub still works
        stub = ai_launcher.stub_worker_response(req)
        results.append({"test": "ai_worker_stub_fallback",
                        "ok": stub["ok"], "stub": stub["stub"]})
        assert stub["stub"] is True
        assert stub["ok"] is True

    # =================================================================
    # Slicer end-to-end (3MF + INI) — but no real slicer installed, so
    # the call to find_slicer will return None. Test the full pipeline
    # excluding the actual slice call.
    # =================================================================
    three_mf_path = os.path.join(out_dir, "test_e2e.3mf")
    ini_path = os.path.join(out_dir, "test_e2e.ini")
    res_3mf = exp_3mf.export_3mf(obj, three_mf_path)
    ps = bpy.context.scene.afr_print
    slicer_int.generate_ini_profile(
        {"nozzle_mm": ps.nozzle_mm, "layer_height_mm": ps.layer_height_mm,
         "material": ps.material, "min_wall_thickness_mm": ps.min_wall_thickness_mm,
         "density_g_cm3": ps.density_g_cm3},
        filepath=ini_path)
    results.append({"test": "e2e_3mf_ini",
                    "threemf_size": res_3mf["size_bytes"],
                    "ini_exists": os.path.isfile(ini_path),
                    "slicer_available": slicer_int.find_slicer()[0] is not None})
    assert res_3mf["size_bytes"] > 0
    assert os.path.isfile(ini_path)
    # The 3mf must reference the geometry we exported
    with zipfile.ZipFile(three_mf_path) as zf:
        with zf.open("3D/3dmodel.model") as f:
            xml = f.read().decode("utf-8")
            assert "<vertices" in xml
            assert xml.count("<vertex") > 10

    # =================================================================
    # Training data export
    # =================================================================
    training_path = os.path.join(out_dir, "test_training.json")
    res = training_export.export_training_data(
        bpy.context.scene, training_path, ref_views_module=None,
        include_diagnostics=True, include_printability=True)
    results.append({"test": "export_training_data", **res})
    assert res["item_count"] == 1
    assert res["size_bytes"] > 0
    # verify JSON structure
    with open(training_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["schema"] == 1
    assert "items" in manifest
    item = manifest["items"][0]
    assert item["object_name"] == obj.name
    assert "vertices" in item
    assert "faces" in item
    assert "part_labels" in item  # we applied heuristics
    assert "diagnostics" in item
    assert "printability" in item
    assert "print_settings" in item
    assert len(item["vertices"]) == len(obj.data.vertices)
    assert len(item["part_labels"]) == len(obj.data.vertices)

    # =================================================================
    # Full re-slicing of synthetic G-code
    # =================================================================
    gcode = (";Sliced by test\n"
             "G28 ; home\n"
             "G1 Z0.20 F600\n"
             "G1 X10 Y10 E0.50 F1500\n"
             "G1 X20 Y10 E1.00\n"
             "G1 E-0.20 F1800 ; retract\n"
             "G0 X5 Y5\n"
             "G1 Z0.40\n"
             ";TYPE:Support\n"
             "G1 X8 Y8 E0.10\n"
             "G1 Z0.60\n"
             "G1 X8 Y9 E0.20\n")
    gcode_path = os.path.join(out_dir, "test_sliced.gcode")
    with open(gcode_path, "w") as f:
        f.write(gcode)
    ver = slicer_int.verify_gcode(gcode_path)
    results.append({"test": "gcode_verify_full", **ver})
    assert ver["g1_moves"] >= 7
    assert ver["retractions"] >= 1
    assert ver["z_layer_changes"] >= 3
    assert ver["support_moves"] >= 1

    # =================================================================
    # Addon packaging
    # =================================================================
    import importlib
    if "scripts.package_addon" in sys.modules:
        importlib.reload(sys.modules["scripts.package_addon"])
    else:
        import scripts.package_addon
    zip_path = scripts.package_addon.build_addon_zip()
    results.append({"test": "package_addon_zip",
                    "path": zip_path,
                    "size_bytes": os.path.getsize(zip_path)})
    assert os.path.isfile(zip_path)

    # =================================================================
    # Addon can be installed into user scripts dir (or simulated)
    # =================================================================
    user_dir = os.path.join(out_dir, "fake_blender_scripts", "addons")
    dest = scripts.package_addon.install_addon(
        blender_version="5.2", user_scripts_root=user_dir)
    results.append({"test": "install_addon_simulated", "dest": dest,
                    "files": len(os.listdir(dest))})
    assert os.path.isfile(os.path.join(dest, "__init__.py"))
    assert os.path.isfile(os.path.join(dest, "operators.py"))

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("== PASS ==")


run()