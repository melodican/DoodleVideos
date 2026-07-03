"""[BROLL] VISUAL PLAN — decide what footage to show for each scene.

For each scene we need a short stock-footage search query. Director paths, in order:
  1. Anthropic API (ANTHROPIC_API_KEY) — works everywhere, incl. nested sessions.
  2. Claude Code CLI — subscription, no API credits (but cannot run *inside* a
     Claude Code session, which is why the API path exists).
  3. keyword heuristic — deterministic offline fallback.

The chosen path is returned explicitly and reported by the builder; there is no
hidden degradation. `require_director=True` makes an LLM director mandatory (raises
rather than silently using the heuristic) for production-critical runs.
"""
from __future__ import annotations
import json, os, re, subprocess, urllib.request
from pipeline.doodle.timestamps import Segment
from pipeline.doodle import script_writer

_STOP = set("""a an the and or but so for of to in on at by with from as is are was were be been
being this that these those it its it's you your we our they their he she his her i me my
about into over under than then them us if when while because there here what which who how
why have has had do does did will would can could should may might must not no yes get got
like just very really only also even still much many more most some any all one two three
out up down off back where now new your you'll you're we'll it'll there's here's
concept identical situation understand basically something instead return benefit everybody
nobody whole simple part weird chunk stuff bother alone bigger world real thing things
actually literally maybe keeping spend give given giving stops sounds start paradise""".split())

# concrete things make better b-roll than abstractions
_BOOST = re.compile(r"^(money|cash|coin|bank|tax|island|fish|boat|ocean|beach|fire|road|"
                    r"city|house|build|farm|food|market|store|paper|clock|time|hand|work|"
                    r"bridge|rope|path|spring|water|shelter|firewood|latrine|country)", re.I)


def keywords_for(text: str, topic: str = "", n: int = 2) -> str:
    """Heuristic: pick the most footage-able words from a line of narration.
    Falls back to the channel/topic when a line is too abstract to visualise."""
    words = re.findall(r"[A-Za-z']+", text.lower())
    cand = [w for w in words if len(w) > 3 and w not in _STOP]
    if not cand:
        return topic or "abstract background"
    cand.sort(key=lambda w: (0 if _BOOST.match(w) else 1, -len(w)))
    seen, picked = set(), []
    for w in cand:
        if w not in seen:
            seen.add(w); picked.append(w)
        if len(picked) >= n:
            break
    # if nothing concrete surfaced, lean on the topic so we don't get generic B-roll
    if topic and not any(_BOOST.match(w) for w in picked):
        return f"{topic.split()[-1]} {picked[0]}"
    return " ".join(picked)


def _heuristic(scenes: list[Segment], topic: str = "", n: int = 2) -> list[str]:
    return [keywords_for(s.text, topic, n) for s in scenes]


def _parse_array(text: str, n: int) -> list[str]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise RuntimeError("no JSON array in director output")
    queries = [str(q).strip() for q in json.loads(m.group(0))]
    if len(queries) != n:
        raise RuntimeError(f"got {len(queries)} queries for {n} scenes")
    return [q or "abstract background" for q in queries]


def _director_prompt(scenes: list[Segment], topic: str) -> str:
    numbered = "\n".join(f"{i}. {s.text}" for i, s in enumerate(scenes))
    return (
        "You are choosing B-roll stock footage for a faceless YouTube documentary"
        + (f" about: {topic}.\n\n" if topic else ".\n\n") +
        "For EACH numbered narration line below, give ONE short stock-footage search "
        "query (1-3 words, concrete and literal — a real filmable object/place/action, "
        "NOT an abstract idea, and avoid generic 'people looking at camera' unless the "
        "line is about people). Reply with ONLY a JSON array of strings, in order.\n\n"
        + numbered)


def plan_via_api(scenes: list[Segment], topic: str = "") -> list[str]:
    """Director via the Anthropic Messages API (works inside nested sessions)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no ANTHROPIC_API_KEY")
    base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    model = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    body = {"model": model, "max_tokens": 2000,
            "messages": [{"role": "user", "content": _director_prompt(scenes, topic)}]}
    req = urllib.request.Request(
        base + "/v1/messages", data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "anthropic-version": "2023-06-01",
                 "x-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return _parse_array(text, len(scenes))


def plan_via_claude(scenes: list[Segment], topic: str = "") -> list[str]:
    """Director via the Claude Code CLI (cannot run inside a Claude Code session)."""
    if not script_writer.claude_code_available():
        raise RuntimeError("claude CLI not available")
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(["claude", "-p", _director_prompt(scenes, topic)],
                          capture_output=True, text=True, timeout=300,
                          stdin=subprocess.DEVNULL, env=env)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude CLI failed").strip()[:300])
    return _parse_array(proc.stdout, len(scenes))


def plan_queries(scenes: list[Segment], topic: str = "",
                 require_director: bool = False) -> tuple[list[str], str]:
    """Return (queries, director_source). Tries API → CLI → heuristic, and reports
    which path ran. With require_director=True, raises rather than degrading."""
    reasons = []
    for name, fn in (("anthropic-api", plan_via_api), ("claude-cli", plan_via_claude)):
        try:
            return fn(scenes, topic), name
        except Exception as e:  # noqa: BLE001 - try the next director path
            reasons.append(f"{name}: {str(e)[:80]}")
    if require_director:
        raise RuntimeError("footage director unavailable and require_director=True — "
                           + "; ".join(reasons))
    return _heuristic(scenes, topic), "heuristic (" + "; ".join(reasons) + ")"
