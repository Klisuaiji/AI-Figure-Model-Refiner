# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# This file is part of the AI Figure Model Refiner (AFR) addon.
"""Self-contained binary STL writer (no operator dependency).

Blender's ``wm.stl_export`` operator changed its keyword arguments across
versions (4.x → 5.x), so we write binary STL directly via bmesh. The binary
STL layout matches the reference packs (Materialise-style 80-byte header).
"""
import struct

import bmesh
import bpy
from mathutils import Vector


def write_stl_binary(obj, filepath, header=b"AFR 1.0"):
    """Write ``obj`` (world space) as binary STL. Returns triangle count."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    me = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.transform(obj.matrix_world)
        # triangulate n-gons in a copy-friendly way: collect triangle fans
        tris = []
        for f in bm.faces:
            verts = [v.co for v in f.verts]
            n = len(verts)
            if n == 3:
                tris.append(verts)
            elif n == 4:
                # simple diagonal split (v0,v1,v2) + (v0,v2,v3)
                tris.append([verts[0], verts[1], verts[2]])
                tris.append([verts[0], verts[2], verts[3]])
            else:
                # fan triangulation around centroid
                c = sum(verts, Vector()) / n
                for i in range(n):
                    tris.append([verts[i], verts[(i + 1) % n], c])
        with open(filepath, "wb") as f:
            hdr = (header[:80] if len(header) <= 80 else header[:80])
            f.write(hdr.ljust(80, b"\x00"))
            f.write(struct.pack("<I", len(tris)))
            for t in tris:
                v0, v1, v2 = t
                nrm = (v1 - v0).cross(v2 - v0)
                ln = nrm.length
                if ln > 1e-12:
                    nrm = nrm / ln
                else:
                    nrm = Vector((0.0, 0.0, 1.0))
                f.write(struct.pack(
                    "<12f",
                    nrm.x, nrm.y, nrm.z,
                    v0.x, v0.y, v0.z,
                    v1.x, v1.y, v1.z,
                    v2.x, v2.y, v2.z))
                f.write(struct.pack("<H", 0))
        return len(tris)
    finally:
        bm.free()
