from PIL import Image, ImageDraw
import math

SIZE = 512
CX, CY = SIZE // 2, SIZE // 2

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Toast shape - bread slice with two top bumps
def toast_path(cx, cy, w, h):
    """Return a list of (x,y) tuples defining a toast/bread shape centered at (cx,cy)."""
    hw, hh = w / 2, h / 2
    t = hh * 0.55  # top bump height
    bs = hh * 0.30 # bump shoulder width

    points = []
    # Start at bottom-left
    bx, by = cx - hw * 0.7, cy + hh * 0.85
    points.append((bx, by))

    # Left side - slight taper inward going up
    lx = cx - hw * 0.78
    ly = cy + hh * 0.1
    points.append((lx, ly))

    # Left bump
    l_bump_cx = cx - hw * 0.42
    l_bump_cy = cy - hh * 0.45
    points.append((l_bump_cx, l_bump_cy))

    # Center dip
    dip_x = cx
    dip_y = cy - hh * 0.15
    points.append((dip_x, dip_y))

    # Right bump
    r_bump_cx = cx + hw * 0.42
    r_bump_cy = cy - hh * 0.45
    points.append((r_bump_cx, r_bump_cy))

    # Right side
    rx = cx + hw * 0.78
    ry = cy + hh * 0.1
    points.append((rx, ry))

    # Bottom-right
    brx = cx + hw * 0.7
    bry = cy + hh * 0.85
    points.append((brx, bry))

    return points

# Draw main toast outline with holographic green
toast_w = SIZE * 0.45
toast_h = SIZE * 0.65
pts = toast_path(CX, CY, toast_w, toast_h)

# Convert to flat list for PIL polygon
flat = []
for p in pts:
    flat.extend(p)

# Holographic green outline
OUTLINE_WIDTH = 8
HOLO_GREEN = (0, 255, 100, 200)
HOLO_GLOW = (0, 255, 100, 60)
HOLO_FILL = (0, 255, 100, 30)

# Draw glow (wider outline)
draw.polygon(flat, outline=HOLO_GLOW, width=OUTLINE_WIDTH * 3)
# Draw main outline
draw.polygon(flat, outline=HOLO_GREEN, width=OUTLINE_WIDTH)
# Draw semi-transparent fill
draw.polygon(flat, fill=HOLO_FILL)

# Add inner glow lines for holographic effect
for i in range(1, 4):
    glow_color = (0, 255, 120, 20 - i * 5)
    draw.polygon(flat, outline=glow_color, width=OUTLINE_WIDTH + i * 4)

# Draw smiley face
face_cx, face_cy = CX, CY + toast_h * 0.08
eye_offset_x = toast_w * 0.13
eye_y = face_cy - toast_h * 0.12
eye_r = toast_w * 0.04

# Eyes
draw.ellipse([
    face_cx - eye_offset_x - eye_r, eye_y - eye_r,
    face_cx - eye_offset_x + eye_r, eye_y + eye_r
], fill=HOLO_GREEN, outline=(0, 255, 100, 200), width=3)

draw.ellipse([
    face_cx + eye_offset_x - eye_r, eye_y - eye_r,
    face_cx + eye_offset_x + eye_r, eye_y + eye_r
], fill=HOLO_GREEN, outline=(0, 255, 100, 200), width=3)

# Smile
smile_cy = face_cy + toast_h * 0.10
smile_rx = toast_w * 0.18
smile_ry = toast_h * 0.08
draw.arc([
    face_cx - smile_rx, smile_cy - smile_ry,
    face_cx + smile_rx, smile_cy + smile_ry
], start=0, end=180, fill=HOLO_GREEN, width=OUTLINE_WIDTH)

# Holographic shimmer lines (diagonal across toast)
for i in range(-4, 5):
    y = CY + i * 12
    x_start = CX - toast_w * 0.5
    x_end = CX + toast_w * 0.5
    alpha = max(0, 30 - abs(i) * 6)
    if alpha > 5:
        shimmer_color = (180, 255, 180, alpha)
        draw.line([(x_start, y), (x_end, y)], fill=shimmer_color, width=2)

# Extra glow dots for holographic feel
glow_positions = [
    (CX - toast_w * 0.3, CY - toast_h * 0.3),
    (CX + toast_w * 0.25, CY - toast_h * 0.2),
    (CX - toast_w * 0.2, CY + toast_h * 0.35),
    (CX + toast_w * 0.35, CY + toast_h * 0.25),
]
for gx, gy in glow_positions:
    for r in range(4, 0, -1):
        alpha = 30 - r * 5
        if alpha > 0:
            dot_color = (0, 255, 100, alpha)
            draw.ellipse([gx - r * 2, gy - r * 2, gx + r * 2, gy + r * 2], fill=dot_color)

img.save("android/icon.png")
print("Icon saved: android/icon.png")

# Also create presplash (simpler version)
ps = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(ps)

# Similar but simpler - just toast with text
draw.polygon(flat, outline=HOLO_GLOW, width=OUTLINE_WIDTH * 3)
draw.polygon(flat, outline=HOLO_GREEN, width=OUTLINE_WIDTH)
draw.polygon(flat, fill=HOLO_FILL)

# Eyes
draw.ellipse([
    face_cx - eye_offset_x - eye_r, eye_y - eye_r,
    face_cx - eye_offset_x + eye_r, eye_y + eye_r
], fill=HOLO_GREEN, outline=(0, 255, 100, 200), width=3)
draw.ellipse([
    face_cx + eye_offset_x - eye_r, eye_y - eye_r,
    face_cx + eye_offset_x + eye_r, eye_y + eye_r
], fill=HOLO_GREEN, outline=(0, 255, 100, 200), width=3)

# Smile
draw.arc([
    face_cx - smile_rx, smile_cy - smile_ry,
    face_cx + smile_rx, smile_cy + smile_ry
], start=0, end=180, fill=HOLO_GREEN, width=OUTLINE_WIDTH)

# Draw "LAZY BOY" text below
try:
    from PIL import ImageFont
    font_size = 32
    font = ImageFont.truetype("arial.ttf", font_size)
    text = "LAZY BOY"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = CX - tw // 2
    ty = CY + toast_h * 0.55
    draw.text((tx, ty), text, fill=HOLO_GREEN, font=font)
except Exception:
    pass  # text is optional

ps.save("android/presplash.png")
print("Presplash saved: android/presplash.png")
