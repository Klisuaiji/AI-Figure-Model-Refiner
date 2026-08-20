"""Connector / joint generation for figure assembly (Phase 10+).

Generates the *interlocking convex/concave parts* (凹凸连接件) a 3D-printed
figure needs so its split pieces can be assembled:

  - ``round``    : cylindrical peg (male) + matching hole (female cutter).
                   The universal joint for assembling split body/limb/head parts.
  - ``ball``     : spherical ball (male) + matching socket bowl (female cutter).
                   For articulated figures (head / shoulders / hips rotation).
  - ``dovetail`` : trapezoidal tab (male) + matching slot (female cutter).
                   For strong flat-interface splits (e.g. a flat base seam).

Design notes (inspired by the public techniques of JointForge, Easy-Print and
fdm_joints, re-implemented here from scratch under the project's MIT license):

  * Every joint is built as a **standalone solid mesh** via ``bmesh`` /
    primitive operators. No fragile boolean is used to *build* a connector.
  * The female side is delivered as a **cutter** mesh (a closed solid). The
    user carves it into the receiving part with :func:`carve_socket`
    (a single guarded Boolean DIFFERENCE). This keeps generation non-destructive
    until the user commits.
  * **FDM clearance** is built in. The female cutter is enlarged by ``2 * clearance``
    so the printed male part slides in with the right tolerance. Presets scale
    the default size/clearance by nozzle diameter (0.2 / 0.4 / 0.6 mm).

All functions take ``position`` (world point) and ``direction`` (world axis the
joint points along). Geometry is built along local +Z and then oriented with a
quaternion that maps +Z -> ``direction``.
"""
from __future__ import annotations

import math

import bpy
import bmesh
from mathutils import Vector, Quaternion

from ..core.logging import logger


# ---------------------------------------------------------------------------
# FDM tolerance presets (keyed by nozzle diameter, mm)
# ---------------------------------------------------------------------------
_NOZZLE_PRESETS = {
    0.2: {"clearance": 0.10, "diameter": 4.0, "depth": 3.0},
    0.4: {"clearance": 0.20, "diameter": 5.0, "depth": 4.0},
    0.6: {"clearance": 0.30, "diameter": 6.0, "depth": 5.0},
}

KIND_ROUND = "round"
KIND_BALL = "ball"
KIND_DOVETAIL = "dovetail"
VALID_KINDS = (KIND_ROUND, KIND_BALL, KIND_DOVETAIL)


def preset_from_nozzle(nozzle_mm: float) -> dict:
    """Return the nearest FDM preset for ``nozzle_mm``."""
    keys = sorted(_NOZZLE_PRESETS)
    best = min(keys, key=lambda k: abs(k - nozzle_mm))
    return dict(_NOZZLE_PRESETS[best])


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _quat_z_to(direction) -> Quaternion:
    """Quaternion rotating local +Z onto ``direction``."""
    d = Vector(direction).normalized()
    return Vector((0.0, 0.0, 1.0)).rotation_difference(d)


def _world_center(obj) -> Vector:
    if obj is None:
        return Vector((0.0, 0.0, 0.0))
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return sum(corners, Vector((0.0, 0.0, 0.0))) / 8.0


def _new_object_from_bm(scene, bm, name: str):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    return obj


def _orient_and_place(obj, position, q: Quaternion):
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = q
    obj.location = Vector(position)
    obj.data.update()
    obj.update_tag()


# ---------------------------------------------------------------------------
# Male builders
# ---------------------------------------------------------------------------
def _make_peg(scene, position, q, diameter, length, chamfer, with_flange, name):
    d = float(diameter)
    bm = bmesh.new()
    # Chamfered cylinder: a frustum (top slightly narrower) is a clean,
    # manifold, print-friendly peg tip — no extra boolean needed.
    top_d = d * 0.82 if chamfer else d
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=True, segments=48,
        radius1=d / 2.0, radius2=top_d / 2.0, depth=length,
    )
    # move so the base sits at local z=0 and the peg extends +Z
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0.0, 0.0, length / 2.0))
    # optional flange: a wider short disc at the base. Built in the same bmesh
    # (overlapping the shaft) so the printed part unions by volume — no boolean.
    if with_flange:
        fr = d * 1.9
        fh = max(0.6, d * 0.22)
        nv = len(bm.verts)
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=True, segments=48,
            radius1=fr / 2.0, radius2=fr / 2.0, depth=fh,
        )
        bmesh.ops.translate(bm, verts=list(bm.verts)[nv:], vec=(0.0, 0.0, fh / 2.0))
    peg = _new_object_from_bm(scene, bm, name)
    _orient_and_place(peg, position, q)
    return peg


def _make_ball(scene, position, q, ball_diameter, name):
    r = float(ball_diameter) / 2.0
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=r, location=(0.0, 0.0, 0.0), segments=32, ring_count=16,
    )
    ball = bpy.context.active_object
    ball.name = name
    _orient_and_place(ball, position, q)
    return ball


