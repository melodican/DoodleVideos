"""[5] VIDEO — assemble the documentary via Vid Rush."""
from __future__ import annotations
import os, logging
log = logging.getLogger("pipeline.video")


def render(voice_path, sources) -> str | None:
    if not os.getenv("VIDRUSH_API_KEY"):
        log.info("video: skipped (no VIDRUSH_API_KEY)")
        return None
    raise NotImplementedError("Integrate Vid Rush render job + poll for result.")
