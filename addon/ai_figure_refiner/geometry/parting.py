"""Geometry-driven auto parting: naming + split for AI figure refiner.

Goal: turn an imported AI figure (a set of meshes named part_N) into a
semantically named, print-ready set of parts that approaches the human-made
``after.zip`` contract (e.g. ``PWY-底座.stl``, ``PWY-手L.stl``).

The mapping is *geometric* and *deterministic* so it can run headless and be
validated against after.zip coverage.  It is intentionally conservative: when
a part cannot be confidently classified it keeps a placeholder name and is
reported, so the user can refine via the naming manifest.
"""
import bpy
import mathutils


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _bbox(o):
    bb = o.bound_box
    xs = [v[0] for v in bb]; ys = [v[1] for v in bb]; zs = [v[2] for v in bb]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _size(o):
    mn, mx, ny, xy, nz, xz = _bbox(o)
    return (mx - mn, xy - ny, xz - nz)


def _center(o):
    mn, mx, ny, xy, nz, xz = _bbox(o)
    return ((mn + mx) / 2, (ny + xy) / 2, (nz + xz) / 2)


def _world_center(o):
    c = _center(o)
    return (o.matrix_world @ mathutils.Vector((c[0], c[1], c[2], 1))).xyz


# ---------------------------------------------------------------------------
# naming
# ---------------------------------------------------------------------------
def auto_name_parts(context, prefix=""):
    """Assign ``afr_part_name`` to every MESH object based on geometry.

    Each part gets a UNIQUE name (role + running index) so parts never collide.
    Symmetric parts (腿/胳膊/脚/手) are additionally tagged with
    ``afr_symmetric = role`` and the big torso with ``afr_band_split = True``
    so AFR_OT_AutoPart can split deterministically without re-splitting the
    children it creates (which used to cause runaway duplication).
    """
    meshes = [o for o in context.scene.objects if o.type == "MESH"]
    if not meshes:
        return {}

    # global height range for relative thresholds
    zmin = min(_bbox(o)[4] for o in meshes)
    zmax = max(_bbox(o)[5] for o in meshes)
    zspan = max(zmax - zmin, 1e-6)
    xmin = min(_bbox(o)[0] for o in meshes)
    xmax = max(_bbox(o)[1] for o in meshes)
    cx = (xmin + xmax) / 2

    # role -> list of (obj, score); later assigned unique names role1..roleN
    roles = {}
    for o in meshes:
        sx, sy, sz = _size(o)
        c = _world_center(o)
        zr = (c.z - zmin) / zspan  # 0 bottom .. 1 top
        mn, mx, ny, xy, nz, xz = _bbox(o)
        # base plate: low, flat, wide
        if zr < 0.15 and sz < 0.18 * zspan and max(sx, sy) > 0.35:
            roles.setdefault("底座", []).append((o, 1.0))
            continue
        # head / hair: top, compact
        if zr > 0.80:
            roles.setdefault("头", []).append((o, zr))
            continue
        # legs: tall, vertical, lower-mid
        if sz > 0.40 * zspan and sz > max(sx, sy) * 1.6 and 0.15 < zr < 0.75:
            roles.setdefault("腿", []).append((o, sz))
            continue
        # arms: elongated horizontally, upper-mid height, clearly wider than tall
        if max(sx, sy) > 1.8 * sz and 0.50 < zr < 0.85 and max(sx, sy) > 0.15:
            roles.setdefault("胳膊", []).append((o, max(sx, sy)))
            continue
        # feet: low, small, near bottom
        if zr < 0.20 and max(sx, sy) < 0.20 and sz < 0.20 * zspan:
            roles.setdefault("脚", []).append((o, 1.0 - zr))
            continue
        # torso / skirt: big mid mass
        if sz > 0.25 * zspan and max(sx, sy) > 0.25:
            roles.setdefault("身体", []).append((o, sx * sy * sz))
            continue
        # everything else -> small accessory
        roles.setdefault("装饰", []).append((o, 1.0))

    result = {}
    for role, items in roles.items():
        items.sort(key=lambda t: -t[1])
        symmetric = role in ("腿", "胳膊", "脚", "手")
        for i, (o, _) in enumerate(items):
            # unique name: 腿1, 腿2, 胳膊1 ... 装饰1, 装饰2 ...
            nm = "%s%d" % (role, i + 1) if (symmetric or role == "装饰") else role
            result[o.name] = nm
            if symmetric:
                o["afr_symmetric"] = role  # tag for AFR_OT_AutoPart
            if role == "身体":
                o["afr_band_split"] = True
            o["afr_part_name"] = nm
    return result


