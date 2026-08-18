"""Compare V4 (original with spikes) vs V15 (spike-removed)."""
from PIL import Image, ImageDraw, ImageFont
import os

HERE = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.join(HERE, "..", "output", "anime_workflow_v2")
V3_DIR = os.path.join(HERE, "..", "output", "anime_workflow_v3")
OUT = os.path.join(V3_DIR, "COMPARE_V4_vs_V15.png")

# V4 already saved
v4_diag = os.path.join(V2_DIR, "hair_v4_diag.png")
v15_diag = os.path.join(V3_DIR, "hair_v15_diag.png")
v15_side = os.path.join(V3_DIR, "hair_v15_side.png")
v15_back = os.path.join(V3_DIR, "hair_v15_back.png")

imgs = [
    (v4_diag, "V4: decimate 0.04\n(原始 + 5-6 根尖刺)"),
    (v15_diag, "V15: V4 + 剔刺\n(二次元笔触, 无尖刺)"),
    (v15_side, "V15 side\n(流线长发)"),
    (v15_back, "V15 back\n(后方披散)"),
]

# open
loaded = []
for path, label in imgs:
    img = Image.open(path).convert("RGBA")
    loaded.append((img, label))

# Compose 1x4 grid with labels
W, H = 800, 800
margin = 20
label_h = 60
canvas_w = W * 4 + margin * 5
canvas_h = H + label_h + margin * 2
canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
except Exception:
    font = ImageFont.load_default()

for i, (img, label) in enumerate(loaded):
    x = margin + i * (W + margin)
    y = margin
    canvas.paste(img, (x, y))
    # label
    draw.text((x + 10, y + H + 5), label, fill=(0, 0, 0, 255), font=font)

canvas.save(OUT)
print(f"Saved {OUT}")
