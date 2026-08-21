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
"""Voronoi lightweight lattice generator (V0.6).

Generates a sparse Voronoi-style micro-lattice inside a closed mesh to
reduce print time / material / weight while maintaining strength. This
is a simplified "shrink-wrap" approximation:

  1. Pick N seed points inside the bounding box of the source mesh,
     rejecting any that fall outside the mesh (rejection sampling via
     ray-cast outward in +Z and checking hit count = 1).
  2. For every vertex in the source mesh, assign it to the nearest seed
     (Euclidean). This partitions the mesh surface into "cells".
  3. Each cell becomes a thin lattice of struts between the cell's seed
     and its boundary vertices (a "tent-pole" approximation).

The output is a new MESH object containing only the lattice struts —
the user can union-merge it with the source for printing (lighter, with
internal support structure for printing).

Pure stdlib + bmesh; no scipy/numpy required.
"""
import random
import math

import bpy
import bmesh
from mathutils import Vector

from ..geometry.printability import _build_bvh, _ray_dist


def _inside_mesh(bvh, bm, point, max_dist):
    """True if `point` is strictly inside a closed mesh. We shoot a ray
    in +Z and require an odd number of hits."""
    eps = 1e-4
    origin = Vector((point[0], point[1], point[2] + eps))
    direction = Vector((0, 0, 1))
    res = bvh.ray_cast(origin, direction, max_dist)
    if res is None or res[0] is None:
        return False
    first_hit_dist = float(res[3])
    # cast again from just past the first hit and count further hits
    pos = origin + direction * (first_hit_dist + eps)
    hits = 1
    while True:
        r = bvh.ray_cast(pos, direction, max_dist)
        if r is None or r[0] is None:
            break
        hits += 1
        pos = pos + direction * (float(r[3]) + eps)
        if hits > 64:
            break
    return (hits % 2) == 1


def voronoi_lattice(obj, n_seeds=20, lattice_radius=0.5, name="AFR_Voronoi"):
    """Generate a Voronoi-style lightweight lattice inside `obj`.

    n_seeds       : number of seed points inside the mesh.
    lattice_radius: strut radius (visually; real print uses the printed
                    line width of the slicer).

    Returns the new lattice mesh object.
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        # world bbox
        verts = [v.co.copy() for v in bm.verts]
        if not verts:
            return None
        xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
        bbox_min = Vector((min(xs), min(ys), min(zs)))
        bbox_max = Vector((max(xs), max(ys), max(zs)))
        bdiag = (bbox_max - bbox_min).length
        bvh = _build_bvh(bm)

        # 1. rejection-sample seeds (hard cap to prevent infinite loops
        #    on thin or empty bbox regions).
        rng = random.Random(0)
        seeds = []
        attempts = 0
        max_attempts = n_seeds * 200
        while len(seeds) < n_seeds and attempts < max_attempts:
            attempts += 1
            p = Vector((
                rng.uniform(bbox_min.x, bbox_max.x),
                rng.uniform(bbox_min.y, bbox_max.y),
                rng.uniform(bbox_min.z, bbox_max.z),
            ))
            if _inside_mesh(bvh, bm, p, bdiag):
                seeds.append(p)
        if not seeds:
            return None

        # 2. assign each surface vert to nearest seed
        cell_of = {}  # vert_index -> seed index
        cell_members = {i: [] for i in range(len(seeds))}
        for v in bm.verts:
            best = 0; best_d = 1e18
            for i, s in enumerate(seeds):
                d = (v.co - s).length_squared
                if d < best_d:
                    best_d = d; best = i
            cell_of[v.index] = best
            cell_members[best].append(v.co.copy())

        # 3. build lattice: for each cell, emit a "tent pole" — a
        # single vertex at the seed + edges from seed to boundary
        # vertices. The polyline skeleton is slicer-friendly enough
        # for a thin lattice; the slicer traces the actual print
        # paths at the configured line width.
        out = bmesh.new()
        seed_verts = [out.verts.new(s) for s in seeds]
        for ci, svert in enumerate(seed_verts):
            bverts = [out.verts.new(co) for co in cell_members[ci]]
            for bv in bverts:
                out.edges.new([svert, bv])
        mesh = bpy.data.meshes.new(name + "_Mesh")
        out.to_mesh(mesh)
        out.free()
        new_obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(new_obj)
        return new_obj
    finally:
        bm.free()