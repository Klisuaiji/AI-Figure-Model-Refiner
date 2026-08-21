# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# This file is part of the AI Figure Model Refiner (AFR) addon.
#
# Small, self-contained geometry utilities grouped into the final
# "工具集（杂项）" panel. Each function is pure (operates on one mesh
# object) and returns a small result dict so operators can log it.
import bmesh
import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# Measure
# ---------------------------------------------------------------------------
def measure(obj):
    """Return bounding box / dimensions / volume for ``obj`` (world space)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        verts = [v.co for v in bm.verts]
        if not verts:
            return {"verts": 0, "min": (0, 0, 0), "max": (0, 0, 0),
                    "dim": (0, 0, 0), "volume": 0.0}
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        zs = [v.z for v in verts]
        mn = (min(xs), min(ys), min(zs))
        mx = (max(xs), max(ys), max(zs))
        dim = (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
        volume = 0.0
        try:
            volume = abs(bm.calc_volume())
        except Exception:
            volume = 0.0
        return {"verts": len(verts), "min": mn, "max": mx,
                "dim": dim, "volume": volume}
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Rename parts
# ---------------------------------------------------------------------------
def rename_parts(objects, base="Part", start=1):
    """Rename a list of mesh objects to ``{base}_{index}``. Returns count."""
    idx = start
    n = 0
    for o in objects:
        if o is None or o.type != "MESH":
            continue
        o.name = "%s_%d" % (base, idx)
        idx += 1
        n += 1
    return n


def prefix_selected(context, prefix):
    """Prepend ``prefix`` to every selected mesh object's name."""
    n = 0
    for o in context.selected_objects:
        if o.type == "MESH":
            o.name = "%s%s" % (prefix, o.name)
            n += 1
    return n


# ---------------------------------------------------------------------------
# Part naming (the after.zip contract: {prefix}-{中文部件名}.stl)
# ---------------------------------------------------------------------------
def name_part(obj, name, lr=None):
    """Set the printable part name on ``obj``.

    Stores ``obj["afr_part_name"]`` = name (+ L/R suffix if requested). The
    packaging operator prefers this over the raw object name, so a part named
    "手" with lr="R" exports as ``PWY-手R.stl``. Returns the final name.
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    final = name.strip()
    if lr:
        final = "%s%s" % (final, lr.strip().upper())
    obj["afr_part_name"] = final
    return final


def bbox_center(obj):
    """World-space bounding-box center of ``obj``."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        if not bm.verts:
            return Vector((0.0, 0.0, 0.0))
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        return Vector(((min(xs) + max(xs)) / 2,
                       (min(ys) + max(ys)) / 2,
                       (min(zs) + max(zs)) / 2))
    finally:
        bm.free()


