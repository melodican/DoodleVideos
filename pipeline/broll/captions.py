"""[BROLL] CAPTIONS — burned-in subtitles, the faceless-video look.

Splits each timed narration segment into short on-screen chunks (a few words at a
time). Two render paths:
  * to_ass(...)      — a styled ASS file (needs an ffmpeg built with libass).
  * caption_png(...) — a transparent PNG per chunk, composited with the `overlay`
                       filter. No libass/freetype needed, so it works on stripped
                       ffmpeg builds — this is the path the assembler uses.
Timing rides the real per-segment timestamps, so captions stay in sync with the VO.
"""
from __future__ import annotations
import pathlib
from pipeline.doodle.timestamps import Segment

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# bold white, thick black outline, bottom-centre — the standard high-retention style
_ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,84,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,2,120,120,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600); m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def caption_chunks(segments: list[Segment], audio_seconds: float,
                   max_words: int = 6) -> list[tuple[float, float, str]]:
    """Split each segment's text into <=max_words chunks, dividing the segment's
    time evenly across them. Returns [(start, end, text)]."""
    out: list[tuple[float, float, str]] = []
    for i, s in enumerate(segments):
        end = s.end if s.end is not None else audio_seconds
        words = s.text.split()
        if not words or end <= s.start:
            continue
        groups = [words[j:j + max_words] for j in range(0, len(words), max_words)]
        span = (end - s.start) / len(groups)
        for k, g in enumerate(groups):
            cs = s.start + k * span
            ce = s.start + (k + 1) * span
            out.append((cs, ce, " ".join(g)))
    return out


def _font(size: int):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if pathlib.Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


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


# named caption looks, selectable per channel/format (see channel blueprints)
STYLES = {
    "bold": {"fontsize": 84, "margin_bottom": 150},      # punchy, high-retention
    "minimal": {"fontsize": 60, "margin_bottom": 90},    # smaller, less intrusive
    "lower": {"fontsize": 72, "margin_bottom": 70},      # closer to the edge
}


def caption_png(text: str, out_path: str, style: str = "bold",
                width: int = 1920, height: int = 1080) -> str:
    """Render a transparent full-frame PNG with `text` at the bottom-centre, bold
    white with a thick black outline (the high-retention caption look). Composited
    later with ffmpeg's overlay filter — no libass needed. `style` selects a preset."""
    from PIL import Image, ImageDraw
    cfg = STYLES.get(style, STYLES["bold"])
    fontsize, margin_bottom = cfg["fontsize"], cfg["margin_bottom"]
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(fontsize)
    lines = _wrap(draw, text.upper(), font, width - 240)
    line_h = int(fontsize * 1.15)
    stroke = max(5, fontsize // 14)
    y = height - margin_bottom - len(lines) * line_h
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((width - w) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y += line_h
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return str(out)


def _escape(text: str) -> str:
    return text.replace("\\", " ").replace("{", "(").replace("}", ")").strip()


def to_ass(chunks: list[tuple[float, float, str]], out_path: str) -> str:
    """Write the chunks to an ASS subtitle file (uppercased for punch)."""
    lines = [_ASS_HEAD]
    for start, end, text in chunks:
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,"
            f"{_escape(text).upper()}")
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)