def _make_dovetail_tab(scene, position, q, width, height, length,
                      dovetail_angle_deg, name):
    w = float(width)
    h = float(height)
    L = float(length)
    t = L * math.tan(math.radians(dovetail_angle_deg))  # side taper per side
    tw = max(w / 2.0 - t, w * 0.1)  # top half-width (narrower -> dovetail)
    bm = bmesh.new()
    co = [
        # bottom (z=0)
        (-w / 2.0, -h / 2.0, 0.0), (w / 2.0, -h / 2.0, 0.0),
        (w / 2.0, h / 2.0, 0.0), (-w / 2.0, h / 2.0, 0.0),
        # top (z=L), tapered
        (-tw, -h / 2.0, L), (tw, -h / 2.0, L),
        (tw, h / 2.0, L), (-tw, h / 2.0, L),
    ]
    verts = [bm.verts.new(Vector(c)) for c in co]
    bm.faces.new([verts[0], verts[1], verts[2], verts[3]])  # bottom
    bm.faces.new([verts[4], verts[7], verts[6], verts[5]])  # top
    bm.faces.new([verts[0], verts[1], verts[5], verts[4]])  # -y side
    bm.faces.new([verts[1], verts[2], verts[6], verts[5]])  # +x side
    bm.faces.new([verts[2], verts[3], verts[7], verts[6]])  # +y side
    bm.faces.new([verts[3], verts[0], verts[4], verts[7]])  # -x side
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    tab = _new_object_from_bm(scene, bm, name)
    _orient_and_place(tab, position, q)
    return tab


# ---------------------------------------------------------------------------
# Female (cutter) builders — closed solids for Boolean DIFFERENCE
# ---------------------------------------------------------------------------
def _make_hole_cutter(scene, position, q, diameter, depth, clearance, name):
    d = float(diameter) + 2.0 * float(clearance)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=True, segments=48,
        radius1=d / 2.0, radius2=d / 2.0, depth=depth,
    )
    # place so the top face is at local z=0 (the surface) and the hole goes -Z
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0.0, 0.0, -depth / 2.0))
    cutter = _new_object_from_bm(scene, bm, name)
    _orient_and_place(cutter, position, q)
    return cutter


def _make_socket_cutter(scene, position, q, ball_diameter, depth,
                        clearance, opening_ratio, name):
    """Spherical bowl cutter. Mouth faces +Z; ball snaps in from +Z.

    The opening radius is ``ball_radius * opening_ratio`` (must be < ball radius
    for a snap-fit that retains the ball). The cut plane sits at
    ``z = -sqrt(R^2 - (ball_r*opening_ratio)^2)`` on a sphere of radius
    ``R = ball_radius + clearance``.
    """
    ball_r = float(ball_diameter) / 2.0
    R = ball_r + float(clearance)
    opening_r = ball_r * float(opening_ratio)
    zp = -math.sqrt(max(R * R - opening_r * opening_r, 0.0))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=R)
    bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
        plane_co=(0.0, 0.0, zp), plane_no=(0.0, 0.0, 1.0),
        clear_inner=True, clear_outer=False,
    )
    # bisect leaves an open rim; cap it with a flat fan so the cutter is a
    # closed manifold (required for a clean Boolean DIFFERENCE).
    rim = [e for e in bm.edges if not e.is_manifold]
    if rim:
        rv = set()
        for e in rim:
            rv.update(e.verts)
        c = sum((v.co for v in rv), Vector((0.0, 0.0, 0.0))) / len(rv)
        center = bm.verts.new(c)
        for e in rim:
            bm.faces.new((e.verts[0], e.verts[1], center))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    cutter = _new_object_from_bm(scene, bm, name)
    _orient_and_place(cutter, position, q)
    return cutter


