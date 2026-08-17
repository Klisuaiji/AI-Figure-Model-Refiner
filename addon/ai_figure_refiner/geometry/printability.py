"""FDM printability analysis.

Pure Blender-BMesh implementation, no external deps. Assumes the model's
working units are millimetres (consistent with diagnostics & UI defaults).

Provided analyses:
  1. Wall thickness: per-face ray-cast along +/- face normal; nearest hit
     distance yields the local shell thickness.
  2. Overhang detection: face angles from build axis (Z by default).
  3. Floating parts: connected components whose min-Z is well above the
     build plate (i.e. not touching ground).
  4. Print validation: aggregate verdict + severity-tagged issues.

Returned dict is JSON-friendly; consumed by the N-Panel and CLI tests.
"""
import bmesh
from mathutils import Vector
from math import degrees, cos, radians

try:
    from mathutils.bvhtree import BVHTree
    _HAVE_BVH = True
except Exception:
    BVHTree = None
    _HAVE_BVH = False

from . import diagnostics as _diag


_UP = Vector((0.0, 0.0, 1.0))


def _build_bvh(bm):
    if _HAVE_BVH:
        return BVHTree.FromBMesh(bm)
    return None


def _ray_dist(bvh, bm, origin, direction, max_dist):
    """Cast a ray; return distance to first hit or None.

    Uses mathutils.bvhtree if available (typical Blender build), otherwise
    falls back to a brute-force triangle intersection (triangulated fan).
    """
    if bvh is not None:
        res = bvh.ray_cast(origin, direction, max_dist)
        if res is None or res[0] is None:
            return None
        return float(res[3])
    best = None
    for f in bm.faces:
        verts = f.verts
        if len(verts) < 3:
            continue
        # triangulate fan: (v0, vi, vi+1)
        v0 = verts[0].co
        for i in range(1, len(verts) - 1):
            hit = _tri_ray(v0, verts[i].co, verts[i + 1].co, origin, direction)
            if hit is None:
                continue
            d = (hit - origin).length
            if d < 1e-7:
                continue
            if best is None or d < best:
                best = d
        if best is not None and best < 1e-5:
            break
    if best is None:
        return None
    return best


def _tri_ray(a, b, c, origin, direction):
    """Möller–Trumbore single-triangle ray intersection; returns hit point or None."""
    eps = 1e-8
    e1 = b - a
    e2 = c - a
    pvec = direction.cross(e2)
    det = e1.dot(pvec)
    if abs(det) < eps:
        return None
    inv_det = 1.0 / det
    tvec = origin - a
    u = tvec.dot(pvec) * inv_det
    if u < 0.0 or u > 1.0:
        return None
    qvec = tvec.cross(e1)
    v = direction.dot(qvec) * inv_det
    if v < 0.0 or u + v > 1.0:
        return None
    t = e2.dot(qvec) * inv_det
    if t < eps:
        return None
    return origin + direction * t


def _diag_bbox_diagonal(diag):
    sz = diag.get("size") or [0, 0, 0]
    return (sz[0] ** 2 + sz[1] ** 2 + sz[2] ** 2) ** 0.5


def _wall_thickness(bm, bvh, diag, min_wall_mm):
    """Per-face local wall thickness via 2 ray casts (-normal & +normal)."""
    max_dist = max(_diag_bbox_diagonal(diag), 1.0)
    eps = 1e-4
    thicknesses = []
    n_under = 0
    area_under = 0.0
    total_area = 0.0
    for f in bm.faces:
        n = f.normal
        if n.length < 0.5:
            continue
        c = f.calc_center_median()
        d_in = _ray_dist(bvh, bm, c - n * eps, -n, max_dist)
        d_out = _ray_dist(bvh, bm, c + n * eps, n, max_dist)
        cand = [d for d in (d_in, d_out) if d is not None]
        if not cand:
            continue
        # thickness is min of the two cast distances (thin shell)
        t = min(cand) + eps
        a = f.calc_area()
        total_area += a
        thicknesses.append(t)
        if t < min_wall_mm:
            n_under += 1
            area_under += a
    if not thicknesses:
        return {
            "sampled_faces": 0,
            "min_mm": 0.0,
            "max_mm": 0.0,
            "avg_mm": 0.0,
            "below_threshold_faces": 0,
            "below_threshold_area_mm2": 0.0,
            "below_threshold_area_pct": 0.0,
            "total_sampled_area_mm2": 0.0,
        }
    return {
        "sampled_faces": len(thicknesses),
        "min_mm": min(thicknesses),
        "max_mm": max(thicknesses),
        "avg_mm": sum(thicknesses) / len(thicknesses),
        "below_threshold_faces": n_under,
        "below_threshold_area_mm2": area_under,
        "below_threshold_area_pct": (area_under / total_area * 100.0) if total_area > 0 else 0.0,
        "total_sampled_area_mm2": total_area,
    }


