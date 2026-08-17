"""Build a Blender-addon-installable zip (V0.6).

Blender's `Edit > Preferences > Add-ons > Install` accepts a .zip file
whose **root** contains the addon folder (named exactly after the
addon bl_info["name"]'s slug, which here is `ai_figure_refiner`).
This script creates that zip in `output/`.

Also exposes `install_addon()` which copies the addon into
``%APPDATA%\\Blender Foundation\\Blender\\<ver>\\scripts\\addons\\``
so the user can enable it without going through the GUI.
"""
import os
import sys
import zipfile

# scripts/package_addon.py  →  …/scripts  →  …/<project_root>
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "addon", "ai_figure_refiner")
OUT = os.path.join(ROOT, "output")


def build_addon_zip(output_path=None):
    """Zip the `addon/ai_figure_refiner/` directory as
    `ai_figure_refiner.zip` (root of the zip is the addon folder)."""
    if output_path is None:
        os.makedirs(OUT, exist_ok=True)
        output_path = os.path.join(OUT, "ai_figure_refiner.zip")
    if not os.path.isdir(ADDON):
        raise FileNotFoundError("addon dir not found: %s" % ADDON)
    base = os.path.dirname(ADDON)  # `addon/`
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(ADDON):
            # skip __pycache__
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, base)  # ai_figure_refiner/...
                zf.write(full, rel)
    return output_path


def install_addon(blender_version="5.2", user_scripts_root=None):
    """Copy the addon into Blender's user scripts addons dir so the
    GUI can enable it without going through `Install from disk`.

    Returns the destination path."""
    if user_scripts_root is None:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if not appdata:
                raise RuntimeError("APPDATA not set on Windows")
            user_scripts_root = os.path.join(
                appdata, "Blender Foundation", "Blender",
                blender_version, "scripts", "addons")
        else:
            # Linux/macOS
            home = os.path.expanduser("~")
            if sys.platform == "darwin":
                user_scripts_root = os.path.join(
                    home, "Library", "Application Support", "Blender",
                    blender_version, "scripts", "addons")
            else:
                user_scripts_root = os.path.join(
                    home, ".config", "blender", blender_version, "scripts", "addons")
    dest = os.path.join(user_scripts_root, "ai_figure_refiner")
    os.makedirs(user_scripts_root, exist_ok=True)
    # copy tree
    import shutil
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(ADDON, dest)
    return dest


if __name__ == "__main__":
    p = build_addon_zip()
    print("addon zip:", p)