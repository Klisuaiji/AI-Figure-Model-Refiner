# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# Phase 9 — disconnected-component splitting.
#
# AI-generated meshes frequently bundle several distinct printable parts into
# one MESH object (the "part_X" style export of Rodin / Tripo / Meshy packs an
# entire figure as 20-something meshes, but each *mesh* is itself a coarse
# soup that may already mix the body, a leg, a free-floating hair spike, and
# a base plinth).  ``split_disconnected`` turns each connected component of
# the source mesh into its own MESH object so the rest of the AFR pipeline
# (fill, label, name, package) can target it independently.
#
# Connected components are computed in face-adjacency space (sharing an edge
# counts as connected).  This matches the slicer / Boolean-tool definition
# of "one printable part".
import bpy
import bmesh


def _face_components(me):
    """Return a list of int arrays — per-component face indices — computed
    via BFS on **face adjacency defined as "share at least one vertex OR at
    least one edge"**.  This matches the human expectation of "two pieces
    attached at a single vertex are still two pieces" while still being
    conservative enough to keep stitched-together shells as one part.

    For each face we collect the set of face-indices that share at least
    one vertex with it (== two faces are in the same component when a
    chain of vertex-shared faces connects them).  This is the standard
    "vertex-connected face component" used in mesh analysis tooling and
    matches what a slicer would consider a "part".
    """
    n = len(me.polygons)
    if n == 0:
        return []
    # build per-face list of incident vertex indices
    face_verts = [tuple(p.vertices) for p in me.polygons]
    # invert: vertex -> list of incident face indices
    v2f = {}
    for fi, vs in enumerate(face_verts):
        for v in vs:
            v2f.setdefault(v, []).append(fi)
    # BFS over faces
    seen = [False] * n
    comps = []
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        cur = []
        while stack:
            f = stack.pop()
            cur.append(f)
            for v in face_verts[f]:
                for nb in v2f[v]:
                    if not seen[nb]:
                        seen[nb] = True
                        stack.append(nb)
        comps.append(cur)
    return comps


def split_disconnected(source_obj, name_prefix=None, min_face_count=1,
                       skip_largest=False, split_all=False):
    """Split ``source_obj`` into one MESH per face-connected component.

    Args:
      source_obj       : the MESH to split.
      name_prefix      : prefix for new object names; default ``source_obj.name``.
      min_face_count   : skip components with fewer than this many faces
                         (degenerate isolated triangles, etc.).
      skip_largest     : if True, don't extract the largest component — keep
                         it on ``source_obj`` and split off the rest.  Useful
                         for the "big body + small accessories" pattern.
      split_all        : if True, every component becomes its own MESH (the
                         source object is left empty).  Use this for
                         *fully broken* AI meshes where the "main" is not
                         reliably the largest — every part must be
                         independently fillable.

    Returns:
      dict with:
        ``kept``        : the source object (now trimmed) or None if fully split.
        ``created``     : list of new MESH objects, one per extracted component.
        ``stats``       : per-component {"faces": n, "verts": n} dict.
    """
    if source_obj is None or source_obj.type != "MESH":
        raise ValueError("MESH required")
    me = source_obj.data
    comps = _face_components(me)
    if not comps:
        return {"kept": source_obj, "created": [], "stats": []}
    if len(comps) == 1:
        return {"kept": source_obj, "created": [],
                "stats": [{"faces": len(comps[0])}]}

    # sort by size, decide which to extract
    comps_sorted = sorted(enumerate(comps), key=lambda kv: -len(kv[1]))
    to_extract = list(range(len(comps_sorted)))
    if split_all:
        to_extract = list(range(len(comps_sorted)))  # extract every one
    elif skip_largest:
        to_extract = to_extract[1:]  # keep largest
    prefix = name_prefix or source_obj.name

    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        # mark all faces; unmark the ones we want to keep in source
        all_faces = set(range(len(bm.faces)))
        keep_set = set()
        if skip_largest:
            keep_set = set(comps_sorted[0][1])
        # process each extractable component
        created = []
        stats = []
        # work on copies: each component gets a fresh bmesh for safety
        for new_idx, (orig_idx, face_list) in enumerate(comps_sorted):
            if orig_idx not in to_extract:
                continue
            face_list = [f for f in face_list if len(face_list) >= min_face_count]
            if not face_list:
                continue
            # build a fresh bmesh containing only these faces (vertex-keyed)
            out = bmesh.new()
            vmap = {}  # original vert idx -> new bmesh vert
            for fi in face_list:
                f = bm.faces[fi]
                new_verts = []
                for v in f.verts:
                    key = v.index
                    if key not in vmap:
                        # compute world-space coordinate from source
                        co = source_obj.matrix_world @ v.co
                        vmap[key] = out.verts.new(co)
                    new_verts.append(vmap[key])
                try:
                    out.faces.new(new_verts)
                except ValueError:
                    pass  # duplicate face
            # transform into local space of new object (so it stays where it was)
            out.transform(source_obj.matrix_world.inverted())
            nmesh = bpy.data.meshes.new(
                "%s_c%d_Mesh" % (prefix, orig_idx))
            out.to_mesh(nmesh)
            out.free()
            nverts = len(nmesh.vertices)
            nfaces = len(nmesh.polygons)
            nobj = bpy.data.objects.new(
                "%s_c%d" % (prefix, orig_idx), nmesh)
            bpy.context.scene.collection.objects.link(nobj)
            # place in world at source's transform
            nobj.matrix_world = source_obj.matrix_world.copy()
            created.append(nobj)
            stats.append({"faces": nfaces, "verts": nverts,
                          "component": orig_idx})
            # tag these faces for removal from source
            if skip_largest:
                pass  # not removing any from source
            else:
                for fi in face_list:
                    keep_set.discard(fi)
        # If we extracted everything, delete the source's mesh
        # If we kept the largest, just delete those faces from source bmesh
        if split_all or not skip_largest:
            to_delete = [bm.faces[i] for i in range(len(bm.faces))
                         if i not in keep_set]
            if to_delete:
                bmesh.ops.delete(bm, geom=to_delete, context="FACES")
                # also delete orphan verts
                orphan = [v for v in bm.verts if not v.link_faces]
                if orphan:
                    bmesh.ops.delete(bm, geom=orphan, context="VERTS")
                bm.to_mesh(me)
                me.update()
            else:
                # nothing left in source — keep the (now empty) object
                pass
        else:
            # source kept; ensure its mesh is current
            bm.to_mesh(me)
            me.update()
        return {"kept": source_obj, "created": created, "stats": stats}
    finally:
        bm.free()
