"""[8] THUMBNAIL — compose a bold 1280x720 YouTube thumbnail from a doodle frame.

Free + offline: takes one already-generated doodle image and lays a big, high-
contrast title over it (Impact-style, white text + thick black outline, like the
viral finance channels). No image-API spend — important while OpenAI credit is low.
"""
from __future__ import annotations
import pathlib
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 720

# Prefer punchy thumbnail fonts; fall back gracefully across machines.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if pathlib.Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001 - try the next candidate
                continue
    return ImageFont.load_default()


def _fill_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale to cover then center-crop to exactly w x h (no bars)."""
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))))
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = word
    if cur:
        lines.append(cur)
    return lines


def make_thumbnail(image_path: str, title: str, out_path: str,
                   accent: str = "#f5c542") -> str:
    """Compose a thumbnail from `image_path` with `title` overlaid. Returns out_path."""
    base = _fill_crop(Image.open(image_path), WIDTH, HEIGHT)
    draw = ImageDraw.Draw(base, "RGBA")

    text = (title or "").strip().upper() or "WHAT ACTUALLY IS"
    margin = 56
    max_w = WIDTH - 2 * margin

    # Auto-fit: shrink until the wrapped title fits in the lower ~55% of the frame.
    size = 150
    while size > 40:
        font = _font(size)
        lines = _wrap(draw, text, font, max_w)
        line_h = int(size * 1.12)
        if len(lines) * line_h <= int(HEIGHT * 0.55):
            break
        size -= 6
    font = _font(size)
    lines = _wrap(draw, text, font, max_w)
    line_h = int(size * 1.12)

    block_h = len(lines) * line_h
    y = HEIGHT - margin - block_h

    # Darken the lower band so text always reads, whatever the doodle behind it.
    band_top = max(0, y - 30)
    grad = Image.new("L", (1, HEIGHT - band_top), 0)
    for i in range(grad.height):
        grad.putpixel((0, i), int(190 * (i / max(1, grad.height - 1))))
    shade = Image.new("RGBA", (WIDTH, HEIGHT - band_top), (0, 0, 0, 255))
    shade.putalpha(grad.resize((WIDTH, HEIGHT - band_top)))
    base.paste(Image.new("RGB", shade.size, (0, 0, 0)), (0, band_top), shade)

    stroke = max(6, size // 12)
    for line in lines:
        lw = draw.textlength(line, font=font)
        x = margin
        # accent underline-ish bar tucked behind the first line for a marker feel
        draw.text((x, y), line, font=font, fill="white",
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += line_h

    # a bold accent rule under the title block (hand-drawn channel vibe)
    ry = HEIGHT - margin + 6
    draw.rectangle([margin, ry, margin + min(max_w, 360), ry + 12], fill=accent)

    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    base.save(out, "PNG")
    return str(out)