def _make_slot_cutter(scene, position, q, width, height, length,
                      dovetail_angle_deg, clearance, name):
    # slightly larger box/trapezoid so the tab slides in with clearance
    w = float(width) + 2.0 * float(clearance)
    h = float(height) + 2.0 * float(clearance)
    L = float(length)
    t = L * math.tan(math.radians(dovetail_angle_deg))
    tw = max(w / 2.0 - t, w * 0.1)
    bm = bmesh.new()
    co = [
        (-w / 2.0, -h / 2.0, 0.0), (w / 2.0, -h / 2.0, 0.0),
        (w / 2.0, h / 2.0, 0.0), (-w / 2.0, h / 2.0, 0.0),
        (-tw, -h / 2.0, L), (tw, -h / 2.0, L),
        (tw, h / 2.0, L), (-tw, h / 2.0, L),
    ]
    verts = [bm.verts.new(Vector(c)) for c in co]
    bm.faces.new([verts[0], verts[1], verts[2], verts[3]])
    bm.faces.new([verts[4], verts[7], verts[6], verts[5]])
    bm.faces.new([verts[0], verts[1], verts[5], verts[4]])
    bm.faces.new([verts[1], verts[2], verts[6], verts[5]])
    bm.faces.new([verts[2], verts[3], verts[7], verts[6]])
    bm.faces.new([verts[3], verts[0], verts[4], verts[7]])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    cutter = _new_object_from_bm(scene, bm, name)
    _orient_and_place(cutter, position, q)
    return cutter


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_connector(scene, kind=KIND_ROUND, position=(0.0, 0.0, 0.0),
                     direction=(0.0, 0.0, 1.0), diameter=5.0, depth=4.0,
                     length=4.0, clearance=0.2, nozzle_mm=0.4,
                     with_flange=False, chamfer=True,
                     dovetail_angle_deg=8.0, opening_ratio=0.7,
                     name="AFR_Connector"):
    """Create one connector set (male + matching female cutter).

    Returns a dict with keys ``kind``, ``male`` (mesh object or None),
    ``female_cutter`` (mesh object or None) and ``params`` (echoed inputs).
    """
    if kind not in VALID_KINDS:
        raise ValueError("kind must be one of %s" % (VALID_KINDS,))
    if nozzle_mm and clearance <= 0:
        clearance = preset_from_nozzle(nozzle_mm)["clearance"]
    q = _quat_z_to(direction)
    pos = tuple(position)
    male = None
    female = None
    base = name

    if kind == KIND_ROUND:
        male = _make_peg(scene, pos, q, diameter, length, chamfer,
                         with_flange, base + "_peg")
        female = _make_hole_cutter(scene, pos, q, diameter, depth, clearance,
                                   base + "_hole")
    elif kind == KIND_BALL:
        male = _make_ball(scene, pos, q, diameter, base + "_ball")
        female = _make_socket_cutter(scene, pos, q, diameter, depth, clearance,
                                     opening_ratio, base + "_socket")
    elif kind == KIND_DOVETAIL:
        male = _make_dovetail_tab(scene, pos, q, diameter, diameter * 0.6,
                                  length, dovetail_angle_deg, base + "_tab")
        female = _make_slot_cutter(scene, pos, q, diameter, diameter * 0.6,
                                  length, dovetail_angle_deg, clearance,
                                  base + "_slot")

    logger.info("create_connector %s @%s dir=%s d=%.2f depth=%.2f len=%.2f clr=%.2f" % (
                kind, tuple(round(p, 2) for p in pos),
                tuple(round(x, 2) for x in direction),
                diameter, depth, length, clearance))
    return {
        "kind": kind,
        "male": male,
        "female_cutter": female,
        "params": {
            "position": pos, "direction": tuple(direction),
            "diameter": diameter, "depth": depth, "length": length,
            "clearance": clearance, "nozzle_mm": nozzle_mm,
            "with_flange": with_flange, "chamfer": chamfer,
            "dovetail_angle_deg": dovetail_angle_deg,
            "opening_ratio": opening_ratio,
        },
    }


def carve_socket(scene, target_obj, cutter_obj, apply=True):
    """Carve ``cutter_obj`` (a female cutter) into ``target_obj``.

    Adds a Boolean DIFFERENCE modifier. When ``apply`` is True the modifier is
    applied immediately (geometry changes); otherwise it is left on the stack
    for the user to tune. Returns a result dict.
    """
    if target_obj is None or target_obj.type != "MESH":
        return {"error": "target must be a MESH object"}
    if cutter_obj is None or cutter_obj.type != "MESH":
        return {"error": "cutter must be a MESH object"}
    mod = target_obj.modifiers.new(name="AFR_Socket", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter_obj
    ok = True
    if apply:
        try:
            bpy.context.view_layer.objects.active = target_obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("carve_socket boolean failed: %s", e)
            ok = False
            try:
                target_obj.modifiers.remove(mod)
            except Exception:
                pass
    logger.info("carve_socket: target=%s cutter=%s applied=%s ok=%s" % (
                target_obj.name, cutter_obj.name, apply, ok))
    return {
        "target": target_obj.name, "cutter": cutter_obj.name,
        "applied": apply, "ok": ok,
    }


def add_connector_between(scene, obj_a, obj_b, kind=KIND_ROUND,
                         diameter=5.0, depth=4.0, length=4.0, clearance=0.2,
                         nozzle_mm=0.4, with_flange=False, chamfer=True,
                         opening_ratio=0.7, name="AFR_Connector"):
    """Place a connector between two parts.

    The male peg/ball/tab is created at the midpoint between the two parts'
    world centers, pointing from A to B. The female cutter is created at the
    same midpoint and carved into ``obj_b`` (the receiving part).

    Returns the dict from :func:`create_connector` plus ``carved`` info.
    """
    if obj_a is None or obj_b is None:
        raise ValueError("two objects required")
    ca = _world_center(obj_a)
    cb = _world_center(obj_b)
    mid = (ca + cb) / 2.0
    direction = (cb - ca)
    if direction.length < 1e-6:
        direction = Vector((0.0, 0.0, 1.0))
    direction.normalize()
    res = create_connector(
        scene, kind=kind, position=mid, direction=direction,
        diameter=diameter, depth=depth, length=length, clearance=clearance,
        nozzle_mm=nozzle_mm, with_flange=with_flange, chamfer=chamfer,
        opening_ratio=opening_ratio, name=name,
    )
    carved = None
    if res.get("female_cutter") is not None:
        carved = carve_socket(scene, obj_b, res["female_cutter"], apply=True)
    res["carved"] = carved
    res["midpoint"] = tuple(mid)
    return res
