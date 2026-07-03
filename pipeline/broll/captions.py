"""[BROLL] CAPTIONS — burned-in subtitles, the faceless-video look.

Splits each timed narration segment into short on-screen chunks (a few words at a
time) and writes a styled ASS file. Timing rides the real per-segment timestamps,
so captions stay in sync with the VO. ffmpeg burns them in at assembly.
"""
from __future__ import annotations
import pathlib
from pipeline.doodle.timestamps import Segment

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
