"""Make a comparison of all 8 hair processing attempts."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow_v2"

versions = [
    ("V1: orig raw mesh", "output/anime_workflow/01_HAIR_BEFORE_diag.png"),
    ("V2: decimate 0.08", "hair_v2_diag.png"),
    ("V3: voxel 1.5cm", "hair_v3_diag.png"),
    ("V4: decimate 0.04 + fill", "hair_v4_diag.png"),
    ("V5: bmesh components (crashed)", None),
    ("V6: separate loose (collapsed)", "hair_v6_diag.png"),
    ("V7: shrinkwrap + toon", "hair_v7_diag.png"),
    ("V8: shrinkwrap + toon + elongate", "hair_v8_diag.png"),
]

# Use only the ones with renders
renders = [(label, path) for label, path in versions if path is not None]
print(f"Renders: {len(renders)}")

# Load all
imgs = []
labels = []
for label, rel in renders:
    p = os.path.join(OUT_DIR, rel)
    if os.path.exists(p):
        img = Image.open(p).convert("RGBA")
        imgs.append(img)
        labels.append(label)
        print(f"  {label}: {img.size}")

# Resize to common height
H = 400
def fit(img, h=H):
    w, ih = img.size
    return img.resize((int(w * h / ih), h), Image.LANCZOS)

imgs = [fit(i) for i in imgs]

# 2 rows × 4 cols
cols = 4
rows = 2
margin = 10
header = 50
img_w = imgs[0].width
img_h = H

canvas_w = cols * img_w + (cols + 1) * margin
canvas_h = rows * (img_h + header) + (rows + 1) * margin
canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("arial.ttf", 18)
except OSError:
    font = ImageFont.load_default()

for i, (img, label) in enumerate(zip(imgs, labels)):
    col = i % cols
    row = i // cols
    x = margin + col * (img_w + margin)
    y = margin + row * (img_h + header + margin)
    draw.text((x, y), label, fill=(0, 0, 0, 255), font=font)
    canvas.paste(img, (x, y + header), img)

out = os.path.join(OUT_DIR, "COMPARE_ALL_HAIR_VERSIONS.png")
canvas.save(out, "PNG")
print(f"\nSaved {out}: {canvas.size}")
