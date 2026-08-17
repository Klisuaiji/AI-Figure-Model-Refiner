bl_info = {
    "name": "AI Figure Model Refiner (AI 手办模型精修器)",
    "author": "Klisuaiji",
    "version": (0, 7, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > AI Figure Refiner",
    "description": "将 AI 生成的 3D 手办修复为 FDM 3D 打印可生产模型（半自动，AI 80% + 用户确认）。",
    "category": "Object",
}

import bpy

from .operators import CLASSES, AFRLogEntry, AFRPrintSettings, AFRRefView
from .ui.panel import AFR_PT_Main
from .reference import views as _ref_views

_CLASSES = tuple(list(CLASSES) + [AFR_PT_Main])


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.afr_source = bpy.props.StringProperty(name="源对象")
    bpy.types.Scene.afr_step = bpy.props.IntProperty(name="当前步骤", default=0)
    bpy.types.Scene.afr_log = bpy.props.CollectionProperty(type=AFRLogEntry)
    bpy.types.Scene.afr_diag_json = bpy.props.StringProperty(name="诊断结果")
    bpy.types.Scene.afr_print_json = bpy.props.StringProperty(name="可打印性结果")
    bpy.types.Scene.afr_print = bpy.props.PointerProperty(type=AFRPrintSettings)
    bpy.types.Scene.afr_ref_views = bpy.props.CollectionProperty(type=AFRRefView)
    _ref_views.ensure_ref_state(bpy.context.scene) if hasattr(bpy.context, "scene") and bpy.context.scene else None
    from .core.logging import logger
    logger.info("AI Figure Refiner v0.3 已注册（Blender 5.2 LTS）")


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    for prop in ("afr_source", "afr_step", "afr_log", "afr_diag_json",
                 "afr_print_json", "afr_print", "afr_ref_views"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)


if __name__ == "__main__":
    register()