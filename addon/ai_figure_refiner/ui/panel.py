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
"""V0.12 — Toolset N-Panel UI.

The fixed-step workflow is replaced by an on-demand **toolset**: one main
panel ("AI 手办模型工具") with a 4-quadrant reference-image area (前/后/左/右,
the front photo is mandatory) and independent, collapsible tool sub-panels
the user runs as needed:

  * 拆分部件  — semantic labeling + split into per-part objects
  * 头发修正  — extract / solidify / procedural hair
  * 布料修正  — fabric solidify
  * 人物修正  — diagnostics / repair / orient / merge / rollback
  * 打印计算  — FDM params / printability / base / Voronoi infill
  * 导出调试  — 3MF exports / slicer integration / log
  * 连接/拼接部件 (V0.11) — solver-free convex/concave joints
  * AI 智能体 (MCP) — Blender MCP bridge for external agents

Sub-panels are unfolded by default so the entire toolset is immediately
visible (collapse whatever you don't need with the triangle on the left).

V0.13: the 4-quadrant area is now a **reference-image uploader** for the
multimodal AI agent (front photo mandatory) that assists part labeling.

V0.14 (hotfix 2026-08-20):
  * sub-panels: removed DEFAULT_CLOSED — all 8 tools visible by default
  * main panel: bigger callouts for "set source / move 3D cursor" workflows
  * connector panel: inline hint about cursor placement + axis dropdown
"""
import os

import bpy

from ..reference import views as ref_views
from ..geometry import decorations as geo_decoration
from ..parts_ops import toolset as toolset_ops

_CN_VIEW = {"FRONT": "前", "BACK": "后", "LEFT": "左", "RIGHT": "右"}


class AFR_PT_Main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_label = "AI 手办模型工具"

    def draw(self, context):
        sc = context.scene
        layout = self.layout

        box = layout.box()
        box.label(text="⚡ 工具集模式：按需执行，不再按固定流程", icon="TOOL_SETTINGS")
        box.label(text="（下方 8 个子面板默认全部展开，按需折叠即可）", icon="INFO")
        box.separator()
        box.label(text="1) 上传 正面参考图（必传，给智能体辅助标注用）",
                  icon="IMAGE")
        box.label(text="2) 点 “使用当前选中” 设源对象（不设的话大部分工具不工作）",
                  icon="HAND")
        box.label(text="3) 展开工具执行；连接键/挖孔前 先把 3D 游标点到接缝位置",
                  icon="CURSOR")
        box.label(text="4) 最后在「打包导出」点 打包 STL→zip 产出可切片文件",
                  icon="PACKAGE")

        # --- Source object ------------------------------------------------
        box = layout.box()
        box.label(text="源对象", icon="IMPORT")
        box.operator("afr.import_model", icon="FILEBROWSER")
        box.operator("afr.use_selected", icon="HAND")
        box.prop(sc, "afr_source", text="源对象")

        # --- 4-quadrant reference images (for the multimodal agent) --------
        box = layout.box()
        box.label(text="参考图（供多模态 AI 智能体辅助部件标记）", icon="IMAGE")
        box.label(text="正面（前）必须上传；四视图参考图可帮助智能体标注部件",
                  icon="INFO")
        ref_views.ensure_ref_state(sc)
        for vname in ("FRONT", "BACK", "LEFT", "RIGHT"):
            slot = ref_views.get_view_slot(sc, vname)
            loaded = bool(slot is not None and slot.image_path)
            row = box.row(align=True)
            if vname == "FRONT":
                icon = "CHECKMARK" if loaded else "ERROR"
                tag = "正面（必须）"
            else:
                icon = "CHECKMARK" if loaded else "INFO"
                tag = "未上传"
            row.label(text=_CN_VIEW[vname], icon=icon)
            if loaded:
                row.label(text=os.path.basename(slot.image_path)[:18])
            else:
                row.label(text=tag)
            op = row.operator("afr.ref_load_image", text="上传", icon="FILE_IMAGE")
            op.view_name = vname
            op = row.operator("afr.ref_clear_image", text="", icon="X")
            op.view_name = vname
            op = row.operator("afr.ref_focus_view", text="看", icon="HAND")
            op.view_name = vname
        row = box.row(align=True)
        row.operator("afr.ref_create_cameras", text="创建参考相机", icon="CAMERA_DATA")
        row.operator("afr.ref_align_to_bbox", text="对齐包围盒", icon="FULLSCREEN_ENTER")
        box.label(text="Ctrl+Alt+Q 开启 Quad View（四视图）", icon="INFO")

        # --- 3D cursor readout (V0.14: makes cursor placement obvious) ------
        box = layout.box()
        box.label(text="3D 游标位置（连接键/挖孔都基于此）", icon="CURSOR")
        cursor = context.scene.cursor.location
        box.label(text="X %.3f   Y %.3f   Z %.3f" % (cursor.x, cursor.y, cursor.z),
                  icon="EMPTY_AXIS")


