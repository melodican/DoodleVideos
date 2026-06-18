"""[1] SCRIPT WRITER — turn a topic into a doodle-style narration script.

Live path: POST to the Anthropic Messages API (ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY),
no SDK required. Offline path: a deterministic doodle-voice template so the whole
1->7 loop runs without network/keys. `estimate_timestamps` turns a script into a
TurboScribe-shaped transcript so the doodle pipeline can run without TurboScribe
(approximate timing; for tight sync use real TurboScribe output).
"""
from __future__ import annotations
import os, json, pathlib, re, urllib.request

_PROMPT = pathlib.Path(__file__).parent.parent.parent / "prompts" / "doodle_script.md"
WPM = 150


def _render_prompt(topic: str, minutes: float) -> str:
    target_words = int(minutes * WPM)
    return (_PROMPT.read_text(encoding="utf-8")
            .replace("{target_words}", str(target_words))
            .replace("{minutes}", str(minutes))
            .replace("{topic}", topic))


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def write_script(topic: str, minutes: float = 6, model: str | None = None) -> str:
    """Return narration text for `topic`. Uses the LLM if a key is set, else a
    styled offline fallback."""
    if not available():
        return _offline_script(topic, minutes)
    base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    model = model or os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    body = {
        "model": model,
        "max_tokens": min(8000, int(minutes * WPM * 2)),
        "messages": [{"role": "user", "content": _render_prompt(topic, minutes)}],
    }
    req = urllib.request.Request(
        base + "/v1/messages", data=json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 "anthropic-version": "2023-06-01",
                 "x-api-key": os.environ["ANTHROPIC_API_KEY"]})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data.get("content", [])).strip()


def estimate_timestamps(script: str, wpm: int = WPM) -> str:
    """Chunk narration into sentences and assign cumulative timestamps by word
    count. Returns TurboScribe-shaped lines: '(M:SS) sentence'."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s.strip()]
    lines, t = [], 0.0
    for s in sentences:
        m, sec = divmod(int(t), 60)
        lines.append(f"({m}:{sec:02d}) {s}")
        words = max(1, len(s.split()))
        t += words / wpm * 60.0
    return "\n".join(lines) + "\n"


def _offline_script(topic: str, minutes: float) -> str:
    """Deterministic doodle-voice draft so the pipeline runs without a key."""
    t = topic.rstrip("?.! ")
    beats = [
        f"Here's something strange about {t.lower()}.",
        "Most people never stop to ask why. But once you see it, you can't unsee it.",
        "Picture it as a simple drawing. A stick figure, standing in front of a problem.",
        "At first the answer seems obvious. It almost always is wrong.",
        "Because the real story hides one layer down, where nobody bothers to look.",
        "Follow the arrow. One small cause, quietly leading to a much bigger effect.",
        "And that is the part that changes how you see everything else.",
        f"So next time you think about {t.lower()}, remember the layer underneath.",
        "The obvious answer is just the door. The interesting part is the room behind it.",
    ]
    # pad/trim toward the target word count
    target = int(minutes * WPM)
    out = []
    i = 0
    while len(" ".join(out).split()) < target and i < 200:
        out.append(beats[i % len(beats)]); i += 1
    return " ".join(out)
