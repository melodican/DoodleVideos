"""[4] VOICE — TTS with the consistent brand narrator voice."""
from __future__ import annotations
import os, logging
log = logging.getLogger("pipeline.voice")


def synthesize(script_text: str) -> str | None:
    if not os.getenv("TTS_API_KEY"):
        log.info("voice: skipped (no TTS_API_KEY)")
        return None
    raise NotImplementedError("Wire TTS provider (voice id from .env).")
