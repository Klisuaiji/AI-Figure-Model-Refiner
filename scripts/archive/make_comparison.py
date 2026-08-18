"""Generate a side-by-side BEFORE/AFTER comparison image."""
import os
from PIL import Image

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo"

before_paths = [
    os.path.join(OUT_DIR, "FINAL_BEFORE_front.png"),
    os.path.join(OUT_DIR, "FINAL_BEFORE_back.png"),
]
after_paths = [
    os.path.join(OUT_DIR, "FINAL_AFTER_front.png"),
    os.path.join(OUT_DIR, "FINAL_AFTER_back.png"),
]

# Resize all to same height
target_h = 600
imgs_before = []
imgs_after = []
for p in before_paths + after_paths:
    img = Image.open(p).convert("RGBA")
    w, h = img.size
    new_w = int(w * target_h / h)
    img = img.resize((new_w, target_h), Image.LANCZOS)
    if p in before_paths:
        imgs_before.append(img)
    else:
        imgs_after.append(img)

# Compose: top row = BEFORE (front | back), bottom row = AFTER (front | back)
margin = 8
header_h = 40
canvas_w = max(
    sum(i.width for i in imgs_before) + margin * (len(imgs_before) + 1),
    sum(i.width for i in imgs_after) + margin * (len(imgs_after) + 1),
)
canvas_h = (target_h + margin) * 2 + header_h * 2 + margin * 2

canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
from PIL import ImageDraw, ImageFont

draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("arial.ttf", 24)
except OSError:
    font = ImageFont.load_default()

# BEFORE row
y = margin
draw.text((margin, y), "BEFORE (原始 main)", fill=(50, 50, 50, 255), font=font)
y += header_h
x = margin
for img in imgs_before:
    canvas.paste(img, (x, y), img)
    x += img.width + margin

# AFTER row
y += target_h + margin
draw.text((margin, y), "AFTER (doll + decoration1 + decoration2)", fill=(50, 50, 50, 255), font=font)
y += header_h
x = margin
for img in imgs_after:
    canvas.paste(img, (x, y), img)
    x += img.width + margin

out = os.path.join(OUT_DIR, "BEFORE_AFTER_compare.png")
canvas.save(out, "PNG")
print(f"Saved {out}")
print(f"Size: {canvas.size}")