def _overhang(bm, diag, angle_deg, ground_tol_mm=0.05):
    """Faces whose normal points downward enough to need support.

    A face is classified as an overhang when:
      (a) it does NOT sit on the build plate (face center_z > ground_tol), AND
      (b) its outward normal points into the lower hemisphere such that the
          angle between the normal and the *downward* axis (-Z) is within
          the threshold. I.e. -n.z / |n| > cos(angle_deg).

    This correctly excludes upward-facing tops (n.z > 0), vertical walls
    (n.z ≈ 0), and the bottom layer that rests on the bed.
    """
    cos_thr = cos(radians(angle_deg))
    n_over = 0
    area_over = 0.0
    total_area = 0.0
    for f in bm.faces:
        n = f.normal
        if n.length < 0.5:
            continue
        cz = f.calc_center_median().z
        total_area += f.calc_area()
        if cz <= ground_tol_mm:
            continue  # bottom layer touches the bed, no support needed
        # n.z must be sufficiently negative for the face to need support
        if (-n.z) / max(n.length, 1e-9) > cos_thr:
            n_over += 1
            area_over += f.calc_area()
    return {
        "threshold_deg": angle_deg,
        "overhang_faces": n_over,
        "overhang_area_mm2": area_over,
        "total_area_mm2": total_area,
        "overhang_area_pct": (area_over / total_area * 100.0) if total_area > 0 else 0.0,
    }


def _component_min_z(bm, diag):
    """Return {component_id: (min_z, vertex_count)}.

    Builds a dict {index: BMVert} for indexed lookup — Blender 5.x no
    longer auto-maintains the BMElemSeq internal index table, so direct
    bm.verts[i] access after from_mesh may raise IndexError.
    """
    if not bm.verts:
        return {}
    vert_by_index = {v.index: v for v in bm.verts}
    visited = {}
    comp_id = 0
    minz_by_comp = {}
    cnt_by_comp = {}
    for v in bm.verts:
        if v.index in visited:
            continue
        stack = [v.index]
        visited[v.index] = comp_id
        comp_min_z = v.co.z
        comp_cnt = 0
        while stack:
            cur = stack.pop()
            cv = vert_by_index[cur]
            comp_min_z = min(comp_min_z, cv.co.z)
            comp_cnt += 1
            for e in cv.link_edges:
                for nb in e.verts:
                    if nb.index not in visited:
                        visited[nb.index] = comp_id
                        stack.append(nb.index)
        minz_by_comp[comp_id] = comp_min_z
        cnt_by_comp[comp_id] = comp_cnt
        comp_id += 1
    return {k: (minz_by_comp[k], cnt_by_comp[k]) for k in minz_by_comp}


def _floating(bm, diag, ground_tol_mm=0.05):
    """Detect components that don't touch the ground (min-Z > tol)."""
    comps = _component_min_z(bm, diag)
    if not comps:
        return {
            "total_components": 0,
            "floating_count": 0,
            "floating_verts": 0,
            "floating_pct": 0.0,
            "ground_tol_mm": ground_tol_mm,
            "components": [],
        }
    total_verts = sum(c[1] for c in comps.values())
    floating = []
    for cid, (minz, cnt) in comps.items():
        if minz > ground_tol_mm:
            floating.append({"id": cid, "min_z_mm": minz, "verts": cnt})
    return {
        "total_components": len(comps),
        "floating_count": len(floating),
        "floating_verts": sum(f["verts"] for f in floating),
        "floating_pct": (sum(f["verts"] for f in floating) / total_verts * 100.0)
                     if total_verts > 0 else 0.0,
        "ground_tol_mm": ground_tol_mm,
        "components": [
            {"id": cid, "min_z_mm": minz, "verts": cnt}
            for cid, (minz, cnt) in comps.items()
        ],
    }


