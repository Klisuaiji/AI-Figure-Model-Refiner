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
"""Phase 2 — extra-limb removal.

AI-generated figures frequently sprout spurious limbs (a third arm, floating
hands, detached spikes) attached to the body by a thin bridge of a few faces.
We detect them as small connected components whose attachment to the main
body is a thin bridge, highlight them in red for the user to confirm, then
delete the component and bridge the resulting opening on the main body.
"""
import bmesh


def detect_extra_limbs(obj, bridge_max=4, max_frac=0.08):
    """Return a list of vertex-index sets that look like spurious limbs:

      * they are NOT the largest connected component (the main body), and
      * they are small (<= ``max_frac`` of all verts), and
      * they attach to the rest of the mesh by a thin bridge
        (<= ``bridge_max`` edges crossing the component boundary).

    The thresholds are intentionally permissive — the result is only a
    *candidate* set the user confirms before deletion.
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    me = obj.data
    n = len(me.vertices)
    if n == 0:
        return []
    adj = [[] for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices[0], e.vertices[1]
        adj[a].append(b)
        adj[b].append(a)
    # connected components (BFS)
    comp = [-1] * n
    comps = []
    for s in range(n):
        if comp[s] != -1:
            continue
        q = [s]
        comp[s] = len(comps)
        cur = [s]
        head = 0
        while head < len(q):
            v = q[head]
            head += 1
            for w in adj[v]:
                if comp[w] == -1:
                    comp[w] = comp[s]
                    cur.append(w)
                    q.append(w)
        comps.append(cur)
    if len(comps) <= 1:
        return []  # single component => nothing to remove
    main_idx = max(range(len(comps)), key=lambda i: len(comps[i]))
    candidates = []
    for i, c in enumerate(comps):
        if i == main_idx:
            continue
        if len(c) > max_frac * n:
            continue
        # count edges with exactly one endpoint inside c (bridge thickness)
        seen = set()
        bridges = 0
        for v in c:
            for w in adj[v]:
                if w not in c:
                    key = (v, w) if v < w else (w, v)
                    if key not in seen:
                        seen.add(key)
                        bridges += 1
        if bridges <= bridge_max:
            candidates.append(c)
    return candidates


def mark_extra(obj, components, color=(1.0, 0.0, 0.0, 1.0)):
    """Paint the candidate vertices red (a ``AFR_ExtraColor`` color
    attribute) and stash their indices on ``obj["afr_extra_verts"]`` so the
    removal operator can act on exactly this selection. Returns the flat
    vertex-index list."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    me = obj.data
    n = len(me.vertices)
    attr = me.color_attributes.get("AFR_ExtraColor")
    if attr is None:
        attr = me.color_attributes.new(
            name="AFR_ExtraColor", type="BYTE_COLOR", domain="POINT")
    rgba = [0, 0, 0, 0] * n
    flat = []
    for c in components:
        for vi in c:
            if 0 <= vi < n:
                flat.append(vi)
                base = vi * 4
                rgba[base:base + 4] = [
                    int(color[0] * 255), int(color[1] * 255),
                    int(color[2] * 255), int(color[3] * 255)]
    attr.data.foreach_set("color", rgba)
    obj.data.update()
    obj["afr_extra_verts"] = flat
    return flat


def remove_marked(obj, fill_boundary=True):
    """Delete the vertices stored in ``obj["afr_extra_verts"]`` and bridge
    the opening left on the main body. Returns the number of vertices
    removed (0 if none marked)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    idxs = obj.get("afr_extra_verts", None)
    if not idxs:
        return 0
    idx_set = set(int(i) for i in idxs)
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        to_del = [bm.verts[i] for i in idx_set if i < len(bm.verts)]
        if not to_del:
            return 0
        bmesh.ops.delete(bm, geom=to_del, context="VERTS")
        if fill_boundary:
            boundary = [e for e in bm.edges if len(e.link_faces) == 1]
            if boundary:
                try:
                    bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
                except Exception:
                    pass
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        obj.data.update()
        removed = len(to_del)
        try:
            del obj["afr_extra_verts"]
        except KeyError:
            pass
        # clear the red overlay
        me = obj.data
        attr = me.color_attributes.get("AFR_ExtraColor")
        if attr is not None:
            n = len(me.vertices)
            attr.data.foreach_set("color", [0, 0, 0, 0] * n)
            me.update()
        return removed
    finally:
        bm.free()
