# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# This file is part of the AI Figure Model Refiner (AFR) addon.
# AFR is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# AFR is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with AFR. If not, see <https://www.gnu.org/licenses/>.
"""Phase 3 — fabric / cloth intersection repair.

AI garments often intersect the body (sleeves poking through the torso,
capes clipping the neck). We ray-cast the fabric against the body to find
the penetrating faces, highlight them, then repair by boolean-differencing
the body out of the fabric and re-thickening the cloth to a printable
shell. A vertex push-out fallback is used if the boolean solver fails.
"""
import bpy
import bmesh
from mathutils import Vector

try:
    from mathutils.bvhtree import BVHTree
except Exception:  # pragma: no cover - BVHTree is always present in Blender
    BVHTree = None


def _build_bvh(obj):
    if obj is None or BVHTree is None:
        return None
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        return BVHTree.FromBMesh(bm)
    finally:
        bm.free()


def _point_inside(bvh, point, margin=1e-3, direction=(1.0, 0.0, 0.0)):
    """Ray-cast parity test: True if ``point`` lies *strictly* inside the
    mesh represented by ``bvh``. A small ``margin`` is subtracted from the
    surface distance so vertices that merely *coincide* with the body
    surface (e.g. a boolean cut cap) are NOT counted as inside."""
    if bvh is None:
        return False
    dirv = Vector(direction)
    o = Vector(point) - dirv * 1e-4
    hits = 0
    for _ in range(64):  # bound the loop
        res = bvh.ray_cast(o, dirv, 1e6)
        if res is None or res[0] is None:
            break
        hits += 1
        o = Vector(res[0]) + dirv * 1e-4
    if (hits % 2) != 1:
        return False
    near = bvh.find_nearest(Vector(point))
    if near is None or near[0] is None:
        return True
    # distance from point to nearest body surface
    return (Vector(point) - Vector(near[0])).length > margin


def detect_intersections(fabric_obj, body_obj, max_dist=3.0):
    """Return the set of fabric face indices that actually *interpenetrate*
    the body mesh.

    A face is considered penetrating when at least one of its vertices is
    strictly inside the body (parity test + surface-distance margin). Using
    per-vertex inside-ness (rather than centroid) avoids false positives on
    coarse "spanning" faces and on boolean cut caps that lie flush on the
    body surface.
    """
    if fabric_obj is None or body_obj is None:
        raise ValueError("fabric and body required")
    bvh = _build_bvh(body_obj)
    if bvh is None:
        return set()
    bm = bmesh.new()
    try:
        bm.from_mesh(fabric_obj.data)
        bm.transform(fabric_obj.matrix_world)
        penetrating = set()
        for fi, f in enumerate(bm.faces):
            for v in f.verts:
                if _point_inside(bvh, v.co):
                    penetrating.add(fi)
                    break
        return penetrating
    finally:
        bm.free()


def highlight_intersections(obj, face_indices):
    """Paint the vertices of penetrating faces red (AFR_IsectColor
    attribute, POINT domain — consistent with the other overlay attrs)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    me = obj.data
    attr = me.color_attributes.get("AFR_IsectColor")
    if attr is None:
        attr = me.color_attributes.new(
            name="AFR_IsectColor", type="BYTE_COLOR", domain="POINT")
    n = len(me.vertices)
    rgba = [0, 0, 0, 0] * n
    for fi in face_indices:
        if 0 <= fi < len(me.polygons):
            for vi in me.polygons[fi].vertices:
                base = vi * 4
                rgba[base:base + 4] = [255, 0, 0, 255]
    attr.data.foreach_set("color", rgba)
    me.update()
    obj["afr_isect_faces"] = list(face_indices)


def _resolve_body(scene, fabric_obj):
    """Pick the body mesh: an object whose name contains BODY and isn't the
    fabric; else the largest other mesh in the scene."""
    for o in scene.objects:
        if o is fabric_obj or o.type != "MESH":
            continue
        if "BODY" in o.name.upper():
            return o
    best = None
    for o in scene.objects:
        if o is fabric_obj or o.type != "MESH":
            continue
        if best is None or len(o.data.vertices) > len(best.data.vertices):
            best = o
    return best


def repair_fabric(fabric_obj, body_obj, thickness=0.6, use_boolean=True):
    """Repair intersecting fabric:
       1. (optional) boolean DIFFERENCE (fabric - body) to cut the bulk of
          the buried cloth out,
       2. a robust pass that pushes any *residual* penetrating vertices to
          just outside the body surface (deterministic; handles the thin
          wall faces a boolean solver leaves behind on coplanar overlaps),
       3. recalculate normals and solidify to a printable shell.
    Returns a list of status strings.
    """
    if fabric_obj is None or fabric_obj.type != "MESH":
        raise ValueError("MESH fabric required")
    info = []
    before = len(detect_intersections(fabric_obj, body_obj)) if body_obj else 0
    info.append("intersections before: %d" % before)
    # --- boolean difference (best-effort) ---
    if use_boolean and body_obj is not None:
        bpy.context.view_layer.objects.active = fabric_obj
        mod = None
        try:
            mod = fabric_obj.modifiers.new(name="AFR_FabricFix", type="BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.object = body_obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            info.append("boolean DIFFERENCE applied")
        except Exception as e:
            info.append("boolean failed (%s); relying on push-out" % e)
            if mod is not None:
                try:
                    fabric_obj.modifiers.remove(mod)
                except Exception:
                    pass
    # --- robust cleanup of residual penetrating verts ---
    pushed = _push_out_penetrating(fabric_obj, body_obj, margin=0.05)
    info.append("pushed out %d residual penetrating verts" % pushed)
    # --- normals + shell ---
    bm = bmesh.new()
    try:
        bm.from_mesh(fabric_obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if thickness > 0:
            try:
                bmesh.ops.solidify(
                    bm,
                    geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                    thickness=thickness,
                )
                info.append("solidify: %.2f mm shell" % thickness)
            except Exception as e:
                info.append("solidify skipped: %s" % e)
        bm.to_mesh(fabric_obj.data)
        fabric_obj.data.update()
    finally:
        bm.free()
    after = len(detect_intersections(fabric_obj, body_obj)) if body_obj else 0
    info.append("intersections after: %d" % after)
    return info


def _push_out_penetrating(fabric_obj, body_obj, margin=0.05):
    """Move every fabric vertex that lies *inside* the body to just
    outside the nearest body-surface point, breaking interpenetration
    deterministically. Returns the number of vertices moved."""
    bvh = _build_bvh(body_obj)
    if bvh is None:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(fabric_obj.data)
        bm.transform(fabric_obj.matrix_world)
        moved = 0
        for v in bm.verts:
            if _point_inside(bvh, v.co):
                res = bvh.find_nearest(v.co)
                if res is not None and res[0] is not None:
                    nearest = Vector(res[0])
                    d = v.co - nearest
                    if d.length < 1e-6:
                        d = Vector((0.0, 0.0, 1.0))
                    v.co = nearest + d.normalized() * margin
                    moved += 1
        bm.transform(fabric_obj.matrix_world.inverted())
        bm.to_mesh(fabric_obj.data)
        fabric_obj.data.update()
        return moved
    finally:
        bm.free()