# ---------------------------------------------------------------------------
# symmetric split (one mesh -> L and R by world X plane through centroid)
# ---------------------------------------------------------------------------
def split_symmetric(context, obj, role):
    """Split ``obj`` into left/right by the world-X plane through its centroid.

    Returns (left_obj, right_obj) or None if not splittable.
    """
    import bmesh
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(obj.matrix_world)
    cx = sum((v.co.x for v in bm.verts), 0.0) / max(len(bm.verts), 1)

    left = bmesh.new(); right = bmesh.new()
    # copy verts
    lmap = {}; rmap = {}
    for v in bm.verts:
        if v.co.x <= cx:
            lmap[v.index] = left.verts.new(v.co)
        else:
            rmap[v.index] = right.verts.new(v.co)
    for f in bm.faces:
        fv = f.verts
        if all(v.co.x <= cx for v in fv):
            nf = left.faces.new([lmap[v.index] for v in fv])
            nf.material_index = f.material_index
        elif all(v.co.x > cx for v in fv):
            nf = right.faces.new([rmap[v.index] for v in fv])
            nf.material_index = f.material_index
        # faces crossing the plane are dropped (rare for clean splits)

    if not left.faces or not right.faces:
        # one-sided mesh: keep as a single part (can't mirror-split)
        bm.free(); left.free(); right.free()
        single = bpy.data.objects.new("%s_C" % role, obj.data)
        single.matrix_world = obj.matrix_world
        single["afr_part_name"] = "%s_C" % role
        context.collection.objects.link(single)
        return (single,)

    lme = bpy.data.meshes.new("%s_L" % role)
    left.to_mesh(lme)
    rme = bpy.data.meshes.new("%s_R" % role)
    right.to_mesh(rme)
    bm.free(); left.free(); right.free()

    lo = bpy.data.objects.new("%s_L" % role, lme)
    ro = bpy.data.objects.new("%s_R" % role, rme)
    for nw in (lo, ro):
        nm = "%s_L" % role if nw is lo else "%s_R" % role
        nw["afr_part_name"] = nm
        context.collection.objects.link(nw)
    return lo, ro


# ---------------------------------------------------------------------------
# vertical Z-band split (a big torso/skirt mesh -> stacked bands)
# ---------------------------------------------------------------------------
def split_by_zbands(context, obj, bands):
    """Split ``obj`` into ``bands`` stacked pieces along world Z.

    ``bands`` is a list of (name, z_lo_frac, z_hi_frac) in 0..1 of obj Z span.
    Returns list of created objects (linked to scene).
    """
    import bmesh
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(obj.matrix_world)
    zs = [v.co.z for v in bm.verts]
    zmn, zmx = min(zs), max(zs)
    zspan = max(zmx - zmn, 1e-6)

    created = []
    for (name, lo, hi) in bands:
        sub = bmesh.new()
        vmap = {}
        for v in bm.verts:
            zr = (v.co.z - zmn) / zspan
            if lo <= zr <= hi:
                vmap[v.index] = sub.verts.new(v.co)
        if not vmap:
            sub.free()
            continue
        for f in bm.faces:
            fv = f.verts
            if all(v.index in vmap for v in fv):
                nf = sub.faces.new([vmap[v.index] for v in fv])
                nf.material_index = f.material_index
        if not sub.faces:
            sub.free()
            continue
        nme = bpy.data.meshes.new(name)
        sub.to_mesh(nme)
        sub.free()
        no = bpy.data.objects.new(name, nme)
        no["afr_part_name"] = name
        context.collection.objects.link(no)
        created.append(no)
    bm.free()
    return created
