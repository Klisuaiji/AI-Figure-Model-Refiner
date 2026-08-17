"""Hair refinement operations.

Phase 5 features:
  - extract_hair_part(obj): copy faces labeled HAIR into a new mesh obj.
  - detect_intersections(hair_obj, body_obj): hair faces that penetrate
    body geometry (ray-cast from hair face centroid inward).
  - solidify_hair(obj, thickness): extrude hair mesh along its face
    normals so each strand becomes a thin tube.
  - generate_from_curves(scene, params): build a hair mesh from a
    set of parametric curves sampled into a watertight tube lattice.
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

from ..geometry.printability import _UP


# ---------------------------------------------------------------------------
# Part extraction
# ---------------------------------------------------------------------------
def extract_part(obj, label_id, new_name=None):
    """Copy all faces whose vertices are all labeled ``label_id`` into a
    new mesh object. Returns the new object (or None if no faces)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    from ..semantic import parts as sem_parts
    labels = sem_parts.get_label_array(obj)
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        # tag faces whose MAJORITY of vertices carry the requested label
        keep_faces = []
        vert_map = {}  # original BMVert object -> new bmesh vert
        for f in bm.faces:
            n_match = sum(1 for v in f.verts if labels[v.index] == label_id)
            if n_match >= max(1, len(f.verts) // 2):
                keep_faces.append(f)
        if not keep_faces:
            return None
        # build new bmesh with only those faces
        out = bmesh.new()
        for f in keep_faces:
            new_verts = []
            for v in f.verts:
                key = id(v)
                if key not in vert_map:
                    vert_map[key] = out.verts.new(v.co)
                new_verts.append(vert_map[key])
            try:
                out.faces.new(new_verts)
            except ValueError:
                pass  # duplicate face
        # transform into world (so we keep absolute position)
        out.transform(obj.matrix_world)
        mesh = bpy.data.meshes.new(
            (new_name or obj.name + "_part_" + sem_parts.ID_PART[label_id])
            + "_Mesh")
        out.to_mesh(mesh)
        out.free()
        new_obj = bpy.data.objects.new(
            new_name or obj.name + "_" + sem_parts.ID_PART[label_id], mesh)
        bpy.context.scene.collection.objects.link(new_obj)
        return new_obj
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Issue detection
# ---------------------------------------------------------------------------
def _ray_cast(bvh, origin, direction, max_dist):
    if bvh is None:
        return None
    res = bvh.ray_cast(origin, direction, max_dist)
    if res is None or res[0] is None:
        return None
    return float(res[3])


def detect_intersections(hair_obj, body_obj):
    """Return list of hair face indices whose centroids cast inward and
    hit the body mesh within a short range (= penetrating)."""
    if hair_obj is None or body_obj is None:
        raise ValueError("hair and body required")
    try:
        from mathutils.bvhtree import BVHTree
    except Exception:
        BVHTree = None
    bm_body = bmesh.new()
    try:
        bm_body.from_mesh(body_obj.data)
        bm_body.transform(body_obj.matrix_world)
        bvh = BVHTree.FromBMesh(bm_body) if BVHTree else None
        bm_hair = bmesh.new()
        try:
            bm_hair.from_mesh(hair_obj.data)
            bm_hair.transform(hair_obj.matrix_world)
            max_dist = 5.0
            penetrating = []
            for fi, f in enumerate(bm_hair.faces):
                n = f.normal
                if n.length < 0.5:
                    continue
                c = f.calc_center_median()
                eps = 1e-4
                d_in = _ray_cast(bvh, c - n * eps, -n, max_dist)
                if d_in is not None and d_in < 0.5:
                    penetrating.append(fi)
            return penetrating
        finally:
            bm_hair.free()
    finally:
        bm_body.free()


def detect_floating(obj, ground_tol=0.05):
    """Faces whose vertices are not connected (within tolerance) to any
    body vertex below them. Returns set of face indices."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        z_thr = ground_tol
        result = set()
        # A face is "floating" if its centroid is above z_thr AND no
        # vertex has a same-XY neighbour (within 0.01) below z_thr.
        for fi, f in enumerate(bm.faces):
            cz = f.calc_center_median().z
            if cz <= z_thr + 0.5:  # near the ground, ignore
                continue
            # find lowest z among face vertices
            min_z = min(v.co.z for v in f.verts)
            if min_z > z_thr:
                result.add(fi)
        return result
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Solidify (thicken hair into printable shells)
# ---------------------------------------------------------------------------
def solidify_part(obj, thickness=0.4):
    """Apply bmesh.ops.solidify to give the mesh uniform wall thickness.
    Returns True on success."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        # solidify needs both verts and edges to be flagged
        bmesh.ops.solidify(
            bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            thickness=thickness,
        )
        bm.to_mesh(obj.data)
        obj.data.update()
        return True
    finally:
        bm.free()


# ---------------------------------------------------------------------------
# Procedural hair generation (curves → mesh tubes)
# ---------------------------------------------------------------------------
def generate_hair_curves(scene, params):
    """Generate hair as a Blender Curves object with the given params.

    params (dict):
      scalp_z       : float  # z of scalp (root)
      scalp_radius  : float  # radius of scalp circle
      count         : int    # number of strands
      length_min/max: (float, float)  # strand length range
      curl          : float  # 0..1 curl amount
      noise         : float  # 0..1 noise amount
      taper         : float  # taper exponent (0 = uniform, >0 = tip thinner)

    Returns the curves object.
    """
    z = params.get("scalp_z", 2.0)
    r = params.get("scalp_radius", 0.3)
    n = int(params.get("count", 200))
    lmin = params.get("length_min", 0.5)
    lmax = params.get("length_max", 1.2)
    curl = params.get("curl", 0.3)
    noise = params.get("noise", 0.2)
    taper = params.get("taper", 1.5)
    rng = random.Random(params.get("seed", 0))

    curve_data = bpy.data.curves.new("AFR_HairCurves", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.fill_mode = "FULL"
    curve_data.bevel_depth = 0.0  # we add thickness via mesh later
    curve_data.bevel_resolution = 0

    for i in range(n):
        ang = rng.uniform(0, math.tau)
        rad = math.sqrt(rng.uniform(0, 1)) * r
        root = Vector((math.cos(ang) * rad, math.sin(ang) * rad, z))
        L = rng.uniform(lmin, lmax)
        # build a tapered, curled, noisy polyline
        steps = 16
        co = []
        for s in range(steps + 1):
            t = s / steps
            # tapered length param
            taper_factor = (1.0 - t) ** taper
            seg_len = L / steps * (0.5 + taper_factor)
            # upward direction with curl + noise
            up = Vector((0, 0, 1))
            curl_dir = Vector((math.cos(ang + math.pi * 0.5),
                               math.sin(ang + math.pi * 0.5), 0)) * curl * 0.3
            noise_vec = Vector((rng.uniform(-1, 1),
                                rng.uniform(-1, 1),
                                rng.uniform(-0.3, 0.3))) * noise
            d = (up + curl_dir + noise_vec).normalized()
            if s == 0:
                co.append(root.copy())
            else:
                co.append(co[-1] + d * seg_len)
        # create spline
        spline = curve_data.splines.new("POLY")
        spline.points.add(len(co) - 1)
        for j, p in enumerate(co):
            spline.points[j].co = (p.x, p.y, p.z, 1.0)
    obj = bpy.data.objects.new("AFR_HairCurves", curve_data)
    scene.collection.objects.link(obj)
    return obj


def curves_to_mesh(curves_obj, radius=0.04, segments=4, taper=0.7):
    """Convert a Curves object to a watertight Mesh by sweeping a circle
    along each spline with radius tapering toward the tip."""
    if curves_obj is None or curves_obj.type != "CURVES" and curves_obj.type != "CURVE":
        # bpy 4.x renamed CURVE -> CURVES for hair; accept both
        if curves_obj.type not in ("CURVE", "CURVES"):
            raise ValueError("expected CURVE/CURVES object, got %s" % curves_obj.type)
    # assign bevel params then convert
    cd = curves_obj.data
    cd.bevel_depth = radius
    cd.bevel_resolution = segments
    cd.fill_mode = "FULL"
    # use bpy.ops to convert
    bpy.context.view_layer.objects.active = curves_obj
    bpy.ops.object.select_group_action = None
    curves_obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return curves_obj  # now a MESH