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
"""AFR MCP server — the AI-agent facing surface.

This module wires the :mod:`ai_figure_refiner.mcp.tools` domain functions
into an MCP server (FastMCP-style ``MCPServer`` from the ``mcp`` SDK). An
AI agent connects to this server (default: stdio transport) and drives
Blender through the tools below. The actual Blender execution is delegated
to a :class:`backend.BlenderBackend` — in-process when the server is launched
from inside Blender, or over the Blender MCP socket otherwise.

Run it:

    python -m ai_figure_refiner.mcp            # stdio (default)
    python -m ai_figure_refiner.mcp --transport streamable-http --port 8000
"""

from __future__ import annotations

import argparse
import asyncio

from mcp.server.mcpserver.server import MCPServer

from .backend import get_default_backend
from . import tools


mcp = MCPServer(
    name="ai-figure-refiner",
    version="0.10.0",
    description=(
        "AI Figure Model Refiner — drives Blender to diagnose, repair, "
        "printability-check, semantically label, refine (hair/fabric/base), "
        "merge and export 3D figure models. Connects to Blender via the "
        "Blender MCP socket by default."),
)


@mcp.tool(name="list_objects", description="List all MESH objects in the Blender scene with vertex/face counts.")
async def t_list_objects() -> dict:
    return tools.list_objects(get_default_backend())


@mcp.tool(name="diagnose", description="Run mesh diagnostics (vertices, edges, faces, non-manifold/ boundary edges, connected components, volume, watertight).")
async def t_diagnose(object_name: str | None = None) -> dict:
    return tools.diagnose(get_default_backend(), object_name=object_name)


@mcp.tool(name="repair", description="Basic repair: remove duplicate verts, fill holes, recalculate normals.")
async def t_repair(object_name: str | None = None) -> dict:
    return tools.repair(get_default_backend(), object_name=object_name)


@mcp.tool(name="printability", description="FDM printability analysis: wall thickness, overhangs, floating components.")
async def t_printability(object_name: str | None = None,
                         min_wall_mm: float = 0.8, nozzle_mm: float = 0.4,
                         layer_height_mm: float = 0.2,
                         overhang_angle_deg: float = 45.0) -> dict:
    return tools.printability(
        get_default_backend(), object_name=object_name,
        min_wall_mm=min_wall_mm, nozzle_mm=nozzle_mm,
        layer_height_mm=layer_height_mm,
        overhang_angle_deg=overhang_angle_deg)


@mcp.tool(name="get_reference_images", description="Return the 4 reference-image slots (FRONT/BACK/LEFT/RIGHT) with file paths, loaded status and whether the mandatory FRONT photo is present. The multimodal agent reads these images to assist part labelling.")
async def t_get_reference_images() -> dict:
    return tools.get_reference_images(get_default_backend())


@mcp.tool(name="set_part_labels", description="Write a per-vertex part-label array (list of ints: 0=UNLABELED 1=HAIR 2=HEAD 3=BODY 4=FABRIC 5=BASE) to the object. Use after multimodal vision analysis of the reference images.")
async def t_set_part_labels(object_name: str | None, labels: list) -> dict:
    return tools.set_part_labels(get_default_backend(), object_name=object_name,
                                 labels=labels)


@mcp.tool(name="label_parts", description="Auto-label mesh parts (HAIR/HEAD/BODY/FABRIC/BASE). method='heuristics' (geometric) or 'flood_body'. method='vision'/'multimodal' additionally requires the FRONT reference photo (mandatory for multimodal-assisted labeling).")
async def t_label_parts(object_name: str | None = None,
                        method: str = "heuristics") -> dict:
    return tools.label_parts(get_default_backend(), object_name=object_name,
                             method=method)


@mcp.tool(name="process_hair", description="Extract the HAIR part and thicken it (Solidify) for anime/figure styling.")
async def t_process_hair(object_name: str | None = None,
                         thickness_mm: float = 0.4) -> dict:
    return tools.process_hair(get_default_backend(), object_name=object_name,
                              thickness_mm=thickness_mm)


@mcp.tool(name="process_fabric", description="Thicken a fabric/cloth part (Solidify) to a printable wall thickness.")
async def t_process_fabric(object_name: str | None = None,
                           thickness_mm: float = 0.6) -> dict:
    return tools.process_fabric(get_default_backend(), object_name=object_name,
                                thickness_mm=thickness_mm)


@mcp.tool(name="process_base", description="Generate a cylindrical base/stand under the figure.")
async def t_process_base(object_name: str | None = None,
                         height_mm: float = 3.0, radius_mm: float = 0.0) -> dict:
    return tools.process_base(get_default_backend(), object_name=object_name,
                              height_mm=height_mm, radius_mm=radius_mm)


@mcp.tool(name="merge_parts", description="Boolean-union a list of named mesh objects into one.")
async def t_merge_parts(names: list[str]) -> dict:
    return tools.merge_parts(get_default_backend(), names)


@mcp.tool(name="auto_orient", description="Automatically orient the object so it rests on the ground (lands flat).")
async def t_auto_orient(object_name: str | None = None) -> dict:
    return tools.auto_orient(get_default_backend(), object_name=object_name)


@mcp.tool(name="export_3mf", description="Export the selected/active mesh object to a 3MF file (self-contained implementation).")
async def t_export_3mf(filepath: str, object_name: str | None = None) -> dict:
    return tools.export_3mf(get_default_backend(), filepath,
                            object_name=object_name)


@mcp.tool(name="run_blender_code", description="Run arbitrary Blender Python. The code must assign a dict to AFR_RESULT. Use for advanced/composed workflows the dedicated tools do not cover.")
async def t_run_blender_code(code: str) -> dict:
    return tools.run_blender_code(get_default_backend(), code)


@mcp.tool(name="create_connector", description="Generate an assembly connector set for a 3D-printed figure: 'round' (peg+hole), 'ball' (ball+socket), or 'dovetail' (tab+slot). Returns the male and female_cutter object names. Female side is a cutter mesh to carve into the receiving part.")
async def t_create_connector(kind: str = "round",
                            position=(0.0, 0.0, 0.0),
                            direction=(0.0, 0.0, 1.0),
                            diameter: float = 5.0, depth: float = 4.0,
                            length: float = 4.0, clearance: float = 0.2,
                            nozzle_mm: float = 0.4,
                            with_flange: bool = False,
                            chamfer: bool = True,
                            opening_ratio: float = 0.7,
                            name: str = "AFR_Connector") -> dict:
    return tools.create_connector(
        get_default_backend(), kind=kind, position=position,
        direction=direction, diameter=diameter, depth=depth, length=length,
        clearance=clearance, nozzle_mm=nozzle_mm, with_flange=with_flange,
        chamfer=chamfer, opening_ratio=opening_ratio, name=name)


@mcp.tool(name="carve_socket", description="Carve the female cutter mesh into the target mesh object via Boolean DIFFERENCE (apply=True bakes geometry). Used after create_connector to cut the hole/socket/slot.")
async def t_carve_socket(target_name: str, cutter_name: str,
                        apply: bool = True) -> dict:
    return tools.carve_socket(get_default_backend(), target_name,
                             cutter_name, apply=apply)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-figure-refiner-mcp",
                                     description="AFR MCP server")
    parser.add_argument("--transport",
                        choices=["stdio", "sse", "streamable-http"],
                        default="stdio", help="MCP transport (default stdio)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host for sse/streamable-http")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port for sse/streamable-http")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # streamable-http / sse need the host/port kwargs
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
