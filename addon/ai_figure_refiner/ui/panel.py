"""V0.12 — Toolset N-Panel UI.

The fixed-step workflow is replaced by an on-demand **toolset**: one main
panel ("AI 手办模型工具") with a 4-quadrant preview area (前/后/左/右) and
independent, collapsible tool sub-panels the user runs as needed:

  * 拆分部件  — semantic labeling + split into per-part objects
  * 头发修正  — extract / solidify / procedural hair
  * 布料修正  — fabric solidify
  * 人物修正  — diagnostics / repair / orient / merge / rollback
  * 打印计算  — FDM params / printability / base / Voronoi infill
  * 导出调试  — 3MF exports / slicer integration / log
  * 连接/拼接部件 (V0.11) — solver-free convex/concave joints
  * AI 智能体 (MCP) — Blender MCP bridge for external agents

Sub-panels start collapsed (``DEFAULT_CLOSED``) so the panel reads as a clean
tool list — expand only what you need.
"""
import bpy


class AFR_PT_Main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_label = "AI 手办模型工具"

    def draw(self, context):
        sc = context.scene
        layout = self.layout

        box = layout.box()
        box.label(text="工具集模式：按需执行，不再按固定流程", icon="TOOL_SETTINGS")
        box.label(text="1) 导入/选中手办  2) 展开所需工具执行", icon="INFO")

        # --- Source object ------------------------------------------------
        box = layout.box()
        box.label(text="源对象", icon="IMPORT")
        box.operator("afr.import_model", icon="FILEBROWSER")
        box.operator("afr.use_selected", icon="HAND")
        box.prop(sc, "afr_source", text="源对象")

        # --- 4-quadrant preview (前/后/左/右) ------------------------------
        box = layout.box()
        box.label(text="预览（四视图：前/后/左/右）", icon="IMAGE")
        box.label(text="点击切换到参考视角；Ctrl+Alt+Q 开启 Quad View", icon="INFO")
        row = box.row(align=True)
        row.operator("afr.ref_focus_view", text="前 Front").view_name = "FRONT"
        row.operator("afr.ref_focus_view", text="后 Back").view_name = "BACK"
        row = box.row(align=True)
        row.operator("afr.ref_focus_view", text="左 Left").view_name = "LEFT"
        row.operator("afr.ref_focus_view", text="右 Right").view_name = "RIGHT"
        row = box.row(align=True)
        row.operator("afr.ref_create_cameras", text="创建参考相机", icon="CAMERA_DATA")
        row.operator("afr.ref_align_to_bbox", text="对齐包围盒", icon="FULLSCREEN_ENTER")


