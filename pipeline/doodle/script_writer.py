"""[1] SCRIPT WRITER — turn a topic into a doodle-style narration script.

Live path: POST to the Anthropic Messages API (ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY),
no SDK required. Offline path: a deterministic doodle-voice template so the whole
1->7 loop runs without network/keys. `estimate_timestamps` turns a script into a
TurboScribe-shaped transcript so the doodle pipeline can run without TurboScribe
(approximate timing; for tight sync use real TurboScribe output).
"""
from __future__ import annotations
import os, json, pathlib, re, shutil, subprocess, urllib.request

_ROOT = pathlib.Path(__file__).parent.parent.parent
_PROMPT = _ROOT / "prompts" / "doodle_script.md"
_FINANCE_PROMPT = _ROOT / "prompts" / "finance_script.md"
_FINANCE_META_PROMPT = _ROOT / "prompts" / "finance_metadata.md"
WPM = 150


def claude_code_available() -> bool:
    """True if the Claude Code CLI is installed (used for subscription, no API credits)."""
    return shutil.which("claude") is not None


def generate_via_claude_code(topic: str, prompt_path: str | None = None) -> dict:
    """Generate a script using the local Claude Code CLI on the user's SUBSCRIPTION
    (no API credits). We strip ANTHROPIC_API_KEY from the child env so Claude Code
    uses the logged-in subscription rather than billing the API.

    Returns {"script": narration, "extras": titles/thumbnail block}.
    """
    if not claude_code_available():
        raise RuntimeError("Claude Code CLI ('claude') not found on PATH. "
                           "Install it and run `claude` once to log in with your subscription.")
    tmpl = pathlib.Path(prompt_path or _FINANCE_PROMPT).read_text(encoding="utf-8")
    prompt = tmpl.replace("{topic}", topic)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True,
                          timeout=600, stdin=subprocess.DEVNULL, env=env)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude CLI failed").strip()[:400])
    return split_script(proc.stdout.strip())


def split_script(text: str) -> dict:
    """Split the model output into the narration and the trailing titles/thumbnail."""
    parts = re.split(r"\n-{3,}\s*\n", text, maxsplit=1)
    return {"script": parts[0].strip(),
            "extras": parts[1].strip() if len(parts) > 1 else ""}


def generate_metadata_via_claude_code(topic: str, script: str = "") -> dict:
    """Generate YouTube title/description/tags via the Claude Code CLI (subscription,
    no API credits). Returns {"title", "description", "tags"}."""
    if not claude_code_available():
        raise RuntimeError("Claude Code CLI ('claude') not found on PATH.")
    tmpl = _FINANCE_META_PROMPT.read_text(encoding="utf-8")
    prompt = tmpl.replace("{topic}", topic).replace("{script}", (script or "")[:4000])
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True,
                          timeout=300, stdin=subprocess.DEVNULL, env=env)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude CLI failed").strip()[:400])
    return parse_metadata(proc.stdout.strip())


def parse_metadata(text: str) -> dict:
    """Pull TITLE / DESCRIPTION / TAGS out of the model output."""
    out = {"title": "", "description": "", "tags": ""}
    mt = re.search(r"TITLE:\s*(.+)", text)
    if mt:
        out["title"] = mt.group(1).strip()
    md = re.search(r"DESCRIPTION:\s*(.*?)(?:\nTAGS:|\Z)", text, re.S)
    if md:
        out["description"] = md.group(1).strip()
    mg = re.search(r"TAGS:\s*(.+)", text, re.S)
    if mg:
        out["tags"] = " ".join(mg.group(1).strip().splitlines()).strip()
    return out


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
