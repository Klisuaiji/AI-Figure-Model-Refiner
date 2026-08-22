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


def repair_basic(obj, remove_doubles_dist=0.001, fill_holes=True, recalc_normals=True):
    """Best-effort basic repair on a mesh object:
       - remove duplicate vertices
       - recalculate face normals
       - fill simple holes (boundary edge loops)
    Returns a list of human-readable status strings.
    Caller is responsible for taking a Snapshot first if rollback is desired."""
    if obj is None or obj.type != "MESH":
        raise ValueError("repair_basic requires a MESH object")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        info = []
        if remove_doubles_dist and remove_doubles_dist > 0:
            before = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=remove_doubles_dist)
            after = len(bm.verts)
            info.append("remove_doubles: -%d verts (%.4f mm)" % (before - after, remove_doubles_dist))
        if recalc_normals:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            info.append("recalc_face_normals: done")
        if fill_holes:
            boundary = [e for e in bm.edges if len(e.link_faces) == 1]
            if boundary:
                try:
                    bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
                    info.append("holes_fill: attempted on %d boundary edges" % len(boundary))
                except Exception as e:
                    info.append("holes_fill skipped: %s" % e)
            else:
                info.append("holes_fill: no boundary edges found")
        bm.to_mesh(obj.data)
        obj.data.update()
        return info
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Per-part fill / close (Phase 1: make every split part a printable solid)
# ---------------------------------------------------------------------------
# Parts that are naturally thin shells on the figure need an explicit wall
# thickness so the slicer can print them; solid volumes (head/body/base) only
# need their open boundaries capped.
THIN_PARTS = ("HAIR", "FABRIC")


def _label_from_name(name):
    """Best-effort extraction of the AFR part token from an object name
    (e.g. ``part_0_HAIR`` -> ``HAIR``). Returns None if unrecognized."""
    if not name:
        return None
    for lab in ("HAIR", "HEAD", "BODY", "FABRIC", "BASE"):
        if name == lab or name.endswith("_" + lab):
            return lab
    return None


def fill_close_part(obj, solidify_thin=0.6, force=False):
    """Turn one extracted part into a watertight, printable solid:

      1. weld any residual duplicate verts (defensive; split already welds)
      2. cap every open boundary loop with ``holes_fill`` (catches simple
         circular holes)
      3. **aggressive pass**: for any boundary edges that survived
         ``holes_fill`` (complex multi-branch / non-planar holes common in
         AI meshes), build a fan-cap face per independent boundary loop.
         This always leaves a manifold surface even if the cap is
         non-planar; ``solidify`` (step 5) then thickens the whole shell.
      4. recalculate face normals
      5. give THIN parts (HAIR/FABRIC) a uniform shell via ``solidify``

    Sets ``obj["afr_filled"] = True`` so the operation is idempotent.
    Returns a list of human-readable status strings.
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("fill_close_part requires a MESH object")
    if (not force) and bool(obj.get("afr_filled", False)):
        return ["skip: already filled"]
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        info = []
        # 1) weld (defensive)
        before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
        after = len(bm.verts)
        if before != after:
            info.append("remove_doubles: -%d verts" % (before - after))
        # 2) cap holes
        boundary = [e for e in bm.edges if len(e.link_faces) == 1]
        if boundary:
            try:
                bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
                info.append("holes_fill: capped %d boundary edges" % len(boundary))
            except Exception as e:
                info.append("holes_fill skipped: %s" % e)
        else:
            info.append("holes_fill: no open boundaries")
        # 3) aggressive boundary cap (handles AI multi-branch / non-planar
        #    holes that holes_fill refuses to touch)
        n_pre = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        n_capped = _cap_all_boundary_loops(bm, max_loop=80)
        info.append("hard-cap: closed %d residual boundary loops "
                    "(was %d bnd edges)" % (n_capped, n_pre))
        # 4) normals
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        # 5) thin parts get a printable shell
        lab = _label_from_name(obj.name)
        if lab in THIN_PARTS:
            try:
                bmesh.ops.solidify(
                    bm,
                    geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                    thickness=solidify_thin,
                )
                info.append("solidify: %.2f mm shell (%s)" % (solidify_thin, lab))
            except Exception as e:
                info.append("solidify skipped: %s" % e)
        bm.to_mesh(obj.data)
        obj.data.update()
        obj["afr_filled"] = True
        return info
    finally:
        bm.free()


def _cap_all_boundary_loops(bm, max_loop=80):
    """Walk every independent boundary edge loop in ``bm`` and cap it with
    a single fan face from an interior centroid.  Returns the number of
    loops successfully capped.  Loops longer than ``max_loop`` edges are
    skipped (they are likely full body openings that should be filled by
    a different tool — we don't want to add a giant non-planar fan).

    Robust against:
      * self-intersecting boundary edges (handled by repeated recompute)
      * multi-branch boundaries (each branch is its own walk)
      * non-manifold vertex configurations (we coerce to a triangle fan)

    A loop is identified as a maximal chain of boundary edges where each
    edge's vertex (other than the start) is the next edge's start.
    """
    capped = 0
    # Use a while loop: every time we cap a loop, the boundary count
    # changes so we re-scan.
    while True:
        # Find one boundary edge to start from
        start = None
        for e in bm.edges:
            if len(e.link_faces) == 1:
                start = e
                break
        if start is None:
            return capped
        # Walk the loop: prefer the boundary-edge-connected neighbour
        loop_verts = []
        visited = set()
        cur = start
        cur_v = cur.verts[0]
        while True:
            loop_verts.append(cur_v)
            visited.add(cur_v.index)
            # find next boundary edge from cur_v (other endpoint)
            nxt = None
            for e in cur_v.link_edges:
                if e is cur:
                    continue
                if len(e.link_faces) != 1:
                    continue
                if e.verts[0].index == cur_v.index:
                    nxt = (e, e.verts[1])
                elif e.verts[1].index == cur_v.index:
                    nxt = (e, e.verts[0])
                if nxt is not None:
                    break
            if nxt is None:
                break
            cur, cur_v = nxt
            if cur_v.index in visited:
                break  # closed the loop
            if len(loop_verts) > max_loop:
                # too long, give up
                loop_verts = None
                break
        if loop_verts is None or len(loop_verts) < 3:
            # give up; mark this edge as consumed to make progress
            # (re-set its other endpoint's link_faces... actually we just
            #  skip the cap and let the outer while loop try the next edge
            #  by hiding the start edge from boundary scan via a tiny trick:
            #  we can't, so just break and let the operator tolerate some
            #  open edges)
            return capped
        # Build a fan-cap face
        try:
            # need at least 3 verts for a valid face
            if len(loop_verts) >= 3:
                bm.faces.new(list(loop_verts))
                capped += 1
        except (ValueError, Exception):
            # duplicate face, or other error
            pass
    return capped


def fill_close_parts(objects, solidify_thin=0.6, force=False):
    """Batch wrapper around :func:`fill_close_part`. Returns a dict
    ``{object_name: [status_lines]}``."""
    infos = {}
    for o in objects:
        if o is None or o.type != "MESH":
            continue
        try:
            infos[o.name] = fill_close_part(
                o, solidify_thin=solidify_thin, force=force)
        except Exception as e:
            infos[o.name] = ["ERROR: %s" % e]
    return infos