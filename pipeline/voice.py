"""[4] VOICE — TTS with the consistent brand narrator voice (ElevenLabs)."""
from __future__ import annotations
import logging
from .doodle import voiceover
log = logging.getLogger("pipeline.voice")


def synthesize(script_text: str, out_path: str = "output/vo.mp3") -> str | None:
    if not voiceover.available():
        log.info("voice: skipped (no ELEVENLABS_API_KEY / TTS_API_KEY)")
        return None
    return voiceover.synthesize(script_text, out_path)
