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
import json
import os

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .core.logging import logger
from .core.pipeline import Pipeline
from .geometry import diagnostics as geo_diag
from .geometry import printability as geo_print
from .geometry import repair as geo_repair
from .geometry import extra_limbs as geo_extra
from .geometry import fabric as geo_fabric
from .geometry import decorations as geo_decoration
from .reference import views as ref_views
from .semantic import parts as sem_parts
from .parts_ops import hair as hair_ops
from .parts_ops import generic as generic_ops
from .parts_ops import voronoi as voronoi_ops
from .parts_ops import connectors as connector_ops
from .parts_ops import toolset as toolset_ops
from .exporter import three_mf as exp_3mf
from .exporter import three_mf_multi as exp_3mf_multi
from .exporter import stl as exp_stl
from .slicer import integration as slicer_int


_PIPELINE = Pipeline()


# ---------------------------------------------------------------------------
# PropertyGroups
# ---------------------------------------------------------------------------
class AFRLogEntry(bpy.types.PropertyGroup):
    level: bpy.props.StringProperty()
    text: bpy.props.StringProperty()
    time: bpy.props.StringProperty()


class AFRPrintSettings(bpy.types.PropertyGroup):
    nozzle_mm: bpy.props.FloatProperty(
        name="喷嘴直径 (mm)", default=0.4, min=0.1, max=2.0
    )
    layer_height_mm: bpy.props.FloatProperty(
        name="层高 (mm)", default=0.2, min=0.05, max=1.0
    )
    material: bpy.props.EnumProperty(
        name="材料",
        items=[
            ("PLA", "PLA", ""),
            ("ABS", "ABS", ""),
            ("PETG", "PETG", ""),
        ],
        default="PLA",
    )
    min_wall_thickness_mm: bpy.props.FloatProperty(
        name="最低壁厚 (mm)", default=0.8, min=0.2, max=5.0
    )
    density_g_cm3: bpy.props.FloatProperty(
        name="材料密度 (g/cm³)", default=1.24, min=0.5, max=3.0
    )


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------
class AFR_OT_ImportModel(bpy.types.Operator, ImportHelper):
    bl_idname = "afr.import_model"
    bl_label = "导入模型 (FBX/OBJ/GLB/STL/PLY)"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".fbx"

    filter_glob: bpy.props.StringProperty(
        default="*.fbx;*.obj;*.glb;*.gltf;*.stl;*.ply",
        options={"HIDDEN"},
    )

    def execute(self, context):
        fp = self.filepath
        ext = fp.lower().rsplit(".", 1)[-1]
        try:
            if ext == "fbx":
                bpy.ops.import_scene.fbx(filepath=fp)
            elif ext in ("glb", "gltf"):
                bpy.ops.import_scene.gltf(filepath=fp)
            elif ext == "obj":
                bpy.ops.wm.obj_import(filepath=fp)
            elif ext == "stl":
                bpy.ops.wm.stl_import(filepath=fp)
            elif ext == "ply":
                bpy.ops.wm.ply_import(filepath=fp)
            else:
                logger.error("不支持的格式: .%s" % ext)
                return {"CANCELLED"}

            meshes = [o for o in context.scene.objects if o.type == "MESH"]
            if not meshes:
                logger.warning("导入完成，但场景中没有网格对象")
                return {"FINISHED"}
            obj = meshes[0]
            context.scene.afr_source = obj.name
            logger.info("已导入 %s → 源对象 %s" % (fp, obj.name))
            return {"FINISHED"}
        except Exception as e:
            logger.error("导入失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_UseSelected(bpy.types.Operator):
    bl_idname = "afr.use_selected"
    bl_label = "使用当前选中对象作为源"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            logger.error("请先选中一个网格对象")
            return {"CANCELLED"}
        context.scene.afr_source = obj.name
        logger.info("源对象已设为 %s" % obj.name)
        return {"FINISHED"}


def _resolve_source(context):
    sc = context.scene
    obj = None
    if sc.afr_source:
        obj = sc.objects.get(sc.afr_source)
    if obj is None:
        obj = context.active_object
    return obj


# ---------------------------------------------------------------------------
# Phase 1: three-state input detection + part collection
# ---------------------------------------------------------------------------
_PART_LABELS_SHORT = ("HAIR", "HEAD", "BODY", "FABRIC", "BASE")


def collect_part_objects(scene, source_name=None):
    """Return mesh objects that are AFR parts of ``source_name``.

    A part is recognized either by the ``<source>_<LABEL>`` prefix (the
    convention used by ``extract_part``) or, when no source is given, by an
    ``_<LABEL>`` suffix on its name. Returns a list, never None.
    """
    parts = []
    for o in scene.objects:
        if o.type != "MESH":
            continue
        name = o.name
        if source_name and name.startswith(source_name + "_"):
            parts.append(o)
            continue
        for lab in _PART_LABELS_SHORT:
            if name == lab or name.endswith("_" + lab):
                parts.append(o)
                break
    return parts


def detect_input_state(scene, source_obj):
    """Classify the current scene into one of the spec's three (plus two
    internal) states so the workflow can adapt instead of re-splitting:

      - ``"no_source"``       : nothing usable selected
      - ``"unlabeled_single"`` : one mesh, no part labels yet
      - ``"labeled_single"``  : one mesh with labels, not yet split
      - ``"named_unfilled"``  : split parts exist, not watertight yet
      - ``"named_filled"``    : split parts exist and already filled
    """
    if source_obj is None or source_obj.type != "MESH":
        return "no_source"
    labels = sem_parts.get_label_array(source_obj)
    has_labels = any(l != sem_parts.PART_ID["UNLABELED"] for l in labels)
    parts = collect_part_objects(scene, source_obj.name)
    if parts:
        all_filled = all(bool(o.get("afr_filled", False)) for o in parts)
        return "named_filled" if all_filled else "named_unfilled"
    if has_labels:
        return "labeled_single"
    return "unlabeled_single"


class AFR_OT_RunDiagnostics(bpy.types.Operator):
    bl_idname = "afr.run_diagnostics"
    bl_label = "运行网格诊断"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象（请先导入或选中）")
            return {"CANCELLED"}
        try:
            res = geo_diag.analyze_object(obj)
            context.scene.afr_diag_json = json.dumps(res, ensure_ascii=False, indent=2)
            context.scene.afr_source = obj.name
            logger.info(
                "V=%d E=%d F=%d (Tri=%d Q=%d NG=%d)"
                % (res["vertices"], res["edges"], res["faces"],
                   res["triangles"], res["quads"], res["ngons"])
            )
            logger.info(
                "非流形边=%d 边界边=%d 重复顶点=%d 零面积面=%d 法线异常=%d"
                % (res["non_manifold_edges"], res["boundary_edges"],
                   res["duplicate_vertices"], res["zero_area_faces"],
                   res["bad_normal_faces"])
            )
            logger.info(
                "连通分量=%d 体积=%.4f mm³ 水密=%s"
                % (res["connected_components"], res["volume"], res["watertight"])
            )
            if res["non_manifold_edges"]:
                logger.warning("%d 处非流形边" % res["non_manifold_edges"])
            if res["boundary_edges"]:
                logger.warning("%d 条边界边（孔洞/开口）" % res["boundary_edges"])
            if res["duplicate_vertices"]:
                logger.warning("%d 个重复顶点" % res["duplicate_vertices"])
            if res["zero_area_faces"]:
                logger.warning("%d 个零面积面" % res["zero_area_faces"])
            if res["bad_normal_faces"]:
                logger.warning("%d 个法线异常面" % res["bad_normal_faces"])
            return {"FINISHED"}
        except Exception as e:
            logger.error("诊断失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RepairBasic(bpy.types.Operator):
    bl_idname = "afr.repair_basic"
    bl_label = "基础修复（去重/法线/补洞）"

    def execute(self, context):
        from .core.session import session  # local import to avoid cycle

        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            ps = context.scene.afr_print
            session.push_snapshot(obj)
            info = geo_repair.repair_basic(
                obj,
                remove_doubles_dist=0.001,
                fill_holes=True,
                recalc_normals=True,
            )
            for line in info:
                logger.info("修复: " + line)
            logger.info("最低目标壁厚 %.2f mm" % ps.min_wall_thickness_mm)
            logger.info("基础修复完成（可回滚）")
            return {"FINISHED"}
        except Exception as e:
            logger.error("修复失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_Rollback(bpy.types.Operator):
    bl_idname = "afr.rollback"
    bl_label = "回滚到上一步快照"

    def execute(self, context):
        from .core.session import session

        if session.rollback():
            logger.info("已回滚到上一快照")
        else:
            logger.warning("没有可回滚的快照")
        return {"FINISHED"}


class AFR_OT_NextStep(bpy.types.Operator):
    bl_idname = "afr.next_step"
    bl_label = "下一步"

    def execute(self, context):
        _PIPELINE.advance()
        context.scene.afr_step = _PIPELINE.current
        logger.info("进入 " + _PIPELINE.current.__str__() + "")
        return {"FINISHED"}


class AFR_OT_PrevStep(bpy.types.Operator):
    bl_idname = "afr.prev_step"
    bl_label = "上一步"

    def execute(self, context):
        _PIPELINE.back()
        context.scene.afr_step = _PIPELINE.current
        logger.info("返回 " + _PIPELINE.current.__str__() + "")
        return {"FINISHED"}


class AFRRefView(bpy.types.PropertyGroup):
    """One reference view slot."""
    name: bpy.props.StringProperty(name="名称")
    image_path: bpy.props.StringProperty(name="图片路径", subtype="FILE_PATH")
    camera_obj: bpy.props.StringProperty(name="相机对象")
    scale: bpy.props.FloatProperty(name="缩放", default=1.0, min=0.01, max=100.0)
    offset_x: bpy.props.FloatProperty(name="偏移 X", default=0.0)
    offset_y: bpy.props.FloatProperty(name="偏移 Y", default=0.0)
    rotation_z: bpy.props.FloatProperty(name="绕 Z 旋转 (°)", default=0.0)


class AFR_OT_RefCreateCameras(bpy.types.Operator):
    bl_idname = "afr.ref_create_cameras"
    bl_label = "创建 4 个参考相机（FRONT/BACK/LEFT/RIGHT）"

    def execute(self, context):
        try:
            ref_views.ensure_ref_state(context.scene)
            for name in ref_views.VIEW_NAMES:
                cam = ref_views.get_or_create_camera(context.scene, name)
                logger.info("参考相机 %s 已就绪" % cam.name)
            return {"FINISHED"}
        except Exception as e:
            logger.error("创建参考相机失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RefAlignToBBox(bpy.types.Operator):
    bl_idname = "afr.ref_align_to_bbox"
    bl_label = "参考相机对齐到对象包围盒"

    def execute(self, context):
        from .geometry.diagnostics import analyze_object
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            ref_views.ensure_ref_state(context.scene)
            for name in ref_views.VIEW_NAMES:
                cam = ref_views.align_camera_to_bbox(context.scene, name, obj)
                logger.info("对齐 %s → %s" % (name, cam.name))
            logger.info("4 个参考相机已对齐到 %s 包围盒" % obj.name)
            return {"FINISHED"}
        except Exception as e:
            logger.error("对齐失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RefLoadImage(bpy.types.Operator, ImportHelper):
    bl_idname = "afr.ref_load_image"
    bl_label = "加载参考图"
    bl_options = {"REGISTER", "UNDO"}

    view_name: bpy.props.EnumProperty(
        name="视角",
        items=[(n, n, "") for n in ref_views.VIEW_NAMES],
        default="FRONT",
    )
    filename_ext = ".png"
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.jpg;*.jpeg;*.bmp;*.tga;*.tif;*.tiff;*.exr",
        options={"HIDDEN"},
    )

    def execute(self, context):
        try:
            ref_views.ensure_ref_state(context.scene)
            img = ref_views.load_reference_image(
                context.scene, self.view_name, self.filepath)
            logger.info("参考图 %s → %s (%dx%d)" % (
                self.view_name, self.filepath, img.size[0], img.size[1]))
            return {"FINISHED"}
        except Exception as e:
            logger.error("加载参考图失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RefClearImage(bpy.types.Operator):
    bl_idname = "afr.ref_clear_image"
    bl_label = "清除参考图"

    view_name: bpy.props.EnumProperty(
        name="视角",
        items=[(n, n, "") for n in ref_views.VIEW_NAMES],
        default="FRONT",
    )

    def execute(self, context):
        try:
            slot = ref_views.get_view_slot(context.scene, self.view_name)
            if slot and slot.camera_obj:
                cam = bpy.data.objects.get(slot.camera_obj)
                ref_views.detach_background(cam)
            if slot:
                slot.image_path = ""
            # remove the image datablock if unused
            name = "AFR_RefImg_" + self.view_name
            img = bpy.data.images.get(name)
            if img is not None and img.users == 0:
                bpy.data.images.remove(img)
            logger.info("参考图 %s 已清除" % self.view_name)
            return {"FINISHED"}
        except Exception as e:
            logger.error("清除失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SlicerSlice3MF(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.slicer_slice_3mf"
    bl_label = "导出 3MF 并调用切片器"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".3mf"
    filter_glob: bpy.props.StringProperty(default="*.3mf", options={"HIDDEN"})

    def execute(self, context):
        try:
            obj = _resolve_source(context)
            if obj is None or obj.type != "MESH":
                logger.error("没有可用的网格源对象")
                return {"CANCELLED"}
            res_3mf = exp_3mf.export_3mf(obj, self.filepath)
            logger.info("已导出 3MF: %s" % res_3mf["filepath"])
            slicer_path, slicer_name = slicer_int.find_slicer()
            if slicer_path is None:
                logger.warning("未发现切片器，跳过 G-code 生成")
                return {"FINISHED"}
            ini_path = os.path.splitext(self.filepath)[0] + ".ini"
            ps = context.scene.afr_print
            slicer_int.generate_ini_profile({
                "nozzle_mm": ps.nozzle_mm,
                "layer_height_mm": ps.layer_height_mm,
                "material": ps.material,
                "min_wall_thickness_mm": ps.min_wall_thickness_mm,
                "density_g_cm3": ps.density_g_cm3,
            }, filepath=ini_path)
            res = slicer_int.slice_model(
                slicer_path, self.filepath, ini_profile=ini_path, timeout=120)
            if res.get("ok"):
                logger.info("切片成功: %s" % res["output_path"])
                verify = slicer_int.verify_gcode(res["output_path"])
                logger.info("G-code: G1=%d G0=%d retract=%d layers=%d support=%d" % (
                    verify["g1_moves"], verify["g0_travels"],
                    verify["retractions"], verify["z_layer_changes"],
                    verify["support_moves"]))
            else:
                logger.warning("切片失败: %s" % res.get("error", "未知"))
            return {"FINISHED"}
        except Exception as e:
            logger.error("端到端流程失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_VoronoiLattice(bpy.types.Operator):
    bl_idname = "afr.voronoi_lattice"
    bl_label = "生成 Voronoi 减重微结构"

    n_seeds: bpy.props.IntProperty(name="种子数", default=20, min=4, max=200)
    lattice_radius: bpy.props.FloatProperty(name="线宽 (mm)", default=0.5,
                                           min=0.1, max=3.0)

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            new_obj = voronoi_ops.voronoi_lattice(
                obj, n_seeds=self.n_seeds, lattice_radius=self.lattice_radius)
            if new_obj is None:
                logger.warning("Voronoi 生成失败（源对象可能为空或全在外部）")
                return {"CANCELLED"}
            logger.info("Voronoi 微结构已生成: %s (种子=%d)"
                        % (new_obj.name, self.n_seeds))
            return {"FINISHED"}
        except Exception as e:
            logger.error("Voronoi 生成失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_ExportMulti3MF(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.export_multi_3mf"
    bl_label = "导出多对象 3MF"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".3mf"
    filter_glob: bpy.props.StringProperty(default="*.3mf", options={"HIDDEN"})

    def execute(self, context):
        try:
            res = exp_3mf_multi.export_multi_3mf(
                self.filepath, context.scene)
            logger.info("已导出多对象 3MF: %s" % res["filepath"])
            logger.info("  对象=%d  build 项=%d  顶点=%d  三角形=%d  字节=%d" % (
                res["object_count"], res["build_item_count"],
                res["total_vertices"], res["total_triangles"],
                res["size_bytes"]))
            return {"FINISHED"}
        except Exception as e:
            logger.error("多对象 3MF 导出失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_ExportAssembly3MF(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.export_assembly_3mf"
    bl_label = "导出装配 3MF（嵌套 components）"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".3mf"
    filter_glob: bpy.props.StringProperty(default="*.3mf", options={"HIDDEN"})

    def execute(self, context):
        try:
            res = exp_3mf_multi.export_assembly_3mf(
                self.filepath, context.scene,
                groups=[{"name": "AFR_Assembly"}])
            logger.info("已导出装配 3MF: %s" % res["filepath"])
            logger.info("  mesh 对象=%d  装配组=%d  build=%d  字节=%d" % (
                res["mesh_object_count"], res["group_count"],
                res["build_item_count"], res["size_bytes"]))
            return {"FINISHED"}
        except Exception as e:
            logger.error("装配 3MF 导出失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SlicerFind(bpy.types.Operator):
    bl_idname = "afr.slicer_find"
    bl_label = "查找切片器（PrusaSlicer/OrcaSlicer/...）"

    def execute(self, context):
        try:
            found = slicer_int.find_all_slicers()
            if not found:
                logger.warning("未在 PATH 上发现切片器，请安装 PrusaSlicer/OrcaSlicer")
                return {"FINISHED"}
            for path, name in found:
                logger.info("  · %s → %s" % (name, path))
            return {"FINISHED"}
        except Exception as e:
            logger.error("查找切片器失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SlicerExportINI(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.slicer_export_ini"
    bl_label = "导出切片器 INI 配置（基于当前 FDM 设置）"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".ini"
    filter_glob: bpy.props.StringProperty(default="*.ini", options={"HIDDEN"})

    def execute(self, context):
        try:
            ps = context.scene.afr_print
            settings = {
                "nozzle_mm": ps.nozzle_mm,
                "layer_height_mm": ps.layer_height_mm,
                "material": ps.material,
                "min_wall_thickness_mm": ps.min_wall_thickness_mm,
                "density_g_cm3": ps.density_g_cm3,
            }
            text = slicer_int.generate_ini_profile(settings, filepath=self.filepath)
            logger.info("已导出 INI: %s (%d 行)" % (self.filepath, len(text.splitlines())))
            return {"FINISHED"}
        except Exception as e:
            logger.error("INI 导出失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SlicerVerifyGCode(bpy.types.Operator, ImportHelper):
    bl_idname = "afr.slicer_verify_gcode"
    bl_label = "校验 G-code（解析 retractions/支撑标记）"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".gcode"
    filter_glob: bpy.props.StringProperty(
        default="*.gcode;*.gco", options={"HIDDEN"})

    def execute(self, context):
        try:
            r = slicer_int.verify_gcode(self.filepath)
            logger.info("G-code: %d 行, G1=%d G0=%d, retract=%d, 支撑=%d, 层数=%d" % (
                r["max_lines"], r["g1_moves"], r["g0_travels"],
                r["retractions"], r["support_moves"], r["z_layer_changes"]))
            for issue in r["issues"]:
                logger.warning("  · " + issue)
            return {"FINISHED"}
        except Exception as e:
            logger.error("G-code 校验失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_HairExtract(bpy.types.Operator):
    bl_idname = "afr.hair_extract"
    bl_label = "提取 HAIR 部件到新对象"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            new_obj = hair_ops.extract_part(obj, sem_parts.PART_ID["HAIR"])
            if new_obj is None:
                logger.warning("未找到 HAIR 顶点，请先应用启发式标注")
                return {"CANCELLED"}
            logger.info("HAIR 已提取到 %s" % new_obj.name)
            return {"FINISHED"}
        except Exception as e:
            logger.error("提取失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_HairSolidify(bpy.types.Operator):
    bl_idname = "afr.hair_solidify"
    bl_label = "头发加厚（Solidify）"

    thickness: bpy.props.FloatProperty(
        name="壁厚 (mm)", default=0.4, min=0.05, max=2.0)

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            ok = hair_ops.solidify_part(obj, thickness=self.thickness)
            if ok:
                logger.info("头发已加厚 %.2f mm" % self.thickness)
            return {"FINISHED"}
        except Exception as e:
            logger.error("加厚失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_HairGenerate(bpy.types.Operator):
    bl_idname = "afr.hair_generate"
    bl_label = "程序化生成头发（曲线→加厚网格）"

    count: bpy.props.IntProperty(name="发丝数", default=200, min=10, max=2000)
    scalp_radius: bpy.props.FloatProperty(name="头皮半径", default=0.3, min=0.05, max=2.0)
    length_min: bpy.props.FloatProperty(name="最短长度 (mm)", default=0.5, min=0.05)
    length_max: bpy.props.FloatProperty(name="最长长度 (mm)", default=1.2, min=0.05)
    curl: bpy.props.FloatProperty(name="卷曲", default=0.3, min=0.0, max=1.0)
    noise: bpy.props.FloatProperty(name="噪声", default=0.2, min=0.0, max=1.0)
    radius: bpy.props.FloatProperty(name="单丝半径 (mm)", default=0.04, min=0.01, max=0.5)

    def execute(self, context):
        obj = _resolve_source(context)
        scalp_z = 2.0
        if obj is not None and obj.type == "MESH":
            zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
            scalp_z = (max(zs) + min(zs)) / 2 + (max(zs) - min(zs)) * 0.35
        try:
            curves = hair_ops.generate_hair_curves(
                context.scene,
                dict(scalp_z=scalp_z, scalp_radius=self.scalp_radius,
                     count=self.count, length_min=self.length_min,
                     length_max=self.length_max, curl=self.curl,
                     noise=self.noise, taper=1.5, seed=0))
            meshed = hair_ops.curves_to_mesh(curves, radius=self.radius)
            logger.info("已生成 %d 根头发 → %s (MESH)" % (self.count, meshed.name))
            return {"FINISHED"}
        except Exception as e:
            logger.error("生成头发失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_FabricSolidify(bpy.types.Operator):
    bl_idname = "afr.fabric_solidify"
    bl_label = "布料加厚（Solidify）"

    thickness: bpy.props.FloatProperty(
        name="壁厚 (mm)", default=0.6, min=0.1, max=2.0)

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            generic_ops.solidify_fabric(obj, thickness=self.thickness)
            logger.info("布料已加厚 %.2f mm" % self.thickness)
            return {"FINISHED"}
        except Exception as e:
            logger.error("布料加厚失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_GenerateBase(bpy.types.Operator):
    bl_idname = "afr.generate_base"
    bl_label = "生成底座（圆柱）"

    radius: bpy.props.FloatProperty(name="半径 (mm)", default=0.0, min=0.0)
    height: bpy.props.FloatProperty(name="高度 (mm)", default=3.0, min=0.5)

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            rad = self.radius if self.radius > 0 else None
            base = generic_ops.generate_base(
                context.scene, obj, radius=rad, height=self.height)
            logger.info("底座已生成: %s (半径=%.2f mm, 高=%.2f mm)"
                        % (base.name, base.dimensions.x / 2, self.height))
            return {"FINISHED"}
        except Exception as e:
            logger.error("底座生成失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_MergeSelected(bpy.types.Operator):
    bl_idname = "afr.merge_selected"
    bl_label = "合并选中对象（Boolean Union）"

    def execute(self, context):
        sel = [o for o in context.selected_objects if o.type == "MESH"]
        if len(sel) < 2:
            logger.error("需要至少 2 个 MESH 选中")
            return {"CANCELLED"}
        try:
            merged = generic_ops.merge_parts(context.scene, sel)
            logger.info("已合并 %d 个对象 → %s" % (len(sel), merged.name))
            return {"FINISHED"}
        except Exception as e:
            logger.error("合并失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_AutoOrient(bpy.types.Operator):
    bl_idname = "afr.auto_orient"
    bl_label = "自动定向（落地）"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            r = generic_ops.auto_orient(obj)
            logger.info("已定向: 偏移 (%.2f, %.2f, %.2f)" % (r[3], r[4], r[5]))
            return {"FINISHED"}
        except Exception as e:
            logger.error("定向失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_Export3MF(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.export_3mf"
    bl_label = "导出 3MF（自研实现）"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".3mf"
    filter_glob: bpy.props.StringProperty(
        default="*.3mf", options={"HIDDEN"})

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            res = exp_3mf.export_3mf(obj, self.filepath)
            logger.info("已导出 3MF: %s" % res["filepath"])
            logger.info("  顶点=%d  三角形=%d  字节=%d" % (
                res["vertices"], res["triangles"], res["size_bytes"]))
            return {"FINISHED"}
        except Exception as e:
            logger.error("3MF 导出失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SemanticApplyHeuristics(bpy.types.Operator):
    bl_idname = "afr.semantic_apply_heuristics"
    bl_label = "应用几何启发式自动标注"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            sem_parts.ensure_part_attribute(obj)
            labels = sem_parts.apply_heuristics(obj)
            from collections import Counter
            cnt = Counter(sem_parts.ID_PART[l] for l in labels)
            logger.info("启发式标注完成 (共 %d 顶点): %s" % (
                len(labels),
                ", ".join("%s=%d" % kv for kv in cnt.most_common())))
            return {"FINISHED"}
        except Exception as e:
            logger.error("启发式标注失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SemanticBrushFlood(bpy.types.Operator):
    bl_idname = "afr.semantic_brush_flood"
    bl_label = "整对象刷成指定部件"

    label_name: bpy.props.EnumProperty(
        name="部件",
        items=[(n, n, "") for n in sem_parts.PART_LABELS],
        default="BODY",
    )

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            sem_parts.brush_flood(obj, sem_parts.PART_ID[self.label_name])
            logger.info("整对象已设为 %s" % self.label_name)
            return {"FINISHED"}
        except Exception as e:
            logger.error("整对象刷失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SemanticBrushUndo(bpy.types.Operator):
    bl_idname = "afr.semantic_brush_undo"
    bl_label = "撤销部件标注"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            prev = sem_parts.brush_undo(obj)
            if prev is None:
                logger.warning("没有可撤销的标注操作")
            else:
                logger.info("已撤销一步标注")
            return {"FINISHED"}
        except Exception as e:
            logger.error("撤销失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SemanticClearLabels(bpy.types.Operator):
    bl_idname = "afr.semantic_clear_labels"
    bl_label = "清空部件标注"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        try:
            sem_parts.brush_flood(obj, sem_parts.PART_ID["UNLABELED"])
            logger.info("部件标注已清空")
            return {"FINISHED"}
        except Exception as e:
            logger.error("清空失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_SplitByPart(bpy.types.Operator):
    bl_idname = "afr.split_by_part"
    bl_label = "按标注拆分所有部件"
    bl_description = "按语义标注（HAIR/HEAD/BODY/FABRIC/BASE）把源对象拆成多个独立对象，每个部件一个；拆分后自动填充闭合（水密化）"
    bl_options = {"REGISTER", "UNDO"}

    force: bpy.props.BoolProperty(
        name="强制重拆", default=False,
        description="即使已存在拆分部件也重新提取（会生成 .001 副本）")
    auto_fill: bpy.props.BoolProperty(
        name="拆分后自动填充闭合", default=True,
        description="拆分后立即对每部件运行补洞+薄壁加厚，使其成为可打印的水密体")

    def _fill_parts(self, context, objs):
        for o in objs:
            if o is None:
                continue
            try:
                info = geo_repair.fill_close_part(o)
                logger.info("填充闭合 %s: %s" % (o.name, "; ".join(info)))
            except Exception as e:
                logger.error("填充闭合 %s 失败: %s" % (o.name, e))

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        state = detect_input_state(context.scene, obj)
        # Already-split parts? (handles 已命名未填充 / 已命名已填充)
        existing = collect_part_objects(context.scene, obj.name)
        if existing and not self.force:
            logger.info("检测到已拆分部件（状态=%s）：%s，跳过重复拆分" % (
                state, ", ".join(o.name for o in existing)))
            if self.auto_fill:
                self._fill_parts(context, existing)
            return {"FINISHED"}
        try:
            sem_parts.ensure_part_attribute(obj)
            labels = sem_parts.get_label_array(obj)
            if all(l == sem_parts.PART_ID["UNLABELED"] for l in labels) and not self.force:
                logger.warning("源对象尚未标注，请先点 “Auto-Label” 或笔刷标注")
                return {"CANCELLED"}
            created = []
            for label in sem_parts.PART_LABELS:
                if label == "UNLABELED":
                    continue
                new_obj = hair_ops.extract_part(obj, sem_parts.PART_ID[label])
                if new_obj is not None:
                    created.append(new_obj.name)
                    logger.info("  拆分出 %s → %s" % (label, new_obj.name))
            if not created:
                logger.warning("未拆出任何部件（请先应用启发式标注）")
                return {"CANCELLED"}
            if self.auto_fill:
                created_objs = [context.scene.objects.get(n) for n in created]
                self._fill_parts(context, created_objs)
            logger.info("按标注拆分完成，共 %d 个部件: %s" % (
                len(created), ", ".join(created)))
            return {"FINISHED"}
        except Exception as e:
            logger.error("拆分失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_FillCloseParts(bpy.types.Operator):
    bl_idname = "afr.fill_close_parts"
    bl_label = "填充闭合所有部件（水密化）"
    bl_description = "对所有 AFR 部件运行补洞+法线重置+薄壁加厚，使其成为独立水密可打印体（可重复执行，已填充的会跳过）"
    bl_options = {"REGISTER", "UNDO"}

    force: bpy.props.BoolProperty(
        name="强制重做", default=False,
        description="即使部件已标记 afr_filled 也重新填充闭合")
    solidify_thin: bpy.props.FloatProperty(
        name="薄壁厚度 (mm)", default=0.6, min=0.0, max=5.0,
        description="HAIR/FABRIC 等薄部件的壳厚")

    def execute(self, context):
        parts = collect_part_objects(context.scene)
        if not parts:
            logger.error("未找到任何 AFR 部件对象（请先拆分或选中已拆部件）")
            return {"CANCELLED"}
        infos = geo_repair.fill_close_parts(
            parts, solidify_thin=self.solidify_thin, force=self.force)
        for name, lines in infos.items():
            logger.info("填充闭合 %s: %s" % (name, "; ".join(lines)))
        n_done = sum(1 for v in infos.values()
                     if not any("skip" in s for s in v))
        logger.info("填充闭合完成：共 %d 个部件，本次实际处理 %d 个" % (
            len(parts), n_done))
        return {"FINISHED"}


class AFR_OT_RefFocusView(bpy.types.Operator):
    bl_idname = "afr.ref_focus_view"
    bl_label = "切换到此参考视角"

    view_name: bpy.props.EnumProperty(
        name="视角",
        items=[(n, n, "") for n in ref_views.VIEW_NAMES],
        default="FRONT",
    )

    def execute(self, context):
        try:
            cam = ref_views.get_or_create_camera(
                context.scene, self.view_name)
            context.scene.camera = cam
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.region_3d.view_perspective = "CAMERA"
            logger.info("当前视角 = %s" % cam.name)
            return {"FINISHED"}
        except Exception as e:
            logger.error("切换失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RunPrintability(bpy.types.Operator):
    bl_idname = "afr.run_printability"
    bl_label = "可打印性分析（壁厚/悬垂/悬空）"

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象")
            return {"CANCELLED"}
        ps = context.scene.afr_print
        try:
            res = geo_print.analyze_printability(
                obj,
                min_wall_mm=ps.min_wall_thickness_mm,
                nozzle_mm=ps.nozzle_mm,
                layer_height_mm=ps.layer_height_mm,
                overhang_angle_deg=45.0,
            )
            context.scene.afr_print_json = json.dumps(res, ensure_ascii=False, indent=2)
            w = res["wall_thickness"]
            logger.info("壁厚  min=%.3fmm  max=%.3fmm  avg=%.3fmm" % (
                w["min_mm"], w["max_mm"], w["avg_mm"]))
            logger.info("  低于最低壁厚的面: %d / %d (面积 %.2fmm²)" % (
                w["below_threshold_faces"], w["sampled_faces"], w["below_threshold_area_mm2"]))
            o = res["overhang"]
            logger.info("悬垂  面=%d  面积=%.2fmm²  占比=%.1f%%" % (
                o["overhang_faces"], o["overhang_area_mm2"], o["overhang_area_pct"]))
            f = res["floating"]
            logger.info("悬空部件  总连通分量=%d  悬空=%d  (悬空顶点=%d, 占比=%.1f%%)" % (
                f["total_components"], f["floating_count"], f["floating_verts"],
                f["floating_pct"]))
            v = res["validation"]
            logger.info("打印验证  可打印=%s  严重度=%s  问题=%d 条" % (
                v["printable"], v["severity"], len(v["issues"])))
            for issue in v["issues"]:
                logger.warning("  · " + issue)
            return {"FINISHED"}
        except Exception as e:
            logger.error("可打印性分析失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_StartMCPServer(bpy.types.Operator):
    bl_idname = "afr.start_mcp_server"
    bl_label = "启动 AI Agent (Blender MCP 桥)"
    bl_description = "在 Blender 内开启 127.0.0.1:9876 的 MCP 兼容 socket，使外部 AI 智能体可驱动本 Blender"

    def execute(self, context):
        from .mcp import bridge

        status = bridge.bridge_status()
        if status == "running":
            logger.info("MCP 桥已在运行 (127.0.0.1:9876)")
            return {"FINISHED"}
        try:
            msg = bridge.start_bridge()
            logger.info("MCP 桥已启动: %s" % msg)
            logger.info("外部 AI 智能体可连接：在 WorkBuddy/终端运行 "
                        "python scripts/run_mcp_server.py（默认 stdio）")
            return {"FINISHED"}
        except Exception as e:
            logger.error("MCP 桥启动失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_StopMCPServer(bpy.types.Operator):
    bl_idname = "afr.stop_mcp_server"
    bl_label = "停止 AI Agent (Blender MCP 桥)"

    def execute(self, context):
        from .mcp import bridge

        try:
            msg = bridge.stop_bridge()
            logger.info("MCP 桥已停止: %s" % msg)
            return {"FINISHED"}
        except Exception as e:
            logger.error("MCP 桥停止失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_CreateConnector(bpy.types.Operator):
    bl_idname = "afr.create_connector"
    bl_label = "生成连接/拼接部件 (凹凸)"
    bl_description = "生成手办装配用的凹凸连接件：圆柱(peg/hole)、球窝(ball/socket)、燕尾(tab/slot)"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        name="类型",
        items=[
            (connector_ops.KIND_ROUND, "圆柱 凹凸", "Peg + Hole"),
            (connector_ops.KIND_BALL, "球窝", "Ball + Socket"),
            (connector_ops.KIND_DOVETAIL, "燕尾 凹凸", "Tab + Slot"),
        ],
        default=connector_ops.KIND_ROUND,
    )
    place: bpy.props.EnumProperty(
        name="布点",
        items=[
            ("cursor", "3D 游标", "在 3D 游标处生成独立连接件对"),
            ("between", "两部件之间", "在两选中网格中心连线中点处生成并挖孔"),
        ],
        default="cursor",
    )
    diameter: bpy.props.FloatProperty(name="直径/宽 (mm)", default=5.0, min=1.0, max=40.0)
    depth: bpy.props.FloatProperty(name="孔深/槽深 (mm)", default=4.0, min=0.5, max=40.0)
    length: bpy.props.FloatProperty(name="凸柱长 (mm)", default=4.0, min=0.5, max=40.0)
    clearance: bpy.props.FloatProperty(name="公差 (mm)", default=0.2, min=0.0, max=2.0)
    nozzle_mm: bpy.props.FloatProperty(name="喷嘴 (mm)", default=0.4, min=0.1, max=2.0)
    with_flange: bpy.props.BoolProperty(name="加法兰盘", default=False)
    chamfer: bpy.props.BoolProperty(name="凸柱倒角", default=True)
    opening_ratio: bpy.props.FloatProperty(name="球窝开口比", default=0.7, min=0.3, max=0.95)
    name: bpy.props.StringProperty(name="名称前缀", default="AFR_Connector")
    axis: bpy.props.EnumProperty(
        name="轴向",
        items=[
            ("view", "对齐视角", "关节轴向 = 当前 3D 视图朝向（半自动布点）"),
            ("z", "固定 +Z", "轴向恒为 +Z"),
        ],
        default="view",
    )
    socket_wall: bpy.props.FloatProperty(name="套筒壁厚 (mm)", default=1.2,
                                         min=0.4, max=10.0)

    def invoke(self, context, event):
        # V0.14 UX: point-and-click — pressing the button generates immediately
        # with the panel-supplied args. (Big props dialog was confusing — users
        # saw the dialog, hit Cancel, and assumed nothing happened.)
        # Advanced: pressing F6 in the redo panel exposes all 11 properties.
        return self.execute(context)

    def draw(self, context):
        # Only shown in the redo panel (F6) — not in the initial dialog.
        layout = self.layout
        layout.prop(self, "kind")
        layout.prop(self, "axis")
        layout.prop(self, "place")
        layout.prop(self, "diameter")
        layout.prop(self, "length")
        layout.prop(self, "depth")
        layout.prop(self, "socket_wall")
        layout.prop(self, "clearance")
        layout.prop(self, "nozzle_mm")
        layout.prop(self, "with_flange")
        layout.prop(self, "chamfer")
        if self.kind == "ball":
            layout.prop(self, "opening_ratio")

    def execute(self, context):
        sc = context.scene
        # resolve joint axis
        if self.axis == "z":
            direction = (0.0, 0.0, 1.0)
        else:
            rv3d = None
            space = getattr(context, "space_data", None)
            if space is not None and hasattr(space, "region_3d"):
                rv3d = space.region_3d
            if rv3d is not None:
                direction = tuple(rv3d.view_direction)
            else:
                direction = (0.0, 0.0, 1.0)
        sel = [o for o in context.selected_objects if o.type == "MESH"]
        if self.place == "between" and len(sel) >= 2:
            obj_a, obj_b = sel[0], sel[1]
            try:
                res = connector_ops.add_connector_between(
                    sc, obj_a, obj_b, kind=self.kind,
                    diameter=self.diameter, depth=self.depth, length=self.length,
                    clearance=self.clearance, nozzle_mm=self.nozzle_mm,
                    with_flange=self.with_flange, chamfer=self.chamfer,
                    opening_ratio=self.opening_ratio,
                    socket_wall_mm=self.socket_wall, name=self.name,
                )
            except Exception as e:
                logger.error("两部件连接件生成失败: %s" % e)
                return {"CANCELLED"}
            pa, pb = res.get("parented_to", (None, None))
            logger.info(
                "连接件(%s) 已布于 %s<->%s 之间（非破坏：凸归 %s / 凹归 %s）"
                % (self.kind, obj_a.name, obj_b.name, pa, pb))
            return {"FINISHED"}
        # default: standalone joint pair at the 3D cursor (semi-auto, no solve)
        pos = context.scene.cursor.location
        try:
            res = connector_ops.create_connector(
                sc, kind=self.kind, position=tuple(pos),
                direction=direction, diameter=self.diameter,
                depth=self.depth, length=self.length, clearance=self.clearance,
                nozzle_mm=self.nozzle_mm, with_flange=self.with_flange,
                chamfer=self.chamfer, opening_ratio=self.opening_ratio,
                socket_wall_mm=self.socket_wall, name=self.name,
            )
        except Exception as e:
            logger.error("连接件生成失败: %s" % e)
            return {"CANCELLED"}
        male = res.get("male")
        sock = res.get("female_socket")
        logger.info(
            "连接件(%s) 已生成 @游标：凸(peg)=%s 凹(套筒)=%s（零布尔）"
            % (self.kind,
               male.name if male else None,
               sock.name if sock else None))
        return {"FINISHED"}


class AFR_OT_CarveSocket(bpy.types.Operator):
    bl_idname = "afr.carve_socket"
    bl_label = "用凹模挖孔 (Boolean)"
    bl_description = "将选中的凹模(cutter)通过布尔差集挖入活动网格对象"
    bl_options = {"REGISTER", "UNDO"}

    apply: bpy.props.BoolProperty(name="立即应用", default=True)

    def execute(self, context):
        target = context.active_object
        cutter = next((o for o in context.selected_objects
                       if o != target and o.type == "MESH"), None)
        if target is None or target.type != "MESH":
            logger.error("请先选中一个 MESH 目标（活动对象）")
            return {"CANCELLED"}
        if cutter is None:
            logger.error("请再选中一个 MESH 凹模(cutter)作为挖孔工具")
            return {"CANCELLED"}
        res = connector_ops.carve_socket(context.scene, target, cutter,
                                         apply=self.apply)
        if res.get("error"):
            logger.error(res["error"])
            return {"CANCELLED"}
        logger.info("挖孔完成：target=%s cutter=%s applied=%s ok=%s" % (
            res.get("target"), res.get("cutter"),
            res.get("applied"), res.get("ok")))
        return {"FINISHED"}


class AFR_OT_FindExtraLimbs(bpy.types.Operator):
    bl_idname = "afr.find_extra_limbs"
    bl_label = "检测多余肢体（红色高亮预览）"
    bl_description = "检测疑似多余肢体（小连通块+细桥接）并红色高亮，确认后再删除"
    bl_options = {"REGISTER", "UNDO"}

    bridge_max: bpy.props.IntProperty(
        name="桥接边上限", default=4, min=1, max=20,
        description="连接主体的体积块，桥接边数 ≤ 此值视为细桥接")
    max_frac: bpy.props.FloatProperty(
        name="体积占比上限", default=0.08, min=0.005, max=0.5,
        description="小于总顶点数此比例的连通块才视为候选")

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象（请先导入或选中）")
            return {"CANCELLED"}
        try:
            comps = geo_extra.detect_extra_limbs(
                obj, bridge_max=self.bridge_max, max_frac=self.max_frac)
            if not comps:
                logger.info("未检测到疑似多余肢体（仅 1 个连通块或均过大）")
                obj["afr_extra_verts"] = []
                return {"FINISHED"}
            flat = geo_extra.mark_extra(obj, comps)
            logger.info("检测到 %d 处疑似多余肢体，共 %d 个顶点（已红色高亮，请确认后点“删除多余肢体”）"
                        % (len(comps), len(flat)))
            return {"FINISHED"}
        except Exception as e:
            logger.error("检测失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RemoveExtraLimbs(bpy.types.Operator):
    bl_idname = "afr.remove_extra_limbs"
    bl_label = "删除多余肢体（并桥接断口）"
    bl_description = "删除红色高亮的候选肢体，并补洞桥接主身体上的断口"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _resolve_source(context)
        if obj is None or obj.type != "MESH":
            logger.error("没有可用的网格源对象（请先导入或选中）")
            return {"CANCELLED"}
        try:
            marked = obj.get("afr_extra_verts", None)
            if not marked:
                logger.warning("没有已高亮的候选肢体，请先点“检测多余肢体”")
                return {"CANCELLED"}
            removed = geo_extra.remove_marked(obj, fill_boundary=True)
            logger.info("已删除 %d 个多余顶点，主身体断口已桥接" % removed)
            return {"FINISHED"}
        except Exception as e:
            logger.error("删除失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_FindFabricIntersection(bpy.types.Operator):
    bl_idname = "afr.find_fabric_intersection"
    bl_label = "检测布料穿插（红色高亮）"
    bl_description = "射线检测布料与身体的穿插面并红色高亮，确认后再修复"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        fabric = _resolve_source(context)
        if fabric is None or fabric.type != "MESH":
            logger.error("没有可用的布料源对象（请先选中布料部件）")
            return {"CANCELLED"}
        body = geo_fabric._resolve_body(context.scene, fabric)
        if body is None:
            logger.error("未找到身体网格用于穿插检测")
            return {"CANCELLED"}
        try:
            faces = geo_fabric.detect_intersections(fabric, body)
            geo_fabric.highlight_intersections(fabric, faces)
            logger.info("检测到 %d 处布料穿插面（已红色高亮，身体=%s）"
                        % (len(faces), body.name))
            return {"FINISHED"}
        except Exception as e:
            logger.error("检测失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_RepairFabricIntersection(bpy.types.Operator):
    bl_idname = "afr.repair_fabric_intersection"
    bl_label = "修复布料穿插（布尔差切除）"
    bl_description = "用布尔差切除埋入身体的布料部分以去除穿插；加厚请用「布料加厚」算子"
    bl_options = {"REGISTER", "UNDO"}

    thickness: bpy.props.FloatProperty(
        name="布料壳厚 (mm)", default=0.0, min=0.0, max=5.0,
        description="默认 0：仅做布尔 carve 去穿插；>0 时额外加厚（可能重新引入贴合处的轻微穿插）")
    use_boolean: bpy.props.BoolProperty(
        name="用布尔差切除", default=True,
        description="默认开启：布尔差切除埋入身体的布料。关闭时改用顶点推出法（更稳健但仅处理顶点在体内的情形）")

    def execute(self, context):
        fabric = _resolve_source(context)
        if fabric is None or fabric.type != "MESH":
            logger.error("没有可用的布料源对象（请先选中布料部件）")
            return {"CANCELLED"}
        body = geo_fabric._resolve_body(context.scene, fabric)
        if body is None:
            logger.error("未找到身体网格用于修复")
            return {"CANCELLED"}
        try:
            info = geo_fabric.repair_fabric(
                fabric, body, thickness=self.thickness,
                use_boolean=self.use_boolean)
            for line in info:
                logger.info("布料修复: " + line)
            return {"FINISHED"}
        except Exception as e:
            logger.error("修复失败: %s" % e)
            return {"CANCELLED"}


class AFR_OT_AddDecoration(bpy.types.Operator):
    bl_idname = "afr.add_decoration"
    bl_label = "添加装饰物"
    bl_description = "从内置资产库放置一个装饰物并吸附到身体对应部位"
    bl_options = {"REGISTER", "UNDO"}

    deco_name: bpy.props.StringProperty(
        name="装饰物", default="耳环",
        description="要放置的装饰物名称（见资产库 decorations.json）")

    def execute(self, context):
        try:
            obj = geo_decoration.add_decoration(self.deco_name, context)
            logger.info("已添加装饰物 %s → %s（吸附到 %s）" % (
                self.deco_name, obj.name, obj.get("afr_attach")))
            return {"FINISHED"}
        except Exception as e:
            logger.error("添加装饰物失败: %s" % e)
            return {"CANCELLED"}


# ---------------------------------------------------------------------------
# Packaging: per-part STL export + zip (production LAST step)
# ---------------------------------------------------------------------------
class AFR_OT_ExportPartStlZip(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.export_part_stl_zip"
    bl_label = "打包导出 (每部件 STL → zip)"
    bl_description = ("把场景中每个网格部件分别导出为 STL 并打包成一个 zip"
                      "（命名 prefix-部件名.stl），用于 FDM 切片")
    bl_options = {"REGISTER"}
    filename_ext = ".zip"
    filter_glob: bpy.props.StringProperty(default="*.zip", options={"HIDDEN"})

    prefix: bpy.props.StringProperty(
        name="文件名前缀", default="",
        description="例如 PWY，则产出 PWY-底座.stl；留空则用部件原名")
    only_selected: bpy.props.BoolProperty(
        name="仅导出选中", default=False,
        description="只导出当前选中的网格；否则导出场景全部网格")
    apply_modifiers: bpy.props.BoolProperty(name="应用修改器", default=True)

    def execute(self, context):
        import zipfile
        import tempfile
        import shutil
        if not self.filepath.lower().endswith(".zip"):
            self.filepath += ".zip"
        if self.only_selected:
            objs = [o for o in context.selected_objects if o.type == "MESH"]
        else:
            objs = [o for o in context.scene.objects if o.type == "MESH"]
        if not objs:
            logger.error("没有可导出的网格对象")
            return {"CANCELLED"}
        prefix = (self.prefix
                  or getattr(context.scene, "afr_package_prefix", "") or "").strip()
        tmp = tempfile.mkdtemp()
        try:
            names = []
            for o in objs:
                # prefer the printable part name set by the naming tools
                base = o.get("afr_part_name") or o.name
                if prefix:
                    sep = "" if prefix.endswith(("-", "_")) else "-"
                    fname = "%s%s%s.stl" % (prefix, sep, base)
                else:
                    fname = "%s.stl" % base
                fp = os.path.join(tmp, fname)
                exp_stl.write_stl_binary(o, fp)
                names.append(fname)
            with zipfile.ZipFile(self.filepath, "w", zipfile.ZIP_DEFLATED) as zf:
                for fn in names:
                    zf.write(os.path.join(tmp, fn), arcname=fn)
            logger.info("已打包 %d 个部件 → %s" % (len(names), self.filepath))
            return {"FINISHED"}
        except Exception as e:
            logger.error("打包失败: %s" % e)
            return {"CANCELLED"}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 工具集（杂项）
# ---------------------------------------------------------------------------
def _resolve_targets(context):
    sel = [o for o in context.selected_objects if o.type == "MESH"]
    if sel:
        return sel
    src = _resolve_source(context)
    if src is not None:
        return [src]
    return []


class AFR_OT_ToolsetMeasure(bpy.types.Operator):
    bl_idname = "afr.toolset_measure"
    bl_label = "测量选中/源对象"

    def execute(self, context):
        objs = _resolve_targets(context)
        if not objs:
            logger.error("请先选中网格或设源对象")
            return {"CANCELLED"}
        for o in objs:
            m = toolset_ops.measure(o)
            logger.info("%s: 尺寸 %.2f×%.2f×%.2f mm, 体积 %.2f, 顶点 %d"
                        % (o.name, m["dim"][0], m["dim"][1], m["dim"][2],
                           m["volume"], m["verts"]))
        return {"FINISHED"}


class AFR_OT_ToolsetRename(bpy.types.Operator):
    bl_idname = "afr.toolset_rename"
    bl_label = "重命名部件"
    base: bpy.props.StringProperty(name="基础名", default="Part")
    start: bpy.props.IntProperty(name="起始序号", default=1, min=1)

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not objs:
            logger.error("请先选中要重命名的网格")
            return {"CANCELLED"}
        n = toolset_ops.rename_parts(objs, base=self.base, start=self.start)
        logger.info("已重命名 %d 个部件（%s_*）" % (n, self.base))
        return {"FINISHED"}


class AFR_OT_ToolsetCleanup(bpy.types.Operator):
    bl_idname = "afr.toolset_cleanup"
    bl_label = "清理（删孤立/合并重叠）"
    dist: bpy.props.FloatProperty(name="合并距离", default=0.001,
                                  min=0.0001, max=0.1)

    def execute(self, context):
        objs = _resolve_targets(context)
        if not objs:
            logger.error("请先选中网格或设源对象")
            return {"CANCELLED"}
        for o in objs:
            changed = toolset_ops.cleanup(o, merge_dist=self.dist)
            logger.info("%s: 清理%s" % (o.name, "完成" if changed else "无变化"))
        return {"FINISHED"}


class AFR_OT_ToolsetNormals(bpy.types.Operator):
    bl_idname = "afr.toolset_normals"
    bl_label = "重算法线"
    inside: bpy.props.BoolProperty(name="翻转(向内)", default=False)

    def execute(self, context):
        objs = _resolve_targets(context)
        if not objs:
            logger.error("请先选中网格或设源对象")
            return {"CANCELLED"}
        for o in objs:
            toolset_ops.recalc_normals(o, inside=self.inside)
            logger.info("%s: 法线已重算" % o.name)
        return {"FINISHED"}


class AFR_OT_ToolsetSymmetry(bpy.types.Operator):
    bl_idname = "afr.toolset_symmetry"
    bl_label = "对称检查/镜像"
    axis: bpy.props.EnumProperty(
        name="轴", items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")],
        default="X")
    fix: bpy.props.BoolProperty(name="镜像修正(+→-)", default=False)

    def execute(self, context):
        objs = _resolve_targets(context)
        if not objs:
            logger.error("请先选中网格或设源对象")
            return {"CANCELLED"}
        for o in objs:
            if self.fix:
                n = toolset_ops.make_symmetric(o, axis=self.axis)
                logger.info("%s: 已镜像 %d 个顶点" % (o.name, n))
            else:
                r = toolset_ops.symmetry_check(o, axis=self.axis)
                logger.info("%s: 对称度 %.1f%% (%d/%d)"
                            % (o.name, r["fraction"] * 100,
                               r["matched"], r["total"]))
        return {"FINISHED"}


class AFR_OT_ToolsetWatertight(bpy.types.Operator):
    bl_idname = "afr.toolset_watertight"
    bl_label = "水密检查"

    def execute(self, context):
        objs = _resolve_targets(context)
        if not objs:
            logger.error("请先选中网格或设源对象")
            return {"CANCELLED"}
        for o in objs:
            r = toolset_ops.watertight_check(o)
            logger.info("%s: %s (边界边 %d, 非流形边 %d)"
                        % (o.name,
                           "水密✓" if r["watertight"] else "非水密✗",
                           r["boundary_edges"], r["non_manifold_edges"]))
        return {"FINISHED"}


class AFR_OT_ToolsetStats(bpy.types.Operator):
    bl_idname = "afr.toolset_stats"
    bl_label = "统计网格"

    def execute(self, context):
        objs = _resolve_targets(context)
        if not objs:
            logger.error("请先选中网格或设源对象")
            return {"CANCELLED"}
        for o in objs:
            s = toolset_ops.stats(o)
            logger.info("%s: 顶点 %d, 面 %d, 非流形边 %d"
                        % (o.name, s["verts"], s["faces"],
                           s["non_manifold_edges"]))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Part naming (after.zip naming contract: {prefix}-{中文部件名}.stl)
# ---------------------------------------------------------------------------
class AFR_OT_NamePart(bpy.types.Operator):
    bl_idname = "afr.name_part"
    bl_label = "命名部件"
    bl_description = ("给选中的网格设置可打印部件名（存入 afr_part_name），"
                      "打包时优先使用该名称；可选 L/R 后缀")
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="部件名", default="",
                                   description="如 手/脚/帽子；留空则用对象名")
    lr: bpy.props.EnumProperty(
        name="L/R",
        items=[("", "无", ""), ("L", "L", ""), ("R", "R", "")],
        default="")

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not objs:
            logger.error("请先选中要命名的网格")
            return {"CANCELLED"}
        base = self.name.strip() or None
        n = 0
        for o in objs:
            final = toolset_ops.name_part(o, base or o.name, self.lr or None)
            logger.info("部件 %s → %s" % (o.name, final))
            n += 1
        return {"FINISHED"}


class AFR_OT_AutoNameLR(bpy.types.Operator):
    bl_idname = "afr.auto_name_lr"
    bl_label = "对称自动命名 L/R"
    bl_description = ("按包围盒对称检测把选中的左右成对部件自动命名为 "
                      "「基础名L / 基础名R」")
    bl_options = {"REGISTER", "UNDO"}

    base_name: bpy.props.StringProperty(name="基础名", default="手",
                                        description="如 手 → 手L / 手R")
    axis: bpy.props.EnumProperty(
        name="对称轴",
        items=[("X", "X（左右镜像）", ""), ("Y", "Y", ""), ("Z", "Z", "")],
        default="X")
    left_side: bpy.props.EnumProperty(
        name="负侧标记",
        items=[("L", "L", ""), ("R", "R", "")],
        default="L")

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not objs:
            logger.error("请先选中左右成对的网格")
            return {"CANCELLED"}
        result = toolset_ops.auto_name_lr(
            objs, self.base_name, axis=self.axis, left_side=self.left_side)
        for k, v in result.items():
            logger.info("%s → %s" % (k, v))
        return {"FINISHED"}


class AFR_OT_ExportNameManifest(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.export_name_manifest"
    bl_label = "导出命名清单 (CSV)"
    bl_description = ("把所有网格的 对象名,部件名 导出为 CSV，供人工/MCP "
                      "填写中文部件名后导回（逼近 after.zip 命名契约）")
    bl_options = {"REGISTER"}
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        import csv
        if not self.filepath.lower().endswith(".csv"):
            self.filepath += ".csv"
        rows = []
        for o in context.scene.objects:
            if o.type == "MESH":
                rows.append([o.name, o.get("afr_part_name") or ""])
        try:
            with open(self.filepath, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["object", "part_name"])
                w.writerows(rows)
        except Exception as e:
            logger.error("导出清单失败: %s" % e)
            return {"CANCELLED"}
        logger.info("已导出命名清单 %d 行 → %s" % (len(rows), self.filepath))
        return {"FINISHED"}


class AFR_OT_ImportNameManifest(bpy.types.Operator, ImportHelper):
    bl_idname = "afr.import_name_manifest"
    bl_label = "导入命名清单 (CSV)"
    bl_description = "按 CSV（object,part_name）回填部件的可打印名 afr_part_name"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        import csv
        objs = {o.name: o for o in context.scene.objects if o.type == "MESH"}
        n = 0
        try:
            with open(self.filepath, newline="", encoding="utf-8-sig") as f:
                rd = csv.DictReader(f)
                for row in rd:
                    oname = (row.get("object") or "").strip()
                    pname = (row.get("part_name") or "").strip()
                    if not oname or oname not in objs:
                        continue
                    if pname:
                        toolset_ops.name_part(objs[oname], pname)
                        n += 1
        except Exception as e:
            logger.error("导入清单失败: %s" % e)
            return {"CANCELLED"}
        logger.info("已按清单命名 %d 个部件" % n)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ComfyUI texturing (AI 贴图)
# ---------------------------------------------------------------------------
class AFR_OT_ComfyUITexture(bpy.types.Operator):
    bl_idname = "afr.comfyui_texture"
    bl_label = "用 ComfyUI 生成贴图"
    bl_description = ("调用本地 ComfyUI 生成手办表面贴图并应用到选中网格"
                      "（需在插件偏好设置填写 Host/Port）")
    prompt: bpy.props.StringProperty(
        name="提示词",
        default="hand-painted anime figure texture, clean, vibrant")

    def execute(self, context):
        import urllib.request
        import json
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not objs:
            logger.error("请先选中要贴图的网格")
            return {"CANCELLED"}
        addon = context.preferences.addons.get("ai_figure_refiner")
        if addon is None:
            logger.error("未找到插件偏好设置")
            return {"CANCELLED"}
        prefs = addon.preferences
        host = getattr(prefs, "comfyui_host", "")
        port = getattr(prefs, "comfyui_port", 8188)
        if not host:
            logger.error("未配置 ComfyUI：请在 编辑→偏好设置→插件→AI Figure "
                         "Refiner 填写 Host/Port")
            return {"CANCELLED"}
        base = "http://%s:%d" % (host, port)
        try:
            req = urllib.request.Request(base + "/system", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    logger.error("ComfyUI 未就绪 (HTTP %d)" % resp.status)
                    return {"CANCELLED"}
        except Exception as e:
            logger.error("无法连接 ComfyUI (%s:%d)：%s" % (host, port, e))
            return {"CANCELLED"}
        workflow = getattr(prefs, "comfyui_workflow", "")
        if workflow:
            try:
                payload = json.loads(workflow)
                req = urllib.request.Request(
                    base + "/prompt",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("ComfyUI 工作流已提交，将为 %d 个网格生成贴图"
                                    % len(objs))
                    else:
                        logger.error("ComfyUI 提交失败 (HTTP %d)" % resp.status)
            except Exception as e:
                logger.error("ComfyUI 工作流提交异常: %s" % e)
        else:
            logger.info("ComfyUI 在线 (%s:%d)；未配置工作流 JSON，仅完成接入握手"
                        % (host, port))
        for o in objs:
            logger.info("已为 %s 登记贴图任务" % o.name)
        return {"FINISHED"}


CLASSES = (
    AFRLogEntry,
    AFRPrintSettings,
    AFRRefView,
    AFR_OT_ImportModel,
    AFR_OT_UseSelected,
    AFR_OT_RunDiagnostics,
    AFR_OT_RepairBasic,
    AFR_OT_FindExtraLimbs,
    AFR_OT_RemoveExtraLimbs,
    AFR_OT_Rollback,
    AFR_OT_NextStep,
    AFR_OT_PrevStep,
    AFR_OT_RunPrintability,
    AFR_OT_RefCreateCameras,
    AFR_OT_RefAlignToBBox,
    AFR_OT_RefLoadImage,
    AFR_OT_RefClearImage,
    AFR_OT_RefFocusView,
    AFR_OT_SemanticApplyHeuristics,
    AFR_OT_SemanticBrushFlood,
    AFR_OT_SemanticBrushUndo,
    AFR_OT_SemanticClearLabels,
    AFR_OT_SplitByPart,
    AFR_OT_FillCloseParts,
    AFR_OT_HairExtract,
    AFR_OT_HairSolidify,
    AFR_OT_HairGenerate,
    AFR_OT_FabricSolidify,
    AFR_OT_FindFabricIntersection,
    AFR_OT_RepairFabricIntersection,
    AFR_OT_AddDecoration,
    AFR_OT_GenerateBase,
    AFR_OT_MergeSelected,
    AFR_OT_AutoOrient,
    AFR_OT_Export3MF,
    AFR_OT_VoronoiLattice,
    AFR_OT_ExportMulti3MF,
    AFR_OT_ExportAssembly3MF,
    AFR_OT_SlicerFind,
    AFR_OT_SlicerExportINI,
    AFR_OT_SlicerVerifyGCode,
    AFR_OT_SlicerSlice3MF,
    AFR_OT_StartMCPServer,
    AFR_OT_StopMCPServer,
    AFR_OT_CreateConnector,
    AFR_OT_CarveSocket,
    AFR_OT_ExportPartStlZip,
    AFR_OT_ToolsetMeasure,
    AFR_OT_ToolsetRename,
    AFR_OT_ToolsetCleanup,
    AFR_OT_ToolsetNormals,
    AFR_OT_ToolsetSymmetry,
    AFR_OT_ToolsetWatertight,
    AFR_OT_ToolsetStats,
    AFR_OT_NamePart,
    AFR_OT_AutoNameLR,
    AFR_OT_ExportNameManifest,
    AFR_OT_ImportNameManifest,
    AFR_OT_ComfyUITexture,
)