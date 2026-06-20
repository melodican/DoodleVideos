"""[2] VOICEOVER — narrate a script with ElevenLabs (no SDK; stdlib HTTP).

Live path needs ELEVENLABS_API_KEY (+ optional ELEVENLABS_VOICE_ID / TTS_VOICE_ID).
Returns the path to an mp3. Keyless callers should check available() and fall back.

Long scripts are split into sentence-aligned chunks under the per-request character
limit and the resulting mp3s are concatenated (MP3 frames join cleanly), so a full
6-minute narration works in one call from the caller's point of view.
"""
from __future__ import annotations
import os, json, pathlib, re, urllib.request, urllib.error

_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel" (placeholder default)
_API = "https://api.elevenlabs.io/v1/text-to-speech"
# ElevenLabs caps a single TTS request at 5000 characters; stay under it.
_MAX_CHARS = 4800


def available() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") or os.getenv("TTS_API_KEY"))


def _voice_id() -> str:
    return os.getenv("ELEVENLABS_VOICE_ID") or os.getenv("TTS_VOICE_ID") or _DEFAULT_VOICE


def estimate_chars(text: str) -> int:
    """Characters ElevenLabs will bill for (whitespace-collapsed)."""
    return len(re.sub(r"\s+", " ", (text or "").strip()))


def _split_text(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """Break text into chunks <= max_chars, preferring sentence boundaries."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    # split on sentence enders, keeping the punctuation attached
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for sent in sentences:
        # a single monster sentence: hard-wrap it on whitespace
        while len(sent) > max_chars:
            cut = sent.rfind(" ", 0, max_chars) or max_chars
            cut = cut if cut > 0 else max_chars
            chunks.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if not cur:
            cur = sent
        elif len(cur) + 1 + len(sent) <= max_chars:
            cur += " " + sent
        else:
            chunks.append(cur)
            cur = sent
    if cur:
        chunks.append(cur)
    return chunks


def _synthesize_one(text: str, key: str, vid: str, model_id: str) -> bytes:
    body = {"text": text, "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    req = urllib.request.Request(
        f"{_API}/{vid}", data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "accept": "audio/mpeg",
                 "xi-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except urllib.error.HTTPError as e:  # surface ElevenLabs' error message
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"ElevenLabs HTTP {e.code}: {detail}") from e


def synthesize(text: str, out_path: str, voice_id: str | None = None,
               model_id: str = "eleven_multilingual_v2", on_progress=None) -> str:
    """Synthesize `text` to an mp3 at `out_path`. Raises if no key is set.

    Long text is chunked transparently. `on_progress(i, n)` is called per chunk."""
    key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("TTS_API_KEY")
    if not key:
        raise RuntimeError("no ELEVENLABS_API_KEY / TTS_API_KEY set")
    if not (text or "").strip():
        raise RuntimeError("no script text to narrate")
    vid = voice_id or _voice_id()
    chunks = _split_text(text)
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    audio = bytearray()
    for i, chunk in enumerate(chunks, 1):
        if on_progress:
            on_progress(i, len(chunks))
        audio += _synthesize_one(chunk, key, vid, model_id)
    out.write_bytes(bytes(audio))
    return str(out)
