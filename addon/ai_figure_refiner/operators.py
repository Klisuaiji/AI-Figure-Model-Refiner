import json

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .core.logging import logger
from .core.pipeline import Pipeline
from .geometry import diagnostics as geo_diag
from .geometry import printability as geo_print
from .geometry import repair as geo_repair
from .reference import views as ref_views
from .semantic import parts as sem_parts
from .parts_ops import hair as hair_ops
from .parts_ops import generic as generic_ops
from .parts_ops import voronoi as voronoi_ops
from .exporter import three_mf as exp_3mf
from .exporter import three_mf_multi as exp_3mf_multi
from .slicer import integration as slicer_int
from .ai_worker import launcher as ai_launcher
from .ai_worker import protocol as ai_protocol
from .training import export as training_export


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


class AFR_OT_AIWorkerCall(bpy.types.Operator):
    bl_idname = "afr.ai_worker_call"
    bl_label = "调用 AI Worker（subprocess 实际运行）"

    model: bpy.props.EnumProperty(
        name="模型",
        items=[(n, n, "") for n in ai_protocol.SUPPORTED_MODELS],
        default="figure_seg",
    )
    task: bpy.props.StringProperty(name="任务", default="segment")

    def execute(self, context):
        worker = ai_launcher.find_worker()
        if worker is None:
            logger.warning("AI worker 未找到，使用 stub 响应")
            req = ai_protocol.make_request(self.model, self.task,
                                           inputs={"object_name": "<none>"})
            resp = ai_launcher.stub_worker_response(req)
        else:
            obj = _resolve_source(context)
            inputs = {"object_name": obj.name if obj else "<none>"}
            if obj is not None and obj.type == "MESH":
                inputs = ai_protocol.mesh_to_inputs(obj)
            req = ai_protocol.make_request(self.model, self.task,
                                           inputs=inputs)
            logger.info("调用 AI worker: %s → %s" % (worker, self.model))
            try:
                resp = ai_protocol.call_sync(worker, req, timeout=120)
            except Exception as e:
                logger.error("worker 调用失败: %s" % e)
                return {"CANCELLED"}
        ok = ai_protocol.is_ok(resp)
        logger.info("AI worker 响应: ok=%s" % ok)
        for k, v in (resp.get("outputs") or {}).items():
            if isinstance(v, (str, int, float, bool)):
                logger.info("  · %s = %s" % (k, v))
        if not ok:
            logger.warning("worker 返回失败: %s" % resp.get("error"))
        return {"FINISHED"}


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


class AFR_OT_ExportTrainingData(bpy.types.Operator, ExportHelper):
    bl_idname = "afr.export_training_data"
    bl_label = "导出训练数据（V0.7 manifest JSON）"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            res = training_export.export_training_data(
                context.scene, self.filepath, ref_views_module=ref_views)
            logger.info("训练数据已导出: %s" % res["filepath"])
            logger.info("  项数=%d  字节=%d  schema=%d" % (
                res["item_count"], res["size_bytes"], res["schema"]))
            return {"FINISHED"}
        except Exception as e:
            logger.error("训练数据导出失败: %s" % e)
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


class AFR_OT_AIWorkerCheck(bpy.types.Operator):
    bl_idname = "afr.ai_worker_check"
    bl_label = "检查 AI Worker 状态"

    def execute(self, context):
        st = ai_launcher.launch_or_message()
        if st.get("ok"):
            logger.info("AI worker 就绪: %s" % st["worker"])
        else:
            logger.warning("AI worker 未找到")
            for hint in (st.get("hint", ""),):
                logger.warning("  · " + hint)
        return {"FINISHED"}


class AFR_OT_AIStubTest(bpy.types.Operator):
    bl_idname = "afr.ai_stub_test"
    bl_label = "测试 AI Worker 协议（Stub）"

    def execute(self, context):
        req = ai_protocol.make_request(
            model="figure_seg", task="segment",
            inputs={"object_name": "test", "vertices": [[0, 0, 0]],
                    "faces": []})
        resp = ai_launcher.stub_worker_response(req)
        logger.info("Stub response: ok=%s stub=%s" % (
            resp.get("ok"), resp.get("stub")))
        return {"FINISHED"}


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
    AFR_OT_HairExtract,
    AFR_OT_HairSolidify,
    AFR_OT_HairGenerate,
    AFR_OT_FabricSolidify,
    AFR_OT_GenerateBase,
    AFR_OT_MergeSelected,
    AFR_OT_AutoOrient,
    AFR_OT_Export3MF,
    AFR_OT_AIWorkerCheck,
    AFR_OT_AIStubTest,
    AFR_OT_VoronoiLattice,
    AFR_OT_ExportMulti3MF,
    AFR_OT_ExportAssembly3MF,
    AFR_OT_SlicerFind,
    AFR_OT_SlicerExportINI,
    AFR_OT_SlicerVerifyGCode,
    AFR_OT_AIWorkerCall,
    AFR_OT_SlicerSlice3MF,
    AFR_OT_ExportTrainingData,
)