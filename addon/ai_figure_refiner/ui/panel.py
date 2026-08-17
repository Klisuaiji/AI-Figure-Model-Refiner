import bpy

from ..core.pipeline import STEPS, STEP_COUNT, step_name


class AFR_PT_Main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_label = "AI 手办模型精修器"

    def draw(self, context):
        sc = context.scene
        layout = self.layout

        # --- Import / Source -------------------------------------------------
        box = layout.box()
        box.label(text="导入 / 源对象", icon="IMPORT")
        box.operator("afr.import_model", icon="FILEBROWSER")
        box.operator("afr.use_selected", icon="HAND")
        box.prop(sc, "afr_source", text="源对象")

        # --- Step progress ---------------------------------------------------
        layout.separator()
        step = sc.afr_step
        box = layout.box()
        box.label(text="步骤进度")
        box.label(text=step_name(step))
        row = box.row(align=True)
        op = row.operator("afr.prev_step", text="", icon="TRIA_LEFT")
        op = row.operator("afr.next_step", text="", icon="TRIA_RIGHT")
        for i in range(STEP_COUNT):
            row = box.row()
            row.label(text=("●" if i == step else "○") + "  " + STEPS[i][1])

        # --- Diagnostics & Repair -------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="网格诊断与修复", icon="MESH_DATA")
        box.operator("afr.run_diagnostics", icon="VIEWZOOM")
        box.operator("afr.repair_basic", icon="BRUSH_DATA")
        box.operator("afr.rollback", icon="LOOP_BACK")

        if sc.afr_diag_json:
            box = layout.box()
            box.label(text="最近一次诊断", icon="INFO")
            for line in sc.afr_diag_json.splitlines()[:20]:
                box.label(text=line)

        # --- Printability ---------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="可打印性分析", icon="PRINT")
        box.operator("afr.run_printability", icon="VIEWZOOM")
        if sc.afr_print_json:
            box.label(text="最近一次可打印性", icon="INFO")
            for line in sc.afr_print_json.splitlines()[:24]:
                box.label(text=line)

        # --- Reference images ----------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="参考图系统 (FRONT/BACK/LEFT/RIGHT)", icon="IMAGE")
        box.operator("afr.ref_create_cameras", icon="CAMERA_DATA")
        box.operator("afr.ref_align_to_bbox", icon="FULLSCREEN_ENTER")
        from ..reference.views import VIEW_NAMES
        for vname in VIEW_NAMES:
            row = box.row(align=True)
            row.label(text=vname)
            op = row.operator("afr.ref_focus_view", text="切换", icon="HAND")
            op.view_name = vname
            op = row.operator("afr.ref_load_image", text="图", icon="FILE_IMAGE")
            op.view_name = vname
            op = row.operator("afr.ref_clear_image", text="", icon="X")
            op.view_name = vname

        # --- Semantic parts --------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="部件语义识别 (HAIR/HEAD/BODY/FABRIC/BASE)", icon="GROUP_VCOL")
        box.operator("afr.semantic_apply_heuristics", icon="AUTO")
        row = box.row(align=True)
        op = row.operator("afr.semantic_brush_flood", text="全设为 BODY", icon="BRUSH_DATA")
        op.label_name = "BODY"
        op = row.operator("afr.semantic_brush_flood", text="全清空", icon="X")
        op.label_name = "UNLABELED"
        box.operator("afr.semantic_brush_undo", icon="LOOP_BACK")

        # --- Hair refinement ------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="头发精修 (Phase 5)", icon="HAIR")
        box.operator("afr.hair_extract", icon="MESH_DATA")
        op = box.operator("afr.hair_solidify", icon="MOD_SOLIDIFY")
        op.thickness = ps.min_wall_thickness_mm
        box.operator("afr.hair_generate", icon="CURVE_DATA")

        # --- Fabric / Base / Merge / Orient ----------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="布料/底座/合并/定向 (Phase 6-9)", icon="TOOL_SETTINGS")
        op = box.operator("afr.fabric_solidify", icon="MOD_SOLIDIFY")
        op.thickness = ps.min_wall_thickness_mm
        box.operator("afr.generate_base", icon="MESH_CIRCLE")
        box.operator("afr.merge_selected", icon="GROUP")
        box.operator("afr.auto_orient", icon="ORPHAN_DATA")
        box.operator("afr.voronoi_lattice", icon="MOD_WIREFRAME")

        # --- Export ---------------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="导出 (Phase 11 + V0.6 多对象)", icon="FILE_TICK")
        box.operator("afr.export_3mf", icon="EXPORT")
        box.operator("afr.export_multi_3mf", icon="EXPORT")
        box.operator("afr.export_assembly_3mf", icon="FILE_3D")

        # --- Slicer ---------------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="切片器集成 (V0.6/V0.7)", icon="SCRIPT")
        box.operator("afr.slicer_find", icon="VIEWZOOM")
        box.operator("afr.slicer_export_ini", icon="FILE_TEXT")
        box.operator("afr.slicer_verify_gcode", icon="CHECKMARK")

        # --- AI Worker ------------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="AI Worker (Phase 12 — 外部)", icon="NETWORK")
        box.operator("afr.ai_worker_check", icon="QUESTION")
        box.operator("afr.ai_stub_test", icon="PLAY")

        # --- Print settings --------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="FDM 打印参数", icon="PRINT_SETTINGS")
        ps = sc.afr_print
        box.prop(ps, "nozzle_mm")
        box.prop(ps, "layer_height_mm")
        box.prop(ps, "material")
        box.prop(ps, "min_wall_thickness_mm")
        box.prop(ps, "density_g_cm3")

        # --- Log -------------------------------------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="日志", icon="TEXT")
        if not sc.afr_log:
            box.label(text="(无)")
        for entry in reversed(list(sc.afr_log)[-30:]):
            icon = "ERROR" if entry.level == "ERROR" else (
                "ERROR" if entry.level == "WARNING" else "TEXT"
            )
            box.label(text="[%s] %s  %s" % (entry.level, entry.time, entry.text),
                      icon=icon)