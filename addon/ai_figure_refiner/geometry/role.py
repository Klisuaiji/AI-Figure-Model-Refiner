# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# Phase 9 — role / label heuristic.
#
# The existing 5-class (HAIR/HEAD/BODY/FABRIC/BASE) heuristic in
# ``semantic/parts.py`` is designed for a *single* figure mesh, using
# per-vertex position (z-band + x/y centrality).  For a *scene* of already
# split part objects (the AI-pipeline output: 23 independent meshes, one per
# part), we need a *per-object* role assignment.
#
# Inputs to the per-object heuristic:
#   * bbox dimensions (size_x, size_y, size_z) in world cm.
#   * z centre relative to the whole figure's z range.
#   * bbox aspect ratios (aspect_z_xy = size_z / max(size_x, size_y)).
#   * approximate "shell-ness": a solid-volume / bbox-volume ratio.  A very
#     thin shell (fabric / hair sheet) has a tiny ratio even when solid.
#   * connectivity: objects with 1 connected component and small bbox are
#     usually limbs; large roundish single-component objects are body parts.
#
# The output is the 5-class enum from ``semantic.parts.PART_ID`` (UNLABELED
# if no rule matches) plus a ``confidence`` float in [0, 1].  This lets the
# caller either:
#   * auto-label high-confidence objects (``confidence >= 0.5``) and leave
#     the rest for the brush / vision agent, or
#   * fall back to the existing per-vertex ``apply_heuristics`` on a
#     mis-classified object.
import bpy
from mathutils import Vector


# Tunable thresholds, in cm (figure is ~6-7 cm tall per the before1.fbx
# measurements).  Adjusted for sub-cm figures; for normal-scale figures
# they can be scaled by the longest bbox dimension.
def _scale_thresholds(size_max):
    """Return a dict of thresholds scaled to the figure."""
    s = max(size_max, 1e-3)
    return {
        "base_z_ratio": 0.12,          # bottom 12% of figure = base/plinth
        "hair_z_ratio_low": 0.55,      # top 45% of figure = hair zone
        "head_z_ratio_low": 0.78,      # top 22% = head zone
        "thin_shell_ratio": 0.15,      # vol / bbox_vol < 0.15 = thin sheet
        "very_thin_ratio": 0.04,       # vol / bbox_vol < 0.04 = paper-thin
        "head_size_min": 0.15 * s,     # head bbox dim is at least 15% of fig
        "head_size_max": 0.40 * s,     # head bbox dim ≤ 40% of fig
        "limb_size_max": 0.55 * s,     # a limb is no wider than 55% of fig
        "limb_aspect_min": 1.6,        # limb aspect ≥ 1.6 (long + narrow)
    }


