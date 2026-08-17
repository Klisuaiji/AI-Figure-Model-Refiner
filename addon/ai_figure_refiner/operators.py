import json

import bpy
from bpy_extras.io_utils import ImportHelper

from .core.logging import logger
from .core.pipeline import Pipeline
from .geometry import diagnostics as geo_diag
from .geometry import printability as geo_print
from .geometry import repair as geo_repair
from .reference import views as ref_views
from .semantic import parts as sem_parts


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


CLASSES = (
    AFRLogEntry,
    AFRPrintSettings,
    AFRRefView,
    AFR_OT_ImportModel,
    AFR_OT_UseSelected,
    AFR_OT_RunDiagnostics,
    AFR_OT_RepairBasic,
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
)