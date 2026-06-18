"""[2] VOICEOVER — narrate a script with ElevenLabs (no SDK; stdlib HTTP).

Live path needs ELEVENLABS_API_KEY (+ optional ELEVENLABS_VOICE_ID / TTS_VOICE_ID).
Returns the path to an mp3. Keyless callers should check available() and fall back.
"""
from __future__ import annotations
import os, json, pathlib, urllib.request

_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel" (placeholder default)
_API = "https://api.elevenlabs.io/v1/text-to-speech"


def available() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") or os.getenv("TTS_API_KEY"))


def _voice_id() -> str:
    return os.getenv("ELEVENLABS_VOICE_ID") or os.getenv("TTS_VOICE_ID") or _DEFAULT_VOICE


def synthesize(text: str, out_path: str, voice_id: str | None = None,
               model_id: str = "eleven_multilingual_v2") -> str:
    """Synthesize `text` to an mp3 at `out_path`. Raises if no key is set."""
    key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("TTS_API_KEY")
    if not key:
        raise RuntimeError("no ELEVENLABS_API_KEY / TTS_API_KEY set")
    vid = voice_id or _voice_id()
    body = {"text": text, "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    req = urllib.request.Request(
        f"{_API}/{vid}", data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "accept": "audio/mpeg",
                 "xi-api-key": key})
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=180) as r:
        out.write_bytes(r.read())
    return str(out)
