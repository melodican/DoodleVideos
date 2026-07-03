"""[BROLL] VISUAL PLAN — decide what footage to show for each scene.

For each scene we need a short stock-footage search query. Claude (via the Code CLI,
on the subscription — no API credits) gives genuinely good, concrete queries; with
no CLI we fall back to a keyword heuristic so the pipeline still runs offline.
"""
from __future__ import annotations
import json, os, re, subprocess
from pipeline.doodle.timestamps import Segment
from pipeline.doodle import script_writer

_STOP = set("""a an the and or but so for of to in on at by with from as is are was were be been
being this that these those it its it's you your we our they their he she his her i me my
about into over under than then them us if when while because there here what which who how
why have has had do does did will would can could should may might must not no yes get got
like just very really only also even still much many more most some any all one two three
out up down off back where now new your you'll you're we'll it'll there's here's""".split())

# concrete things make better b-roll than abstractions
_BOOST = re.compile(r"^(money|cash|coin|bank|tax|island|fish|boat|ocean|beach|fire|road|"
                    r"city|house|build|farm|food|market|store|paper|clock|time|hand|work)",
                    re.I)


def keywords_for(text: str, n: int = 2) -> str:
    """Heuristic: pick the most footage-able words from a line of narration."""
    words = re.findall(r"[A-Za-z']+", text.lower())
    cand = [w for w in words if len(w) > 3 and w not in _STOP]
    if not cand:
        return "abstract background"
    # prefer concrete nouns, then longer words; keep original order for readability
    cand.sort(key=lambda w: (0 if _BOOST.match(w) else 1, -len(w)))
    seen, picked = set(), []
    for w in cand:
        if w not in seen:
            seen.add(w); picked.append(w)
        if len(picked) >= n:
            break
    return " ".join(picked)


def _heuristic(scenes: list[Segment], n: int = 2) -> list[str]:
    return [keywords_for(s.text, n) for s in scenes]


def plan_via_claude(scenes: list[Segment], topic: str = "") -> list[str]:
    """One concise stock-footage query per scene via the Claude Code CLI. Raises if
    the CLI is missing or the output can't be parsed (callers fall back)."""
    if not script_writer.claude_code_available():
        raise RuntimeError("claude CLI not available")
    numbered = "\n".join(f"{i}. {s.text}" for i, s in enumerate(scenes))
    prompt = (
        "You are choosing B-roll stock footage for a faceless YouTube explainer"
        + (f" about: {topic}.\n\n" if topic else ".\n\n") +
        "For EACH numbered narration line below, give ONE short stock-footage search "
        "query (1-3 words, concrete and literal, the kind that returns good Pexels "
        "clips). Reply with ONLY a JSON array of strings, one per line, in order.\n\n"
        + numbered)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True,
                          timeout=300, stdin=subprocess.DEVNULL, env=env)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude CLI failed").strip()[:300])
    m = re.search(r"\[.*\]", proc.stdout, re.S)
    if not m:
        raise RuntimeError("no JSON array in claude output")
    queries = [str(q).strip() for q in json.loads(m.group(0))]
    if len(queries) != len(scenes):
        raise RuntimeError(f"got {len(queries)} queries for {len(scenes)} scenes")
    return [q or "abstract background" for q in queries]


def plan_queries(scenes: list[Segment], topic: str = "", use_claude: bool = True) -> list[str]:
    """Footage query per scene: Claude when available, else a keyword heuristic."""
    if use_claude:
        try:
            return plan_via_claude(scenes, topic)
        except Exception:  # noqa: BLE001 - fall back to the offline heuristic
            pass
    return _heuristic(scenes)
