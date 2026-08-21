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
"""Connector / joint generation for figure assembly (Phase 10+).

Generates the *interlocking convex/concave parts* (凹凸连接件) a 3D-printed
figure needs so its split pieces can be assembled:

  - ``round``    : cylindrical peg (male) + matching socket cup (female, a real
                   concave blind bore). The universal joint for assembling split
                   body/limb/head parts. This is the default, solver-free joint.
  - ``ball``     : spherical ball (male) + matching socket bowl (female cutter,
                   for the optional carve path). For articulated figures.
  - ``dovetail`` : trapezoidal tab (male) + matching slot (female cutter,
                   for the optional carve path). For strong flat-interface splits.

Design notes (inspired by the public techniques of JointForge, Easy-Print and
fdm_joints, re-implemented here from scratch under the project's GPL-3.0 license):

  * Every joint is built as a **standalone solid mesh** via ``bmesh`` /
    primitive operators. No fragile boolean is used to *build* a connector.
  * Default mode is **semi-automatic and solver-free**: the user places a
    connection point (the 3D cursor) and the operator emits BOTH a male peg and
    a matching female **socket** (a real concave cup with a blind bore). Each is
    a watertight, directly-printable solid — no Boolean is ever run on the
    figure. The two printed pieces are glued/snapped together at assembly.
  * An optional legacy *cutter* path still exists (:func:`carve_socket` with
    ``legacy_cutter=True``) for Boolean-carving a hole into a manifold receiving
    part, but it is no longer the default and is not required for assembly.
  * **FDM clearance** is built in. The socket bore is enlarged by ``2 * clearance``
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


def _make_socket_solid(scene, position, q, peg_diameter, socket_depth,
                       clearance, wall, name):
    """Watertight concave cup (true BLIND bore) the male peg inserts into.

    Built as a single closed bmesh — no Boolean. The cup is a solid outer
    cylinder (radius ``ro``, total height ``Hb``) with a blind cylindrical hole
    (radius ``ri = peg_radius + clearance``) drilled from the *top* mouth down to
    ``z = bottom_thickness``; the base below the bore is solid.

    Surface decomposition (all edges shared by exactly 2 faces -> manifold):
      * outer wall   : cylinder radius ``ro``, ``z=0`` -> ``Hb``
      * bottom disk  : full fan center->``ro`` at ``z=0`` (solid base exterior)
      * bore wall    : cylinder radius ``ri``, ``z=bottom_thickness`` -> ``Hb``
      * bore floor   : full fan center->``ri`` at ``z=bottom_thickness``
      * top rim      : annulus ``ri``->``ro`` at ``z=Hb``

    The previous bug put the bore floor at ``z=0`` coincident with the bottom
    annulus, making the ``ib[i]-ib[j]`` edge shared by 3 faces (non-manifold).
    Lifting the bore floor to ``z > 0`` removes the coincidence.
    """
    pr = float(peg_diameter) / 2.0
    ri = pr + float(clearance)                 # bore radius
    ro = ri + max(float(wall), 0.4)            # outer radius (wall >= 0.4mm)
    bore_depth = float(socket_depth)           # depth of the blind hole
    bottom_thickness = max(0.4, ri * 0.2)      # solid base below the bore
    Hb = bottom_thickness + bore_depth         # total cup height
    segs = 48
    bm = bmesh.new()
    # ctr_b : center of the solid base (z=0).  ctr_i : center of the bore floor.
    ctr_b = bm.verts.new((0.0, 0.0, 0.0))
    ctr_i = bm.verts.new((0.0, 0.0, bottom_thickness))
    ob, ot, ib, it = [], [], [], []
    for i in range(segs):
        a = 2.0 * math.pi * i / segs
        c, s = math.cos(a), math.sin(a)
        ob.append(bm.verts.new((ro * c, ro * s, 0.0)))                 # base ring
        ot.append(bm.verts.new((ro * c, ro * s, Hb)))                  # top ring
        ib.append(bm.verts.new((ri * c, ri * s, bottom_thickness)))     # bore floor ring
        it.append(bm.verts.new((ri * c, ri * s, Hb)))                  # mouth ring
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((ob[i], ot[i], ot[j], ob[j]))     # outer wall
        bm.faces.new((ib[i], ib[j], it[j], it[i]))     # bore wall (blind)
        bm.faces.new((ot[i], it[i], it[j], ot[j]))     # top rim
        bm.faces.new((ctr_b, ob[j], ob[i]))            # bottom disk (solid base)
        bm.faces.new((ctr_i, ib[i], ib[j]))            # bore floor fan
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    sock = _new_object_from_bm(scene, bm, name)
    _orient_and_place(sock, position, q)
    return sock


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
                     socket_depth=None, socket_wall_mm=1.2,
                     legacy_cutter=False, name="AFR_Connector"):
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

    female_socket = None
    female_cutter = None
    if kind == KIND_ROUND:
        male = _make_peg(scene, pos, q, diameter, length, chamfer,
                         with_flange, base + "_peg")
        female_socket = _make_socket_solid(
            scene, pos, q, diameter, socket_depth or depth, clearance,
            socket_wall_mm, base + "_socket")
        if legacy_cutter:
            female_cutter = _make_hole_cutter(
                scene, pos, q, diameter, depth, clearance, base + "_hole")
    elif kind == KIND_BALL:
        male = _make_ball(scene, pos, q, diameter, base + "_ball")
        female_cutter = _make_socket_cutter(
            scene, pos, q, diameter, depth, clearance,
            opening_ratio, base + "_socket")
    elif kind == KIND_DOVETAIL:
        male = _make_dovetail_tab(scene, pos, q, diameter, diameter * 0.6,
                                  length, dovetail_angle_deg, base + "_tab")
        female_cutter = _make_slot_cutter(
            scene, pos, q, diameter, diameter * 0.6,
            length, dovetail_angle_deg, clearance, base + "_slot")

    logger.info("create_connector %s @%s dir=%s d=%.2f depth=%.2f len=%.2f clr=%.2f socket_wall=%.2f" % (
                kind, tuple(round(p, 2) for p in pos),
                tuple(round(x, 2) for x in direction),
                diameter, depth, length, clearance, socket_wall_mm))
    return {
        "kind": kind,
        "male": male,
        "female_socket": female_socket,
        "female_cutter": female_cutter,
        "params": {
            "position": pos, "direction": tuple(direction),
            "diameter": diameter, "depth": depth, "length": length,
            "clearance": clearance, "nozzle_mm": nozzle_mm,
            "socket_wall_mm": socket_wall_mm,
            "with_flange": with_flange, "chamfer": chamfer,
            "dovetail_angle_deg": dovetail_angle_deg,
            "opening_ratio": opening_ratio,
            "legacy_cutter": legacy_cutter,
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
                         opening_ratio=0.7, socket_wall_mm=1.2,
                         name="AFR_Connector"):
    """Place a connector pair between two parts, solver-free.

    Generates the male peg and matching female socket at the midpoint between
    the two parts' world centers, oriented along A->B. Neither piece is carved:
    the peg is parented to ``obj_a`` and the socket to ``obj_b`` so they travel
    with their respective parts; the user glues/snaps them at assembly.

    Returns the dict from :func:`create_connector` plus ``midpoint`` and
    ``parented_to`` (the two parents' names).
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
        opening_ratio=opening_ratio, socket_wall_mm=socket_wall_mm, name=name,
    )
    peg = res.get("male")
    sock = res.get("female_socket")
    if peg is not None:
        peg.parent = obj_a
    if sock is not None:
        sock.parent = obj_b
    res["midpoint"] = tuple(mid)
    res["parented_to"] = (obj_a.name if peg is not None else None,
                          obj_b.name if sock is not None else None)
    return res
