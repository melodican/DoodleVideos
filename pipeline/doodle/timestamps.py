"""Parse a timestamped transcript (e.g. TurboScribe) into ordered segments.

Accepts common formats per line, e.g.:
    (0:00) Talks about XYZ
    0:07 Also talks about XYZ
    [00:11] More XYZ
    0:20 - Even more XYZ
    1:02:33 long-form hour mark
"""
from __future__ import annotations
import re
from dataclasses import dataclass

_TS = re.compile(
    r"""^\s*
        [\(\[]?\s*                       # optional ( or [
        (?P<ts>\d{1,2}:\d{2}(?::\d{2})?) # m:ss or h:mm:ss
        \s*[\)\]]?\s*[-–:]?\s*           # optional ) ] and separator
        (?P<text>.*\S)\s*$               # the spoken text
    """,
    re.VERBOSE,
)


@dataclass
class Segment:
    index: int
    start: float          # seconds
    label: str            # "0:07"
    text: str
    end: float | None = None   # filled by build_segments (start of next seg)

    @property
    def filename(self) -> str:
        """Image filename for this segment. Index-based so it is always unique
        (real transcription timestamps can round to the same second)."""
        return f"{self.index:03d}.png"


def to_seconds(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 2:
        m, s = parts; return m * 60 + s
    h, m, s = parts; return h * 3600 + m * 60 + s


def parse(transcript: str) -> list[Segment]:
    segs: list[Segment] = []
    for line in transcript.splitlines():
        m = _TS.match(line)
        if not m:
            continue
        segs.append(Segment(index=len(segs), start=to_seconds(m["ts"]),
                            label=m["ts"], text=m["text"].strip()))
    return build_segments(segs)


def build_segments(segs: list[Segment]) -> list[Segment]:
    """Sort by start time and set each segment's end = next segment's start."""
    segs = sorted(segs, key=lambda s: s.start)
    for i, s in enumerate(segs):
        s.index = i
        s.end = segs[i + 1].start if i + 1 < len(segs) else None
    return segs


def group_segments(segs: list[Segment], min_seconds: float) -> list[Segment]:
    """Merge consecutive segments so each spans at least `min_seconds`.

    Fewer, longer scenes = fewer images to generate (less cost + time) while
    keeping real timing. `min_seconds <= 0` returns the segments unchanged.
    """
    if min_seconds <= 0 or not segs:
        return segs
    segs = sorted(segs, key=lambda s: s.start)
    merged: list[Segment] = []
    cur = None
    for s in segs:
        if cur is None:
            cur = Segment(index=0, start=s.start, label=s.label, text=s.text, end=s.end)
        else:
            cur.text = f"{cur.text} {s.text}".strip()
            cur.end = s.end
        span = (cur.end if cur.end is not None else s.start) - cur.start
        if span >= min_seconds:
            merged.append(cur); cur = None
    if cur is not None:
        merged.append(cur)
    return build_segments(merged)

