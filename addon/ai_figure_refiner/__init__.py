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
bl_info = {
    "name": "AI Figure Model Refiner (AI 手办模型精修器)",
    "author": "Klisuaiji",
    "version": (0, 15, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > AI Figure Refiner",
    "description": "将 AI 生成的 3D 手办修复为 FDM 3D 打印可生产模型；工具集模式按需执行（拆分部件/头发修正/布料修正/人物修正/打印计算/导出调试）；四视图参考图供多模态 AI 智能体辅助部件标注（正面必传）；GPL-3.0。",
    "category": "Object",
}

try:
    import bpy
except ImportError:
    # Allow importing the package (e.g. the ``mcp`` subpackage) outside of
    # Blender without crashing. The heavy registration only happens in Blender.
    bpy = None  # type: ignore

if bpy is not None:
    from .operators import CLASSES, AFRLogEntry, AFRPrintSettings, AFRRefView
    from .ui.panel import PANELS
    from .core.prefs import AFRAddonPreferences
    from .reference import views as _ref_views
    _CLASSES = tuple(list(CLASSES) + list(PANELS) + [AFRAddonPreferences])
else:
    _CLASSES = ()  # type: ignore
    _ref_views = None  # type: ignore


def register():
    if bpy is None:
        return
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.afr_source = bpy.props.StringProperty(name="源对象")
    bpy.types.Scene.afr_step = bpy.props.IntProperty(name="当前步骤", default=0)
    bpy.types.Scene.afr_log = bpy.props.CollectionProperty(type=AFRLogEntry)
    bpy.types.Scene.afr_diag_json = bpy.props.StringProperty(name="诊断结果")
    bpy.types.Scene.afr_print_json = bpy.props.StringProperty(name="可打印性结果")
    bpy.types.Scene.afr_print = bpy.props.PointerProperty(type=AFRPrintSettings)
    bpy.types.Scene.afr_ref_views = bpy.props.CollectionProperty(type=AFRRefView)
    bpy.types.Scene.afr_package_prefix = bpy.props.StringProperty(
        name="打包前缀", default="")
    _ref_views.ensure_ref_state(bpy.context.scene) if hasattr(bpy.context, "scene") and bpy.context.scene else None
    from .core.logging import logger
    logger.info("AI Figure Refiner v0.15（工具集 + 三状态拆分 + 每部件填充闭合水密化 + 四视图参考图→多模态智能体辅助标注，正面必传；GPL-3.0）已注册（Blender 5.2 LTS）")


def unregister():
    if bpy is None:
        return
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    for prop in ("afr_source", "afr_step", "afr_log", "afr_diag_json",
                 "afr_print_json", "afr_print", "afr_ref_views",
                 "afr_package_prefix"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)


if __name__ == "__main__":
    register()