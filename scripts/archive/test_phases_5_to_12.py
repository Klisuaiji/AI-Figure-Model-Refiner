"""Headless tests for Phases 5 (hair), 6-9 (fabric/base/merge/orient), 11 (3MF), 12 (AI worker)."""
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "addon")
sys.path.insert(0, ADDON)

import bpy
import bmesh
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
import ai_figure_refiner
ai_figure_refiner.register()


from ai_figure_refiner.parts_ops import hair as hair_ops
from ai_figure_refiner.parts_ops import generic as generic_ops
from ai_figure_refiner.exporter import three_mf as exp_3mf
from ai_figure_refiner.ai_worker import launcher as ai_launcher
from ai_figure_refiner.ai_worker import protocol as ai_protocol
from ai_figure_refiner.semantic import parts as sem_parts


def _make_figure():
    """Build a synthetic figure with HAIR spikes on a head."""
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6,
                                         location=(0, 0, 0.3))
    obj = bpy.context.active_object
    obj.name = "AFR_Fig"
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in list(bm.verts):
        bm.verts.remove(v)
    bmesh.ops.create_cone(bm, segments=12, radius1=0.4, radius2=0.3,
                          depth=1.6, cap_ends=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 1.4))
    bmesh.ops.create_cone(bm, segments=12, radius1=0.35, radius2=0.25,
                          depth=0.7, cap_ends=True)
    bmesh.ops.translate(bm, verts=list(bm.verts)[-37:], vec=(0, 0, 2.35))
    import math
    for ang in range(0, 360, 45):
        rad = math.radians(ang)
        x = math.cos(rad) * 0.25
        y = math.sin(rad) * 0.25
        bmesh.ops.create_cone(bm, segments=4, radius1=0.05, radius2=0.0,
                              depth=0.5, cap_ends=True)
        spike_verts = list(bm.verts)[-5:]
        bmesh.ops.translate(bm, verts=spike_verts, vec=(x, y, 2.85))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def run():
    results = []
    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)

    # =================================================================
    # Phase 5 — Hair
    # =================================================================
    obj = _make_figure()
    sem_parts.apply_heuristics(obj)

    # extract HAIR into a new object
    hair_obj = hair_ops.extract_part(obj, sem_parts.PART_ID["HAIR"])
    hair_v = len(hair_obj.data.vertices) if hair_obj else 0
    hair_f = len(hair_obj.data.polygons) if hair_obj else 0
    results.append({"test": "hair_extract", "verts": hair_v, "faces": hair_f})
    assert hair_obj is not None
    assert hair_v > 0

    # generate procedural hair curves + convert to mesh
    curves = hair_ops.generate_hair_curves(
        bpy.context.scene,
        dict(scalp_z=2.85, scalp_radius=0.25, count=80,
             length_min=0.3, length_max=0.7, curl=0.4,
             noise=0.3, taper=1.5, seed=42))
    hair_mesh = hair_ops.curves_to_mesh(curves, radius=0.02, segments=3)
    results.append({
        "test": "hair_generate",
        "type": hair_mesh.type,
        "verts": len(hair_mesh.data.vertices),
        "polys": len(hair_mesh.data.polygons),
    })
    assert hair_mesh.type == "MESH"
    assert len(hair_mesh.data.vertices) > 100  # 80 strands * circle of 3 segs ≈ ~480 verts

    # solidify on the extracted hair
    n_before = len(hair_obj.data.vertices)
    hair_ops.solidify_part(hair_obj, thickness=0.2)
    n_after = len(hair_obj.data.vertices)
    results.append({"test": "hair_solidify", "verts_before": n_before,
                    "verts_after": n_after})
    assert n_after > n_before

    # =================================================================
    # Phase 6-9 — fabric, base, merge, orient
    # =================================================================
    # generate_base
    base = generic_ops.generate_base(bpy.context.scene, obj, height=3.0)
    results.append({"test": "generate_base", "type": base.type,
                    "radius_x": base.dimensions.x / 2})
    assert base.type == "MESH"

    # auto_orient
    bpy.context.view_layer.objects.active = obj
    obj.location = (0, 0, 5.0)  # raise to test
    bpy.context.view_layer.update()
    r = generic_ops.auto_orient(obj)
    bpy.context.view_layer.update()
    bbox_world = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    z_min = min(b.z for b in bbox_world)
    obj_loc = list(obj.matrix_world.translation)
    results.append({"test": "auto_orient",
                    "z_min_after": z_min,
                    "obj_location": obj_loc,
                    "applied_offset": r[3:]})
    assert abs(z_min) < 0.01, "z_min=%s after orient (obj loc=%s)" % (z_min, obj_loc)

    # merge_parts: join obj + hair_mesh + base
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    hair_mesh.select_set(True)
    base.select_set(True)
    bpy.context.view_layer.objects.active = obj
    merged = generic_ops.merge_parts(
        bpy.context.scene, [obj, hair_mesh, base], name="AFR_Merged")
    results.append({
        "test": "merge_parts",
        "verts": len(merged.data.vertices),
        "polys": len(merged.data.polygons),
    })
    assert len(merged.data.vertices) > 0
    assert merged.name == "AFR_Merged"

    # solidify_fabric on merged
    n0 = len(merged.data.vertices)
    generic_ops.solidify_fabric(merged, thickness=0.3)
    n1 = len(merged.data.vertices)
    results.append({"test": "solidify_fabric",
                    "verts_before": n0, "verts_after": n1})
    assert n1 > n0

    # =================================================================
    # Phase 11 — 3MF export
    # =================================================================
    out3mf = os.path.join(out_dir, "test_export.3mf")
    info = exp_3mf.export_3mf(merged, out3mf)
    results.append({"test": "export_3mf", **info})
    assert info["size_bytes"] > 0
    assert info["triangles"] > 0
    # verify zip structure
    with zipfile.ZipFile(out3mf) as zf:
        names = zf.namelist()
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "3D/3dmodel.model" in names
        # model file must contain mesh + vertices + triangles
        with zf.open("3D/3dmodel.model") as f:
            xml = f.read().decode("utf-8")
            assert "<vertices" in xml
            assert "<triangles" in xml
            assert "</model>" in xml
    results.append({"test": "3mf_zip_structure_valid", "names": names})

    # =================================================================
    # Phase 12 — AI worker protocol (no actual worker required)
    # =================================================================
    # request/response roundtrip
    req = ai_protocol.make_request(
        "figure_seg", "segment",
        inputs={"object_name": merged.name,
                "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "faces": [[0, 1, 2]]})
    enc = ai_protocol.encode_request(req)
    dec = ai_protocol.decode_response(enc)
    results.append({"test": "ai_protocol_roundtrip",
                    "id_match": dec["id"] == req["id"],
                    "model_match": dec["model"] == req["model"]})
    assert dec["id"] == req["id"]
    assert dec["model"] == req["model"]

    # mesh_to_inputs
    mi = ai_protocol.mesh_to_inputs(merged)
    results.append({"test": "mesh_to_inputs",
                    "verts": len(mi["vertices"]),
                    "faces": len(mi["faces"])})
    assert len(mi["vertices"]) == len(merged.data.vertices)
    assert len(mi["faces"]) == len(merged.data.polygons)

    # launcher diagnostic (no worker on PATH → returns ok=False)
    st = ai_launcher.launch_or_message()
    results.append({"test": "ai_launcher_diagnostic",
                    "ok": st.get("ok"),
                    "has_hint": bool(st.get("hint"))})
    assert "ok" in st
    assert "hint" in st

    # stub response shape
    stub = ai_launcher.stub_worker_response(req)
    results.append({"test": "ai_stub_response",
                    "ok": stub["ok"], "is_stub": stub["stub"]})
    assert stub["stub"] is True

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("== PASS ==")


run()