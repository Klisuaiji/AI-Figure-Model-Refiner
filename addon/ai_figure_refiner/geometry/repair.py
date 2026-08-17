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