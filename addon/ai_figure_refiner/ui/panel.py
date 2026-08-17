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