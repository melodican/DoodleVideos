"""[3] SCRIPT — assemble an 18-24 min narration following the channel structure.

Deterministic, grounded draft: weaves each cited fact into an escalating beat and
flags the climax as speculation. An LLM pass (prompts/script.md) can later refine
prose, but the structure here guarantees a runnable, fact-anchored script offline.
"""
from __future__ import annotations
import pathlib, yaml

_CH = pathlib.Path(__file__).parent.parent / "config" / "channel.yaml"


def write(title: str, sources: list[dict]) -> str:
    ch = yaml.safe_load(_CH.read_text())["channel"]
    persona = ch.get("voice_persona", "calm narrator")
    out = []
    out.append(f"[VOICE: {persona}]\n")
    # Cold-open hook (<= 30s)
    out.append("## COLD OPEN (0:00-0:30)")
    out.append(f"What you are about to hear is real. {title.rstrip('.')}. "
               "Stay with me — because the deeper we look, the stranger it gets.\n")
    # Escalating beats, one per grounded fact
    out.append("## BEATS")
    for i, f in enumerate(sources, 1):
        out.append(f"### Beat {i}")
        out.append(f"{f['claim']} [{i}]")
        out.append(f"(Source: {f['source_name']})\n")
    # Speculative climax — explicitly flagged
    out.append("## CLIMAX (speculation — flagged)")
    out.append("[SPECULATION] Here is where scientists stop and wonder: if even "
               "part of this holds, what else might be waiting just out of view? "
               "We don't know yet — and that uncertainty is the most thrilling part.\n")
    # Soft CTA
    out.append("## CTA")
    out.append("If moments like this make the universe feel a little less empty, "
               "subscribe — there's a new signal every day.")
    return "\n".join(out)
