"""Transcribe a voiceover into timestamped segments (real audio timing).

Uses OpenAI Whisper (verbose_json, segment granularity) so images can be placed
at the exact moment each line is spoken — true sync instead of estimation.
Requires OPENAI_API_KEY. No SDK; stdlib-friendly via requests.
"""
from __future__ import annotations
import os, pathlib
from .timestamps import Segment, build_segments


def available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _label(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def transcribe(audio_path: str) -> list[Segment]:
    """Return Segments with real start/end times from the audio."""
    if not available():
        raise RuntimeError("no OPENAI_API_KEY set for transcription")
    import requests
    key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("TRANSCRIBE_MODEL", "whisper-1")
    with open(audio_path, "rb") as f:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (pathlib.Path(audio_path).name, f)},
            data={"model": model, "response_format": "verbose_json",
                  "timestamp_granularities[]": "segment"},
            timeout=600,
        )
    resp.raise_for_status()
    raw = resp.json().get("segments", [])
    segs = [Segment(index=i, start=float(s["start"]), label=_label(s["start"]),
                    text=(s.get("text") or "").strip())
            for i, s in enumerate(raw) if (s.get("text") or "").strip()]
    if not segs:
        raise RuntimeError("transcription returned no segments")
    return build_segments(segs)


def to_transcript_text(segments: list[Segment]) -> str:
    return "\n".join(f"({s.label}) {s.text}" for s in segments) + "\n"
