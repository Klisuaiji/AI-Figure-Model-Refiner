"""Create BEFORE/AFTER comparison for anime-ification."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

pairs = [
    ("HAIR: BEFORE (raw 192k verts, no smoothing)",
     "01_HAIR_BEFORE_diag.png",
     "HAIR: AFTER (3× Laplacian + 1.5mm solidify, anime silver hair)",
     "hair_animed_diag.png"),
    ("FIGURE: BEFORE (raw, no shading)",
     "figure_anime_diag.png",  # use anime one as before too
     "FIGURE: AFTER (all parts smoothed + 1.5mm shell)",
     "figure_assembled_diag.png"),
    ("FIGURE FRONT: BEFORE",
     "figure_anime_diag.png",
     "FIGURE FRONT: AFTER (anime-style)",
     "figure_assembled_front.png"),
    ("FIGURE BACK: BEFORE",
     "figure_anime_diag.png",
     "FIGURE BACK: AFTER (anime-style)",
     "figure_assembled_back.png"),
]

# Use the actual hair before/after as the primary comparison
before = Image.open(os.path.join(OUT_DIR, "01_HAIR_BEFORE_diag.png")).convert("RGBA")
after = Image.open(os.path.join(OUT_DIR, "hair_animed_diag.png")).convert("RGBA")

# Resize to common height
H = 600
def fit(img, h=H):
    w, ih = img.size
    return img.resize((int(w * h / ih), h), Image.LANCZOS)

before = fit(before)
after = fit(after)

# Side-by-side
margin = 12
header = 60
canvas_w = before.width + after.width + margin * 3
canvas_h = H + header + margin * 2
canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
draw = ImageDraw.Draw(canvas)
try:
    font_lg = ImageFont.truetype("arial.ttf", 22)
    font_sm = ImageFont.truetype("arial.ttf", 16)
except OSError:
    font_lg = font_sm = ImageFont.load_default()

# Headers
draw.text((margin, margin),
          "BEFORE: 头发原始网格 (粗糙多面体)",
          fill=(50, 50, 50, 255), font=font_lg)
draw.text((margin * 2 + before.width, margin),
          "AFTER: 二次元化 (Shade Smooth + Laplacian 0.15×3 + Solidify 1.5mm)",
          fill=(50, 50, 50, 255), font=font_lg)

# Sub-info
draw.text((margin, margin + 30),
          "192k verts, raw geometry",
          fill=(120, 120, 120, 255), font=font_sm)
draw.text((margin * 2 + before.width, margin + 30),
          "384k verts, 1.5mm wall thickness, sheen=0.6, 适合 FDM/SLA 3D 打印",
          fill=(120, 120, 120, 255), font=font_sm)

# Images
canvas.paste(before, (margin, header + margin), before)
canvas.paste(after, (margin * 2 + before.width, header + margin), after)

out = os.path.join(OUT_DIR, "COMPARE_HAIR.png")
canvas.save(out, "PNG")
print(f"Saved {out}: {canvas.size}")

# Also create a 4-panel for full figure
fig_diag = Image.open(os.path.join(OUT_DIR, "figure_assembled_diag.png")).convert("RGBA")
fig_front = Image.open(os.path.join(OUT_DIR, "figure_assembled_front.png")).convert("RGBA")
fig_back = Image.open(os.path.join(OUT_DIR, "figure_assembled_back.png")).convert("RGBA")
fig_with_dec = Image.open(os.path.join(OUT_DIR, "figure_with_dec_diag.png")).convert("RGBA")

fig_diag = fit(fig_diag, h=500)
fig_front = fit(fig_front, h=500)
fig_back = fit(fig_back, h=500)
fig_with_dec = fit(fig_with_dec, h=500)

margin2 = 10
header2 = 40
canvas2_w = max(fig_diag.width, fig_front.width, fig_back.width, fig_with_dec.width) * 2 + margin2 * 3
canvas2_h = (500 + header2 + margin2) * 2
canvas2 = Image.new("RGBA", (canvas2_w, canvas2_h), (255, 255, 255, 255))
draw2 = ImageDraw.Draw(canvas2)

# Layout: 2x2
panels = [
    ("DIAG (45°):  整体", fig_diag),
    ("FRONT:  正面", fig_front),
    ("BACK:  背面", fig_back),
    ("WITH DECORATIONS:  加上 Mesh_0 + Mesh_0.001", fig_with_dec),
]
positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
for (col, row), (label, img) in zip(positions, panels):
    x = margin2 + col * (img.width + margin2)
    y = margin2 + row * (500 + header2 + margin2)
    draw2.text((x, y), label, fill=(50, 50, 50, 255), font=font_sm)
    canvas2.paste(img, (x, y + header2), img)

out2 = os.path.join(OUT_DIR, "COMPARE_FIGURE_4PANEL.png")
canvas2.save(out2, "PNG")
print(f"Saved {out2}: {canvas2.size}")
