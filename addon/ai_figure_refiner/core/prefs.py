# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# This file is part of the AI Figure Model Refiner (AFR) addon.
"""Addon-level preferences (ComfyUI integration, etc.)."""
import bpy


class AFRAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "ai_figure_refiner"

    comfyui_host: bpy.props.StringProperty(
        name="ComfyUI Host",
        default="127.0.0.1",
        description="本地 ComfyUI 服务地址（用于 AI 贴图）")
    comfyui_port: bpy.props.IntProperty(
        name="ComfyUI Port",
        default=8188,
        min=1, max=65535,
        description="本地 ComfyUI 服务端口")
    comfyui_workflow: bpy.props.StringProperty(
        name="Workflow (JSON)",
        default="",
        description="可选：贴图用 ComfyUI 工作流 JSON；留空则仅做接入握手")

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="ComfyUI 贴图集成", icon="TEXTURE")
        box.prop(self, "comfyui_host")
        box.prop(self, "comfyui_port")
        box.prop(self, "comfyui_workflow")
        box.label(
            text="填写后，在「AI 贴图」面板点「用 ComfyUI 生成贴图」即可调用本地服务",
            icon="INFO")
