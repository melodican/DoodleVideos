"""[9] UPLOAD — YouTube Data API: upload, schedule, thumbnail, metadata."""
from __future__ import annotations
import os, logging
log = logging.getLogger("pipeline.upload")


def publish(job) -> str | None:
    if not os.getenv("YT_CHANNEL_ID"):
        log.info("upload: skipped (no YouTube credentials)")
        return None
    raise NotImplementedError("Wire YouTube Data API (OAuth from .env).")