def _bbox_stats(obj):
    """Return (size_x, size_y, size_z), (cx, cy, cz), volume, vertex_count
    from a MESH object, in world space.  Uses mesh.data.vertices directly
    to avoid bmesh access-pattern quirks in Blender 5.2."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    me = obj.data
    if len(me.vertices) == 0:
        return (0, 0, 0), (0, 0, 0), 0.0, 0
    mw = obj.matrix_world
    pts = [mw @ v.co for v in me.vertices]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    mn = (min(xs), min(ys), min(zs))
    mx = (max(xs), max(ys), max(zs))
    size = (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
    center = ((mn[0] + mx[0]) * 0.5,
              (mn[1] + mx[1]) * 0.5,
              (mn[2] + mx[2]) * 0.5)
    bbox_vol = size[0] * size[1] * size[2]
    return size, center, bbox_vol, len(me.vertices)


def _signed_volume_of_mesh(obj):
    """Compute mesh volume via divergence theorem in world space, using
    direct triangle iteration.  Robust to non-manifold faces."""
    if obj is None or obj.type != "MESH":
        return 0.0
    mw = obj.matrix_world
    me = obj.data
    vol = 0.0
    for poly in me.polygons:
        verts = poly.vertices
        if len(verts) < 3:
            continue
        # triangulate n-gon fan from vertex 0
        v0 = mw @ me.vertices[verts[0]].co
        for i in range(1, len(verts) - 1):
            v1 = mw @ me.vertices[verts[i]].co
            v2 = mw @ me.vertices[verts[i + 1]].co
            vol += v0.dot(v1.cross(v2))
    return abs(vol) / 6.0


def _figure_z_range(objects):
    """Return (z_min, z_max) over all mesh objects, using **bbox bottom
    and top** (not centres).  This is the correct "where does the figure
    sit in 3D space" extent — using per-object centres would understate
    the range for objects with large vertical span (e.g. the body)."""
    zmin, zmax = None, None
    for o in objects:
        if o is None or o.type != "MESH":
            continue
        size, _, _, _ = _bbox_stats(o)
        # need a fresh stats call to get bbox mins
        if o is None or o.type != "MESH":
            continue
        me = o.data
        if len(me.vertices) == 0:
            continue
        mw = o.matrix_world
        zs = [(mw @ v.co).z for v in me.vertices]
        if not zs:
            continue
        lo, hi = min(zs), max(zs)
        if zmin is None or lo < zmin:
            zmin = lo
        if zmax is None or hi > zmax:
            zmax = hi
    if zmin is None:
        return 0.0, 1.0
    return zmin, zmax


def classify_object(obj, z_min, z_max, th):
    """Return (label_id, confidence) for a single MESH, using the figure's
    z range ``(z_min, z_max)`` and pre-scaled thresholds ``th``.

    Important: ``_signed_volume_of_mesh`` is only accurate for *closed*
    meshes.  For meshes that are still full of open boundaries (pre-FILL),
    it will drastically under-estimate the volume and any thin_shell rule
    will misfire (a 6cm body might look like 5%-of-bbox thin shell).  We
    therefore detect this condition and short-circuit: an unclosed, large
    bbox object is much more likely a BODY that simply needs filling than
    a 5%-volume fabric sheet.
    """
    size, center, bbox_vol, vcount = _bbox_stats(obj)
    if vcount == 0 or max(size) < 1e-6:
        return 0, 0.0  # UNLABELED, no confidence
    sx, sy, sz = size
    smax = max(size)
    sxy = max(sx, sy)
    vol = _signed_volume_of_mesh(obj)
    shell_ratio = vol / bbox_vol if bbox_vol > 1e-9 else 0.0

    z_range = max(z_max - z_min, 1e-6)
    z_rel = (center[2] - z_min) / z_range  # 0 = bottom, 1 = top

    # Count boundary edges — if many, the mesh is open and the divergence
    # theorem volume is unreliable.  We must build a per-edge face count
    # from polygon edges, because ``MeshEdge`` (mesh.data.edges) does not
    # expose link_faces (that's a bmesh concept only).
    me = obj.data
    edge_face_count = {}
    for poly in me.polygons:
        for ei in poly.edge_keys if hasattr(poly, "edge_keys") else poly.edges:
            # `poly.edge_keys` (set of (v0, v1) tuples) is read-only; for
            # a count we can use `poly.edge_indices` if available,
            # otherwise fall back to per-vertex pair.
            if isinstance(ei, tuple):
                key = tuple(sorted(ei))
            else:
                # `ei` is an edge index; we still need a stable hash key
                # to increment a count.  We index by the int directly
                # and look up later via `me.edges[ei].key`.
                key = ei
            edge_face_count[key] = edge_face_count.get(key, 0) + 1
    n_boundary = sum(1 for c in edge_face_count.values() if c < 2)
    n_edges = max(len(me.edges), 1)
    open_frac = n_boundary / n_edges
    trust_volume = (open_frac < 0.05)  # <5% boundary → trust the volume

    # 1) BASE: low + flat (plinth, base, disc) — shell_ratio is not needed
    if (z_rel <= th["base_z_ratio"] and
            sz / max(sxy, 1e-6) < 0.6 and
            bbox_vol > 1e-6):
        flatness = min(1.0, (sxy * 0.5) / max(sz, 1e-6))
        return 5, min(1.0, 0.55 + flatness * 0.3)  # PART_ID["BASE"]=5

    # 2) HAIR: very top + thin shell + wide
    if (trust_volume and
            z_rel >= th["hair_z_ratio_low"] and
            shell_ratio <= th["thin_shell_ratio"] and
            sxy > sz * 0.7):
        return 1, 0.75  # PART_ID["HAIR"]=1

    # 3) HEAD: very top, round, small/medium, solid
    if (z_rel >= th["head_z_ratio_low"] and
            th["head_size_min"] <= smax <= th["head_size_max"]):
        return 2, 0.70  # PART_ID["HEAD"]=2

    # 4) FABRIC: thin shell (anywhere, but only if volume is trusted
    #    AND the object is small/medium-sized — a 6cm body is never a
    #    fabric sheet, even if holes_fill failed to seal it)
    if (trust_volume and
            shell_ratio <= th["thin_shell_ratio"] and
            z_rel < th["hair_z_ratio_low"] and
            smax < th["limb_size_max"] * 0.85):
        return 4, 0.65  # PART_ID["FABRIC"]=4

    # 4.5) Body-size rescue: a large bbox object that didn't qualify as
    #      BODY above (rule 5) but lives in the mid-z band IS a body,
    #      even if shell_ratio is artificially tiny.  AI-mesh bodies
    #      routinely fail to fully close after holes_fill, so this
    #      prevents them from falling through to UNLABELED.
    if (smax > th["limb_size_max"] * 0.7 and
            z_rel > th["base_z_ratio"] and
            z_rel < th["head_z_ratio_low"]):
        return 3, 0.50  # PART_ID["BODY"]=3

    # 5) BODY: large, central — works for unclosed too (we don't trust
    #    the volume in that case, so just check size and z position)
    if (z_rel > th["base_z_ratio"] and
            z_rel < th["head_z_ratio_low"] and
            smax > th["limb_size_max"] * 0.6):
        return 3, 0.65  # PART_ID["BODY"]=3 (boosted above the rescue 0.50)

    # 6) Fallback: any elongated object → BODY if mid-figure, else UNLABELED
    if (z_rel > th["base_z_ratio"] and
            z_rel < th["head_z_ratio_low"]):
        return 3, 0.35
    return 0, 0.0


def classify_scene(scene, source_obj=None):
    """Classify every MESH in ``scene`` (or just ``source_obj`` if given).
    Returns a list of dicts {name, label_id, label_name, confidence, size,
    center, shell_ratio} for each input.
    """
    objs = ([source_obj] if source_obj is not None
            else [o for o in scene.objects if o.type == "MESH"])
    objs = [o for o in objs if o is not None and o.type == "MESH"]
    if not objs:
        return []
    z_min, z_max = _figure_z_range(objs)
    smax_overall = 0.0
    for o in objs:
        s, _, _, _ = _bbox_stats(o)
        smax_overall = max(smax_overall, max(s))
    th = _scale_thresholds(smax_overall)

    from ..semantic.parts import ID_PART
    out = []
    for o in objs:
        lab_id, conf = classify_object(o, z_min, z_max, th)
        size, center, bbox_vol, _ = _bbox_stats(o)
        vol = _signed_volume_of_mesh(o)
        shell = vol / bbox_vol if bbox_vol > 1e-6 else 0.0
        out.append({
            "name": o.name,
            "label_id": lab_id,
            "label_name": ID_PART.get(lab_id, "UNLABELED"),
            "confidence": round(conf, 3),
            "size": [round(x, 4) for x in size],
            "center": [round(x, 4) for x in center],
            "shell_ratio": round(shell, 3),
        })
    return out


def apply_role_labels(scene, source_obj=None, min_confidence=0.5):
    """Run :func:`classify_scene` and write the per-object ``AFR_Part``
    vertex attribute for high-confidence objects.  Returns the list of
    dicts (one per object processed)."""
    from ..semantic import parts as sem_parts
    rows = classify_scene(scene, source_obj=source_obj)
    objs = {o.name: o for o in scene.objects if o.type == "MESH"}
    for r in rows:
        if r["confidence"] < min_confidence:
            continue
        o = objs.get(r["name"])
        if o is None:
            continue
        sem_parts.ensure_part_attribute(o)
        n = len(o.data.vertices)
        sem_parts.set_label_array(o, [r["label_id"]] * n)
    return rows
