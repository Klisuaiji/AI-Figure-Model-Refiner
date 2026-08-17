"""Headless test for V0.4 semantic part recognition."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "addon")
sys.path.insert(0, ADDON)

import bpy
import bmesh
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
import ai_figure_refiner
ai_figure_refiner.register()


from ai_figure_refiner.semantic import parts as sem_parts


def _make_figure_like():
    """Build a synthetic 'figure': base + body + head + hair spikes,
    so the heuristic has clearly-distinct vertical zones to label.
    Returns the mesh object.
    """
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6,
                                         location=(0, 0, 0.3))
    base = bpy.context.active_object
    base.name = "AFR_Figure"
    bm = bmesh.new()
    bm.from_mesh(base.data)
    # body (sphere 0..2)
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5)
    # scale the upper half (z>0) into a head + body shape
    # simpler: delete current verts and add a few primitives manually
    for v in list(bm.verts):
        bm.verts.remove(v)
    # Body (cylinder-like)
    bmesh.ops.create_cone(bm, segments=12, radius1=0.4, radius2=0.3,
                          depth=1.6, cap_ends=True)
    # shift up so its bottom sits at z=0.6 (above base)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.6 + 0.8))
    # Head (smaller sphere) above body
    head_verts = [v for v in bm.verts]
    # Add sphere vertices: easiest is to insert two cones then merge
    # Simpler: add a small cone as head
    bmesh.ops.create_cone(bm, segments=12, radius1=0.35, radius2=0.25,
                          depth=0.7, cap_ends=True)
    bmesh.ops.translate(bm, verts=list(bm.verts)[-len(head_verts):],
                        vec=(0, 0, 2.0 + 0.35))
    # Hair: a few spike cones on top of head
    for ang in range(0, 360, 45):
        import math
        rad = math.radians(ang)
        x = math.cos(rad) * 0.25
        y = math.sin(rad) * 0.25
        bmesh.ops.create_cone(bm, segments=4, radius1=0.05, radius2=0.0,
                              depth=0.5, cap_ends=True)
        spike_verts = list(bm.verts)[-5:]
        bmesh.ops.translate(bm, verts=spike_verts, vec=(x, y, 2.5))
    bm.to_mesh(base.data)
    bm.free()
    base.data.update()
    return base


def run():
    results = []

    # --- Test 1: heuristics_label on figure-like mesh ---------------
    obj = _make_figure_like()
    labels = sem_parts.apply_heuristics(obj)
    n = len(labels)
    from collections import Counter
    cnt = Counter(sem_parts.ID_PART[l] for l in labels)
    results.append({
        "test": "heuristics_label",
        "vertex_count": n,
        "label_counts": dict(cnt),
    })
    # we expect at least one HAIR, one HEAD, one BODY, one BASE
    assert cnt.get("HAIR", 0) > 0, "expected hair"
    assert cnt.get("HEAD", 0) > 0, "expected head"
    assert cnt.get("BODY", 0) > 0, "expected body"
    assert cnt.get("BASE", 0) > 0, "expected base"

    # --- Test 2: attribute is on mesh data --------------------------
    attr = obj.data.attributes.get(sem_parts.ATTR_NAME)
    assert attr is not None
    assert attr.domain == "POINT"
    results.append({"test": "attribute_registered", "name": attr.name,
                    "type": attr.data_type, "domain": attr.domain})

    # --- Test 3: color overlay created ------------------------------
    color_attr = obj.data.color_attributes.get("AFR_PartColor")
    assert color_attr is not None
    results.append({"test": "color_overlay", "name": color_attr.name})

    # --- Test 4: brush_flood sets all to BODY -----------------------
    sem_parts.brush_flood(obj, sem_parts.PART_ID["BODY"])
    labels2 = sem_parts.get_label_array(obj)
    assert all(l == sem_parts.PART_ID["BODY"] for l in labels2)
    results.append({"test": "brush_flood_body", "all_body": True})

    # --- Test 5: brush_undo reverts to previous ---------------------
    prev = sem_parts.brush_undo(obj)
    assert prev is not None
    labels3 = sem_parts.get_label_array(obj)
    # after undo the labels should match what we had before the flood
    assert labels3 == labels
    results.append({"test": "brush_undo", "matches_previous": True})

    # --- Test 6: vote_labels (placeholder for multi-view AI) -------
    v1 = [sem_parts.PART_ID["HAIR"]] * 5 + [sem_parts.PART_ID["BODY"]] * 5
    v2 = [sem_parts.PART_ID["BODY"]] * 5 + [sem_parts.PART_ID["BODY"]] * 5
    v3 = [sem_parts.PART_ID["HAIR"]] * 5 + [sem_parts.PART_ID["HAIR"]] * 5
    voted = sem_parts.vote_labels([v1, v2, v3])
    results.append({"test": "vote_labels", "result": voted})
    # first 5 should be HAIR (v1+v3 vote HAIR), last 5 should be HAIR (v3) or BODY (v1+v2)
    assert voted[0] == sem_parts.PART_ID["HAIR"]
    # last 5: v1=BODY, v2=BODY, v3=HAIR → tie BODY vs HAIR → first (BODY)
    assert voted[9] == sem_parts.PART_ID["BODY"]

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("== PASS ==")


run()