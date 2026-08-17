# -*- coding: utf-8 -*-
"""Deploy the AI Figure Refiner addon into Blender's user addon directory.

Usage:
    blender --background --python scripts/deploy_addon.py

Or directly in a normal Python:
    python scripts/deploy_addon.py
"""
import os
import shutil
import sys

WS = r"D:/Qq203/Downloads/AI Figure Model Refiner"
SRC = os.path.join(WS, "addon", "ai_figure_refiner")
DEPLOY = r"D:/blender/5.2/scripts/addons/ai_figure_refiner"


def deploy():
    if not os.path.isdir(SRC):
        raise SystemExit("source not found: %s" % SRC)
    if os.path.exists(DEPLOY):
        shutil.rmtree(DEPLOY)
    shutil.copytree(SRC, DEPLOY)
    # strip __pycache__
    for root, dirs, files in os.walk(DEPLOY):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                dirs.remove(d)
    print("Deployed -> %s" % DEPLOY)


if __name__ == "__main__":
    deploy()