class AFR_PT_Tool_Split(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "拆分部件"
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        sc = context.scene
        layout = self.layout
        layout.label(text="先标注，后拆分；每个部件独立成对象", icon="GROUP_VCOL")
        layout.operator("afr.semantic_apply_heuristics", icon="AUTO")
        layout.operator("afr.split_by_part", icon="MESH_DATA")
        layout.operator("afr.fill_close_parts", icon="MOD_SOLIDIFY")
        row = layout.row(align=True)
        op = row.operator("afr.semantic_brush_flood", text="全设为 BODY", icon="BRUSH_DATA")
        op.label_name = "BODY"
        op = row.operator("afr.semantic_brush_flood", text="全清空", icon="X")
        op.label_name = "UNLABELED"
        layout.operator("afr.semantic_brush_undo", icon="LOOP_BACK")
        # --- part naming (after.zip contract) ------------------------------
        layout.separator()
        box = layout.box()
        box.label(text="部件命名（打包用 {前缀}-{部件名}.stl）", icon="OUTLINER")
        box.prop(sc, "afr_part_name_input", text="部件名")
        row = box.row(align=True)
        op = row.operator("afr.name_part", text="命名选中", icon="RENAME")
        op.name = sc.afr_part_name_input
        op = row.operator("afr.name_part", text="命名+L", icon="RENAME")
        op.name = sc.afr_part_name_input
        op.lr = "L"
        op = row.operator("afr.name_part", text="命名+R", icon="RENAME")
        op.name = sc.afr_part_name_input
        op.lr = "R"
        row2 = box.row(align=True)
        op = row2.operator("afr.auto_name_lr", text="对称自动 L/R", icon="MOD_MIRROR")
        op.base_name = sc.afr_part_name_input or "手"
        named = [o for o in bpy.data.objects
                 if o.type == "MESH" and o.get("afr_part_name")]
        box.label(text="已命名部件 %d 个" % len(named), icon="CHECKMARK")
        row3 = box.row(align=True)
        row3.operator("afr.export_name_manifest", text="导出清单",
                      icon="FILE_TEXT")
        row3.operator("afr.import_name_manifest", text="导入清单",
                      icon="FILE_FOLDER")


class AFR_PT_Tool_Hair(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "头发修正"
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        sc = context.scene
        src = sc.afr_source
        has_src = bool(src) and src in bpy.data.objects
        ps = context.scene.afr_print
        layout = self.layout
        layout.label(text="提取 / 加厚 / 程序化生成", icon="HAIR")
        if not has_src:
            layout.label(text="⚠ 请先在主面板点 “使用当前选中”", icon="ERROR")
        if has_src and "HAIR" not in bpy.data.objects[src].data.attributes:
            layout.label(text="⚠ 请先到“拆分部件”面板点 Auto-Label", icon="ERROR")
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
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        sc = context.scene
        src = sc.afr_source
        has_src = bool(src) and src in bpy.data.objects
        ps = context.scene.afr_print
        layout = self.layout
        layout.label(text="布料加厚（Solidify）", icon="MOD_CLOTH")
        if not has_src:
            layout.label(text="⚠ 请先在主面板点 “使用当前选中”", icon="ERROR")
        op = layout.operator("afr.fabric_solidify", icon="MOD_SOLIDIFY")
        op.thickness = ps.min_wall_thickness_mm
        layout.separator()
        layout.operator("afr.find_fabric_intersection", icon="VIEWZOOM")
        layout.operator("afr.repair_fabric_intersection", icon="MOD_BOOLEAN")


class AFR_PT_Tool_Figure(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "人物修正"
    bl_options = set()   # V0.14: unfold all sub-panels by default

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
        layout.operator("afr.find_extra_limbs", icon="X")
        layout.operator("afr.remove_extra_limbs", icon="CANCEL")
        layout.operator("afr.auto_orient", icon="ORPHAN_DATA")
        layout.operator("afr.merge_selected", icon="GROUP")
        layout.operator("afr.rollback", icon="LOOP_BACK")
        layout.separator()
        layout.label(text="装饰物库（吸附到身体部位）", icon="MESH_TORUS")
        deco_names = geo_decoration.list_decorations()
        for d in deco_names:
            op = layout.operator("afr.add_decoration", icon="PLUS",
                                 text="放置 %s（%s）" % (d["name"], d["attach"]))
            op.deco_name = d["name"]


class AFR_PT_Tool_Print(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "打印计算"
    bl_options = set()   # V0.14: unfold all sub-panels by default

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
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        layout = self.layout
        layout.label(text="⚠ 连接键生成在 3D 游标位置", icon="CURSOR")
        layout.label(text="游标移动：Left Mouse 空白区 / Shift+S → Cursor to World Origin",
                     icon="INFO")
        layout.separator()
        layout.label(text="生成 (V0.11 零布尔：凸柱 + 套筒，可直接打印)")
        layout.operator("afr.create_connector", text="圆柱 (Round · 游标)",
                        icon="PLUS").kind = "round"
        row = layout.row(align=True)
        row.operator("afr.create_connector", text="球窝 (Ball)",
                     icon="SPHERE").kind = "ball"
        row.operator("afr.create_connector", text="燕尾 (Dovetail)",
                     icon="MOD_WEDGE").kind = "dovetail"
        layout.separator()
        layout.label(text="挖孔 (legacy：把套筒切到选中 mesh)", icon="INFO")
        layout.operator("afr.carve_socket", icon="MOD_BOOLEAN")


class AFR_PT_Tool_Agent(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "AI 智能体 (MCP 接口)"
    bl_options = set()   # V0.14: unfold all sub-panels by default

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


class AFR_PT_Tool_Package(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "打包导出 (STL/3MF)"
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        sc = context.scene
        layout = self.layout
        # --- production LAST step: per-part STL + zip ----------------------
        box = layout.box()
        box.label(text="打包 (每部件 STL → zip，生产最后一步)", icon="PACKAGE")
        box.prop(sc, "afr_package_prefix", text="文件名前缀")
        box.operator("afr.export_part_stl_zip", icon="EXPORT",
                     text="打包 STL → zip")
        layout.separator()
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


class AFR_PT_Tool_AITexture(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "AI 贴图 (ComfyUI)"
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        layout = self.layout
        layout.label(text="选中网格 → 调用本地 ComfyUI 生成贴图", icon="TEXTURE")
        row = layout.row(align=True)
        op = row.operator("afr.comfyui_texture", icon="PLAY", text="生成贴图")
        layout.label(
            text="Host/Port 在 编辑→偏好设置→插件→AI Figure Refiner",
            icon="INFO")


class AFR_PT_Toolset(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Figure Refiner"
    bl_parent_id = "AFR_PT_Main"
    bl_label = "工具集（杂项）"
    bl_options = set()   # V0.14: unfold all sub-panels by default

    def draw(self, context):
        sc = context.scene
        layout = self.layout
        layout.label(text="零散工具：测量/清理/法线/对称/水密/统计",
                     icon="TOOL_SETTINGS")
        src = bpy.data.objects.get(sc.afr_source) if sc.afr_source else None
        if src is not None and src.type == "MESH":
            try:
                s = toolset_ops.stats(src)
                m = toolset_ops.measure(src)
                wt = toolset_ops.watertight_check(src)
                layout.label(text="源 %s: 顶点 %d / 面 %d"
                             % (src.name, s["verts"], s["faces"]))
                layout.label(text="尺寸 %.1f×%.1f×%.1f mm"
                             % (m["dim"][0], m["dim"][1], m["dim"][2]))
                layout.label(text="水密: %s (边界 %d)"
                             % ("✓" if wt["watertight"] else "✗",
                                wt["boundary_edges"]))
            except Exception as e:
                layout.label(text="统计失败: %s" % e, icon="ERROR")
        layout.separator()
        layout.operator("afr.toolset_measure", icon="VIEWZOOM")
        layout.operator("afr.toolset_stats", icon="VIEWZOOM")
        layout.operator("afr.toolset_watertight", icon="MOD_SOLIDIFY")
        row = layout.row(align=True)
        row.operator("afr.toolset_cleanup", icon="BRUSH_DATA")
        row.operator("afr.toolset_normals", icon="NORMALS")
        row = layout.row(align=True)
        row.operator("afr.toolset_symmetry", icon="MOD_MIRROR")
        row.operator("afr.toolset_symmetry", text="镜像修正",
                     icon="MOD_MIRROR").fix = True
        layout.separator()
        box = layout.box()
        box.label(text="重命名选中部件", icon="OUTLINER")
        box.operator("afr.toolset_rename", icon="RENAME")


PANELS = (
    AFR_PT_Main,
    AFR_PT_Tool_Split,
    AFR_PT_Tool_Hair,
    AFR_PT_Tool_Fabric,
    AFR_PT_Tool_Figure,
    AFR_PT_Tool_Print,
    AFR_PT_Tool_Connector,
    AFR_PT_Tool_Agent,
    AFR_PT_Tool_AITexture,
    AFR_PT_Tool_Package,
    AFR_PT_Toolset,
)