def bbox_dims(obj):
    """World-space bounding-box dimensions (w, h, d) of ``obj``."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        if not bm.verts:
            return (0.0, 0.0, 0.0)
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    finally:
        bm.free()


def auto_name_lr(objects, base_name, axis="X", tol_ratio=0.15, left_side="L"):
    """Group mirror-symmetric objects and name them L/R.

    Objects are grouped by similar bounding-box dimensions; pairs whose
    bbox centers are mirrored across the chosen axis (default X) get the
    L/R suffix — the one on the negative side of the axis gets ``left_side``
    (default "L"). Returns a dict {obj.name: final_name}.
    """
    result = {}
    dims_of = {o.name: bbox_dims(o) for o in objects}
    center_of = {o.name: bbox_center(o) for o in objects}
    used = set()

    def dims_close(a, b):
        return all(abs(x - y) <= max(tol_ratio * max(abs(x), abs(y), 1e-6), 1e-3)
                   for x, y in zip(a, b))

    def close(a, b):
        return abs(a - b) < tol_ratio * 2 * max(abs(a), abs(b), 1e-3)

    for o in objects:
        if o.name in used or o.name in result:
            continue
        c = center_of[o.name]
        # find a mirror partner across the axis
        partner = None
        for q in objects:
            if q.name == o.name or q.name in used:
                continue
            if not dims_close(dims_of[o.name], dims_of[q.name]):
                continue
            cq = center_of[q.name]
            # mirror across axis: cross coords close, axis coord opposite sign
            if axis == "X":
                mirror_ok = (close(cq.y, c.y) and close(cq.z, c.z) and
                             cq.x * c.x < 0 and close(abs(cq.x), abs(c.x)))
            elif axis == "Y":
                mirror_ok = (close(cq.x, c.x) and close(cq.z, c.z) and
                             cq.y * c.y < 0 and close(abs(cq.y), abs(c.y)))
            else:
                mirror_ok = (close(cq.x, c.x) and close(cq.y, c.y) and
                             cq.z * c.z < 0 and close(abs(cq.z), abs(c.z)))
            if mirror_ok:
                partner = q
                break
        if partner is not None:
            axis_coord = c.x if axis == "X" else (c.y if axis == "Y" else c.z)
            if axis_coord < 0:
                result[o.name] = name_part(o, base_name, left_side)
                result[partner.name] = name_part(partner, base_name,
                                                 "R" if left_side == "L" else "L")
            else:
                result[partner.name] = name_part(partner, base_name, left_side)
                result[o.name] = name_part(o, base_name,
                                           "R" if left_side == "L" else "L")
            used.add(o.name)
            used.add(partner.name)
        else:
            result[o.name] = name_part(o, base_name)
    return result


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
def cleanup(obj, merge_dist=0.001):
    """Remove loose geometry and merge by distance. Returns True on change."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        before = len(bm.verts)
        # delete loose verts/edges (verts with no linked faces)
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        # remove degenerate faces (zero-area)
        bm.faces.ensure_lookup_table()
        bad = [f for f in bm.faces if f.calc_area() < 1e-9]
        if bad:
            bmesh.ops.delete(bm, geom=bad, context="FACES")
        # merge by distance
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
        bm.to_mesh(obj.data)
        obj.data.update()
        after = len(obj.data.vertices)
        return after != before
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Normals
# ---------------------------------------------------------------------------
def recalc_normals(obj, inside=False):
    """Recalculate normals (outside by default)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if inside:
            for f in bm.faces:
                f.normal_flip()
        bm.to_mesh(obj.data)
        obj.data.update()
        return True
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Symmetry check
# ---------------------------------------------------------------------------
def symmetry_check(obj, axis="X", tol=0.01):
    """Return fraction (0..1) of verts that have a mirrored partner."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        coord = {}
        for v in bm.verts:
            c = list(v.co)
            coord.setdefault(round(c[1], 3), []).append(c)
            coord.setdefault(round(c[2], 3), []).append(c)
        matched = 0
        total = len(bm.verts)
        for v in bm.verts:
            c = v.co
            mirror = list(c)
            if axis == "X":
                mirror[0] = -c[0]
            elif axis == "Y":
                mirror[1] = -c[1]
            else:
                mirror[2] = -c[2]
            # look for a vertex near the mirror position
            found = False
            for key in (round(mirror[1], 3), round(mirror[2], 3)):
                for cand in coord.get(key, []):
                    d = (candidate_dist(cand, mirror))
                    if d < tol:
                        found = True
                        break
                if found:
                    break
            if found:
                matched += 1
        frac = (matched / total) if total else 0.0
        return {"matched": matched, "total": total, "fraction": frac}
    finally:
        bm.free()


def candidate_dist(a, b):
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]))


def make_symmetric(obj, axis="X"):
    """Mirror the +side of the mesh onto the -side (simple overwrite)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        # collect verts by absolute axis coordinate
        pos = {}
        for v in bm.verts:
            c = list(v.co)
            if axis == "X":
                key = round(c[1], 3), round(c[2], 3)
                sign = c[0]
            elif axis == "Y":
                key = round(c[0], 3), round(c[2], 3)
                sign = c[1]
            else:
                key = round(c[0], 3), round(c[1], 3)
                sign = c[2]
            pos.setdefault(key, []).append((sign, v))
        changed = 0
        for key, vals in pos.items():
            if len(vals) < 2:
                continue
            pos_v = [v for s, v in vals if s >= 0]
            neg_v = [v for s, v in vals if s < 0]
            if not pos_v or not neg_v:
                continue
            # use the positive side as source, copy to negative
            src = pos_v[0].co
            for v in neg_v:
                c = list(src)
                if axis == "X":
                    c[0] = -src[0]
                elif axis == "Y":
                    c[1] = -src[1]
                else:
                    c[2] = -src[2]
                v.co = Vector(c)
                changed += 1
        bm.to_mesh(obj.data)
        obj.data.update()
        return changed
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Watertight / manifold check
# ---------------------------------------------------------------------------
def watertight_check(obj):
    """Return dict with boundary-edge count and a watertight bool."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        boundary = [e for e in bm.edges if len(e.link_faces) < 2]
        non_manifold = [e for e in bm.edges if len(e.link_faces) > 2]
        return {"boundary_edges": len(boundary),
                "non_manifold_edges": len(non_manifold),
                "watertight": len(boundary) == 0}
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def stats(obj):
    """Return vertex/face counts and non-manifold edge count."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        non_manifold = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        return {"verts": len(bm.verts), "faces": len(bm.faces),
                "edges": len(bm.edges), "non_manifold_edges": non_manifold}
    finally:
        bm.free()
