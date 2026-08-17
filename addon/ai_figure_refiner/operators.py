import json

import bpy
from bpy_extras.io_utils import ImportHelper

from .core.logging import logger
from .core.pipeline import Pipeline
from .geometry import diagnostics as geo_diag
from .geometry import repair as geo_repair


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


CLASSES = (
    AFRLogEntry,
    AFRPrintSettings,
    AFR_OT_ImportModel,
    AFR_OT_UseSelected,
    AFR_OT_RunDiagnostics,
    AFR_OT_RepairBasic,
    AFR_OT_Rollback,
    AFR_OT_NextStep,
    AFR_OT_PrevStep,
)