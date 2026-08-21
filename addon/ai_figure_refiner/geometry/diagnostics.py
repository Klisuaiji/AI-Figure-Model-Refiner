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
import bmesh
from mathutils import Vector


def _count_components(bm):
    """Count connected components via BFS over vertex adjacency."""
    # Blender 5.x maintains BMesh lookup tables automatically.
    visited = set()
    comps = 0
    adj = {v.index: [] for v in bm.verts}
    for e in bm.edges:
        a, b = e.verts[0].index, e.verts[1].index
        adj[a].append(b)
        adj[b].append(a)
    for v in bm.verts:
        if v.index in visited:
            continue
        comps += 1
        stack = [v.index]
        visited.add(v.index)
        while stack:
            cur = stack.pop()
            for n in adj[cur]:
                if n not in visited:
                    visited.add(n)
                    stack.append(n)
    return comps


def _mesh_volume(bm):
    """Signed volume via divergence theorem (coords are already in the
    desired space — caller is responsible for any matrix transform)."""
    vol = 0.0
    for f in bm.faces:
        verts = f.verts
        if len(verts) < 3:
            continue
        v0 = verts[0].co
        for i in range(1, len(verts) - 1):
            v1 = verts[i].co
            v2 = verts[i + 1].co
            vol += v0.dot(v1.cross(v2))
    return abs(vol) / 6.0


def analyze_bmesh(bm):
    """Run diagnostics on a BMesh that has already been transformed into
    the desired evaluation space (world for bbox / volume)."""
    # Blender 5.x maintains BMesh lookup tables automatically.

    n_verts = len(bm.verts)
    n_edges = len(bm.edges)
    n_faces = len(bm.faces)

    non_manifold = [e for e in bm.edges if len(e.link_faces) != 2]
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]

    # duplicate vertices (same coordinate within tolerance)
    dup = 0
    seen = set()
    for v in bm.verts:
        key = (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
        if key in seen:
            dup += 1
        else:
            seen.add(key)

    zero_area = [f for f in bm.faces if f.calc_area() < 1e-9]
    bad_normal = [f for f in bm.faces if f.normal.length < 0.5]

    comps = _count_components(bm)

    if n_verts > 0:
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        bbox = {
            "min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)],
        }
        size = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
    else:
        bbox = None
        size = [0.0, 0.0, 0.0]

    volume = _mesh_volume(bm)
    watertight = (len(boundary) == 0 and len(non_manifold) == 0)

    triangles = sum(1 for f in bm.faces if len(f.verts) == 3)
    quads = sum(1 for f in bm.faces if len(f.verts) == 4)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)

    return {
        "vertices": n_verts,
        "edges": n_edges,
        "faces": n_faces,
        "triangles": triangles,
        "quads": quads,
        "ngons": ngons,
        "non_manifold_edges": len(non_manifold),
        "boundary_edges": len(boundary),
        "duplicate_vertices": dup,
        "zero_area_faces": len(zero_area),
        "bad_normal_faces": len(bad_normal),
        "connected_components": comps,
        "bbox": bbox,
        "size": size,
        "volume": volume,
        "watertight": watertight,
    }


def analyze_object(obj):
    """Analyze a Blender mesh object. Returns a dict of metrics in
    world-space coordinates (bbox, volume)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("analyze_object requires a MESH object")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        return analyze_bmesh(bm)
    finally:
        bm.free()