class AFR_PT_Tool_Split(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "拆分部件"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.label(text="先标注，后拆分；每个部件独立成对象", icon="GROUP_VCOL")
        layout.operator("afr.semantic_apply_heuristics", icon="AUTO")
        layout.operator("afr.split_by_part", icon="MESH_DATA")
        row = layout.row(align=True)
        op = row.operator("afr.semantic_brush_flood", text="全设为 BODY", icon="BRUSH_DATA")
        op.label_name = "BODY"
        op = row.operator("afr.semantic_brush_flood", text="全清空", icon="X")
        op.label_name = "UNLABELED"
        layout.operator("afr.semantic_brush_undo", icon="LOOP_BACK")


class AFR_PT_Tool_Hair(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "头发修正"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        ps = context.scene.afr_print
        layout = self.layout
        layout.label(text="提取 / 加厚 / 程序化生成", icon="HAIR")
        layout.operator("afr.hair_extract", icon="MESH_DATA")
        op = layout.operator("afr.hair_solidify", icon="MOD_SOLIDIFY")
        op.thickness = ps.min_wall_thickness_mm
        layout.operator("afr.hair_generate", icon="CURVE_DATA")


class AFR_PT_Tool_Fabric(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "布料修正"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        ps = context.scene.afr_print
        layout = self.layout
        layout.label(text="布料加厚（Solidify）", icon="MOD_CLOTH")
        op = layout.operator("afr.fabric_solidify", icon="MOD_SOLIDIFY")
        op.thickness = ps.min_wall_thickness_mm


class AFR_PT_Tool_Figure(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "人物修正"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc = context.scene
        layout = self.layout
        layout.label(text="诊断 → 修复 → 定向/合并", icon="ARMATURE_DATA")
        layout.operator("afr.run_diagnostics", icon="VIEWZOOM")
        if sc.afr_diag_json:
            for line in sc.afr_diag_json.splitlines()[:12]:
                layout.label(text=line)
        layout.separator()
        layout.operator("afr.repair_basic", icon="BRUSH_DATA")
        layout.operator("afr.auto_orient", icon="ORPHAN_DATA")
        layout.operator("afr.merge_selected", icon="GROUP")
        layout.operator("afr.rollback", icon="LOOP_BACK")


class AFR_PT_Tool_Print(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "打印计算"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        ps = context.scene.afr_print
        sc = context.scene
        layout = self.layout
        layout.label(text="FDM 参数", icon="PRINT_SETTINGS")
        layout.prop(ps, "nozzle_mm")
        layout.prop(ps, "layer_height_mm")
        layout.prop(ps, "material")
        layout.prop(ps, "min_wall_thickness_mm")
        layout.prop(ps, "density_g_cm3")
        layout.separator()
        layout.operator("afr.run_printability", icon="VIEWZOOM")
        if sc.afr_print_json:
            for line in sc.afr_print_json.splitlines()[:16]:
                layout.label(text=line)
        layout.separator()
        layout.operator("afr.generate_base", icon="MESH_CIRCLE")
        layout.operator("afr.voronoi_lattice", icon="MOD_WIREFRAME")


class AFR_PT_Tool_Connector(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "连接/拼接部件 (半自动·零布尔, V0.11)"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.label(text="移动 3D 游标到接缝 → 生成 凸柱+套筒", icon="INFO")
        layout.operator("afr.create_connector", icon="PLUS").kind = "round"
        row = layout.row(align=True)
        row.operator("afr.create_connector", icon="SPHERE").kind = "ball"
        row.operator("afr.create_connector", icon="MOD_WEDGE").kind = "dovetail"
        layout.operator("afr.carve_socket", icon="MOD_BOOLEAN")


class AFR_PT_Tool_Agent(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "AI 智能体 (MCP 接口)"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.label(text="在 Blender 内开启 MCP 兼容桥，外部 AI 智能体可驱动本实例",
                     icon="INFO")
        row = layout.row(align=True)
        row.operator("afr.start_mcp_server", icon="PLAY", text="启动桥")
        row.operator("afr.stop_mcp_server", icon="PAUSE", text="停止桥")
        layout.label(text="外部启动 MCP 服务器（AI 智能体侧）：", icon="CONSOLE")
        layout.label(text="  python scripts/run_mcp_server.py")
        layout.label(text="  python scripts/run_mcp_server.py --transport streamable-http --port 8000")


class AFR_PT_Tool_Export(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "导出调试"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc = context.scene
        layout = self.layout
        layout.label(text="导出 (3MF)", icon="FILE_TICK")
        layout.operator("afr.export_3mf", icon="EXPORT")
        layout.operator("afr.export_multi_3mf", icon="EXPORT")
        layout.operator("afr.export_assembly_3mf", icon="FILE_3D")
        layout.separator()
        layout.label(text="切片器集成", icon="SCRIPT")
        layout.operator("afr.slicer_find", icon="VIEWZOOM")
        layout.operator("afr.slicer_export_ini", icon="FILE_TEXT")
        layout.operator("afr.slicer_verify_gcode", icon="CHECKMARK")
        layout.operator("afr.slicer_slice_3mf", icon="EXPORT")
        layout.separator()
        layout.label(text="日志", icon="TEXT")
        if not sc.afr_log:
            layout.label(text="(无)")
        recent = list(sc.afr_log)[-30:]
        for entry in reversed(recent):
            icon = "ERROR" if entry.level in ("ERROR", "WARNING") else "TEXT"
            layout.label(text="[%s] %s  %s" % (entry.level, entry.time, entry.text),
                         icon=icon)


PANELS = (
    AFR_PT_Main,
    AFR_PT_Tool_Split,
    AFR_PT_Tool_Hair,
    AFR_PT_Tool_Fabric,
    AFR_PT_Tool_Figure,
    AFR_PT_Tool_Print,
    AFR_PT_Tool_Connector,
    AFR_PT_Tool_Agent,
    AFR_PT_Tool_Export,
)
