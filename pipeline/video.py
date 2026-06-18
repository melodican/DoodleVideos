"""[5] VIDEO — assemble the documentary via Vid Rush.

Feed narration + grounded shot list (NASA/ESA public-domain footage) + ambient
bed + captions. Enforce only allowed (public-domain/licensed) footage sources.
"""
from __future__ import annotations


def render(voice_path: str, sources: list[dict]) -> str:
    """Return path to rendered mp4. TODO: call Vid Rush API."""
    raise NotImplementedError("Integrate Vid Rush render job + poll for result.")