def _validate(diag, wall, overhang, floating, nozzle_mm, layer_height_mm,
              min_wall_mm, supports_enabled=False):
    """Aggregate the analyses into severity-tagged issues."""
    issues = []  # list of {severity, code, message}
    if not diag.get("watertight", False):
        issues.append({
            "severity": "ERROR",
            "code": "NOT_WATERTIGHT",
            "message": "模型未水密（%d 边界边，%d 非流形边）"
                       % (diag.get("boundary_edges", 0),
                          diag.get("non_manifold_edges", 0)),
        })
    if diag.get("duplicate_vertices", 0) > 0:
        issues.append({
            "severity": "WARNING",
            "code": "DUPLICATE_VERTS",
            "message": "存在 %d 个重复顶点" % diag["duplicate_vertices"],
        })
    if diag.get("zero_area_faces", 0) > 0:
        issues.append({
            "severity": "WARNING",
            "code": "ZERO_AREA_FACES",
            "message": "存在 %d 个零面积面" % diag["zero_area_faces"],
        })
    if wall["sampled_faces"] > 0:
        if wall["min_mm"] < nozzle_mm:
            issues.append({
                "severity": "ERROR",
                "code": "WALL_BELOW_NOZZLE",
                "message": "最薄处 %.3f mm < 喷嘴 %.2f mm，打印机无法成形"
                           % (wall["min_mm"], nozzle_mm),
            })
        elif wall["min_mm"] < min_wall_mm:
            issues.append({
                "severity": "ERROR",
                "code": "WALL_BELOW_TARGET",
                "message": "最薄处 %.3f mm < 目标最低壁厚 %.2f mm"
                           % (wall["min_mm"], min_wall_mm),
            })
    if overhang["overhang_faces"] > 0:
        if not supports_enabled:
            issues.append({
                "severity": "WARNING",
                "code": "OVERHANG_UNSUPPORTED",
                "message": "%d 个悬垂面（面积 %.2f mm²，占比 %.1f%%），未启用支撑"
                           % (overhang["overhang_faces"],
                              overhang["overhang_area_mm2"],
                              overhang["overhang_area_pct"]),
            })
        else:
            issues.append({
                "severity": "INFO",
                "code": "OVERHANG_SUPPORTED",
                "message": "%d 个悬垂面已配置支撑" % overhang["overhang_faces"],
            })
    if floating["floating_count"] > 0:
        issues.append({
            "severity": "ERROR",
            "code": "FLOATING_PARTS",
            "message": "%d 个悬空部件（%d 顶点，占比 %.1f%%）"
                       % (floating["floating_count"],
                          floating["floating_verts"],
                          floating["floating_pct"]),
        })
    if layer_height_mm > nozzle_mm:
        issues.append({
            "severity": "WARNING",
            "code": "LAYER_HEIGHT_GT_NOZZLE",
            "message": "层高 %.2f mm 大于喷嘴 %.2f mm（建议层高 ≤ 0.8 × 喷嘴）"
                       % (layer_height_mm, nozzle_mm),
        })

    severity_order = {"ERROR": 3, "WARNING": 2, "INFO": 1, "OK": 0}
    if any(i["severity"] == "ERROR" for i in issues):
        severity = "ERROR"
        printable = False
    elif any(i["severity"] == "WARNING" for i in issues):
        severity = "WARNING"
        printable = True
    else:
        severity = "OK" if issues else "INFO"
        printable = True

    return {
        "printable": printable,
        "severity": severity,
        "supports_enabled": supports_enabled,
        "issues": [
            "[%s] %s" % (i["severity"], i["message"]) for i in issues
        ],
        "issue_count": len(issues),
    }


def analyze_printability(obj, min_wall_mm=0.8, nozzle_mm=0.4,
                         layer_height_mm=0.2, overhang_angle_deg=45.0,
                         supports_enabled=False, ground_tol_mm=0.05):
    """Top-level entry point. Returns a JSON-friendly dict."""
    if obj is None or obj.type != "MESH":
        raise ValueError("analyze_printability requires a MESH object")
    diag = _diag.analyze_object(obj)
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        bvh = _build_bvh(bm)
        wall = _wall_thickness(bm, bvh, diag, min_wall_mm)
        over = _overhang(bm, diag, overhang_angle_deg)
        flt = _floating(bm, diag, ground_tol_mm)
        val = _validate(diag, wall, over, flt, nozzle_mm, layer_height_mm,
                        min_wall_mm, supports_enabled)
        return {
            "object": obj.name,
            "settings": {
                "min_wall_mm": min_wall_mm,
                "nozzle_mm": nozzle_mm,
                "layer_height_mm": layer_height_mm,
                "overhang_angle_deg": overhang_angle_deg,
                "supports_enabled": supports_enabled,
                "ground_tol_mm": ground_tol_mm,
            },
            "diagnostics_summary": {
                "vertices": diag["vertices"],
                "faces": diag["faces"],
                "watertight": diag["watertight"],
                "connected_components": diag["connected_components"],
            },
            "wall_thickness": wall,
            "overhang": over,
            "floating": flt,
            "validation": val,
        }
    finally:
        bm.free()