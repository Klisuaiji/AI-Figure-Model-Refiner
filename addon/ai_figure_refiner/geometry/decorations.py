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
"""Phase 4 — decorative asset library.

Manages a small built-in catalogue of figure decorations (earrings,
necklaces, crowns, swords, ...) defined as primitive combos in
``assets/decorations.json``. Each decoration is built from bmesh primitives
(no external .blend dependency) and snapped to a named attach point on the
body (head / neck / chest / wrists / waist) using the body bounding box.
"""
import bpy
import bmesh
import json
import math
import os
from mathutils import Matrix, Vector

MANIFEST = os.path.join(
    os.path.dirname(__file__), "..", "assets", "decorations.json")


def _load_manifest():
    try:
        with open(MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"decorations": []}


def list_decorations():
    """Return list of {name, attach} dicts for the UI enum."""
    out = []
    for d in _load_manifest().get("decorations", []):
        out.append({"name": d.get("name", "?"),
                    "attach": d.get("attach", "chest")})
    return out


def get_decoration(name):
    for d in _load_manifest().get("decorations", []):
        if d.get("name") == name:
            return d
    return None


def _build_torus(bm, mat, major_radius, minor_radius, segments, ring_segments):
    """Manually construct a torus (bmesh.ops has no create_torus in 5.x).
    ``mat`` is applied to every generated vertex so the ring can be offset."""
    verts = []
    for i in range(segments):
        u = 2.0 * 3.141592653589793 * i / segments
        for j in range(ring_segments):
            v = 2.0 * 3.141592653589793 * j / ring_segments
            x = (major_radius + minor_radius * math.cos(v)) * math.cos(u)
            y = (major_radius + minor_radius * math.cos(v)) * math.sin(u)
            z = minor_radius * math.sin(v)
            co = mat @ Vector((x, y, z))
            verts.append(bm.verts.new(co))
    for i in range(segments):
        for j in range(ring_segments):
            a = verts[i * ring_segments + j]
            b = verts[((i + 1) % segments) * ring_segments + j]
            c = verts[((i + 1) % segments) * ring_segments + (j + 1) % ring_segments]
            d = verts[i * ring_segments + (j + 1) % ring_segments]
            bm.faces.new((a, b, c, d))


def _build_part(bm, part):
    prim = part.get("primitive")
    p = part.get("params", {})
    loc = part.get("location", [0.0, 0.0, 0.0])
    mat = Matrix.Translation(Vector(loc))
    if prim == "torus":
        _build_torus(bm, mat,
                     p.get("major_radius", 1.0),
                     p.get("minor_radius", 0.3),
                     p.get("segments", 24),
                     p.get("ring_segments", 8))
    elif prim == "sphere":
        bmesh.ops.create_uvsphere(
            bm, matrix=mat,
            radius=p.get("radius", 1.0),
            u_segments=p.get("u_segments", 16),
            v_segments=p.get("v_segments", 12))
    elif prim == "box":
        sc = p.get("scale", [1.0, 1.0, 1.0])
        sm = Matrix.Diagonal(Vector((sc[0], sc[1], sc[2], 1.0)))
        bmesh.ops.create_cube(bm, size=p.get("size", 1.0), matrix=mat @ sm)
    elif prim == "cone":
        bmesh.ops.create_cone(
            bm, matrix=mat,
            radius1=p.get("radius1", 0.5),
            radius2=p.get("radius2", 0.0),
            depth=p.get("depth", 1.0),
            segments=p.get("segments", 16),
            cap_ends=True, cap_tris=False)
    elif prim == "cylinder":
        r = p.get("radius", 0.5)
        bmesh.ops.create_cone(
            bm, matrix=mat,
            radius1=r, radius2=r,
            depth=p.get("depth", 1.0),
            segments=p.get("segments", 16),
            cap_ends=True, cap_tris=False)
    else:
        raise ValueError("unknown primitive: %s" % prim)


def _attach_point(body_obj, attach):
    """World-space point for the given attach slot, derived from the body
    bounding box. Coordinate convention: +X right, +Y back, +Z up (Blender
    default). 'front' of the figure faces -Y."""
    if body_obj is None:
        return Vector((0.0, 0.0, 0.0))
    bb = [body_obj.matrix_world @ Vector(c) for c in body_obj.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    cz = (minz + maxz) / 2.0
    sx = (maxx - minx); sy = (maxy - miny); sz = (maxz - minz)
    slots = {
        "head": Vector((cx, cy, maxz + sz * 0.05)),
        "neck": Vector((cx, cy, maxz - sz * 0.15)),
        "chest": Vector((cx, miny - sy * 0.05, cz + sz * 0.1)),
        "waist": Vector((cx, miny - sy * 0.05, minz + sz * 0.45)),
        "left_wrist": Vector((minx - sx * 0.05, cy, minz + sz * 0.35)),
        "right_wrist": Vector((maxx + sx * 0.05, cy, minz + sz * 0.35)),
    }
    return slots.get(attach, Vector((cx, miny, cz)))


def add_decoration(name, context, scale_override=None):
    """Build a decoration by name and snap it to its attach point on the
    body. Returns the new object, or raises ValueError if the name is
    unknown."""
    entry = get_decoration(name)
    if entry is None:
        raise ValueError("未知装饰物: %s" % name)
    bm = bmesh.new()
    try:
        for part in entry.get("parts", []):
            _build_part(bm, part)
        me = bpy.data.meshes.new("AFR_Decor_%s" % name)
        bm.to_mesh(me)
    finally:
        bm.free()
    obj = bpy.data.objects.new("AFR_Decor_%s" % name, me)
    bpy.context.scene.collection.objects.link(obj)
    sc = scale_override if scale_override else entry.get("scale", 1.0)
    obj.scale = (sc, sc, sc)
    # snap to body
    body = None
    for o in context.scene.objects:
        if o.type == "MESH" and "AFR_Decor" not in o.name:
            body = o
            break
    pt = _attach_point(body, entry.get("attach", "chest"))
    obj.location = pt
    obj["afr_decoration"] = name
    obj["afr_attach"] = entry.get("attach", "chest")
    return obj
