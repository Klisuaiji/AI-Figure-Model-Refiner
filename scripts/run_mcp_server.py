#!/usr/bin/env python
"""Launch the AFR MCP server (out-of-process).

Adds the addon package to ``sys.path`` and starts the MCP server, which
then drives Blender over the Blender MCP socket (default 127.0.0.1:9876)
or in-process if launched from inside Blender.

Usage:
    python scripts/run_mcp_server.py                 # stdio
    python scripts/run_mcp_server.py --transport streamable-http --port 8000
"""

import os
import sys

# Make ``ai_figure_refiner`` importable (it lives in ../addon).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ADDON_DIR = os.path.join(os.path.dirname(_HERE), "addon")
if _ADDON_DIR not in sys.path:
    sys.path.insert(0, _ADDON_DIR)


def main():
    from ai_figure_refiner.mcp.server import main as server_main
    server_main()


if __name__ == "__main__":
    main()
