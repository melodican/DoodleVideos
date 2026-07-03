"""[BROLL] DIRECTOR — editorial layer: turn narration beats into a *shot list*.

Raw keyword search gives generic, repetitive B-roll. This layer adds editorial
intelligence on top of whatever query source ran (LLM director or heuristic):

  * scene-purpose classification — each beat gets an editorial ROLE
    (establishing / process / human / abstract / reveal / transition), which
    decides the visual strategy (e.g. abstract beats use concept visuals, NOT
    generic "stock people").
  * multi-clip beats — enumeration/process beats ("one fishes, one builds…")
    become 2–3 short shots instead of one long repeated clip.
  * repetition awareness — the builder uses each shot's role + query to avoid the
    same clip or the same visual concept back to back.

Output is a list of Shots (start/end/query/role/allow_people); the builder fetches
one clip per shot and the assembler treats each shot as a scene.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pipeline.doodle.timestamps import Segment
from . import visual_plan

ROLES = ("establishing", "process", "human", "abstract", "reveal", "transition")

# non-people concept B-roll for abstract beats (rotated for variety)
ABSTRACT_VISUALS = [
    "aerial city skyline", "world map", "money counting closeup", "printing money",
    "flowing river aerial", "clock ticking closeup", "government building exterior",
    "stock chart screen",
]

_RE_ESTABLISH = re.compile(r"\b(imagine|picture|welcome|meet |this is|find a|somewhere|"
                           r"once upon|long ago|deep in|high above)\b", re.I)
_RE_REVEAL = re.compile(r"(here'?s the (weird|twist|catch|secret|crazy|strange)|"
                        r"that'?s literally|the truth is|turns out|plot twist|"
                        r"and that'?s (a|the)|but here'?s)", re.I)
_RE_ABSTRACT = re.compile(r"\b(concept|identical|basically|essentially|means|idea|"
                          r"principle|in other words|the point|fundamentally|in theory|"
                          r"in return|the same way|it'?s just)\b", re.I)
_RE_TRANSITION = re.compile(r"^\s*(now|so|but|meanwhile|okay|alright|back in|fast forward|"
                            r"here'?s where|anyway|instead)\b", re.I)
_RE_HUMAN = re.compile(r"\b(millions of people|everyone chips|crowd|workers?|family|"
                       r"citizens|society|community|neighbou?rs)\b", re.I)
_RE_ENUM = re.compile(r"\bone (person|of you)\b", re.I)


def classify_role(text: str, index: int, n: int) -> str:
    """Assign an editorial role to a beat from its text + position."""
    t = text.strip()
    if index == 0 or _RE_ESTABLISH.search(t):
        return "establishing"
    if _RE_REVEAL.search(t):
        return "reveal"
    if _RE_ENUM.search(t) or t.count(",") >= 3:
        return "process"
    if _RE_ABSTRACT.search(t):
        return "abstract"
    if _RE_TRANSITION.match(t):
        return "transition"
    if _RE_HUMAN.search(t):
        return "human"
    return "process"


def _split_items(text: str, topic: str = "") -> list[str]:
    """Concrete queries from an enumeration/process beat (max 3, de-duped)."""
    parts = re.split(r",|\band\b|\bor\b", text)
    items: list[str] = []
    for p in parts:
        kw = visual_plan.keywords_for(p, topic, n=1)
        if kw and kw not in items and kw != "abstract background":
            items.append(kw)
    return items[:3]


# shot-type framings per role — rotated so even a repeated subject changes framing
SHOT_TYPES = {
    "establishing": ["aerial", "wide landscape", "drone"],
    "process": ["close up", "", "macro"],
    "human": ["", "hands closeup"],
    "reveal": ["close up", "macro"],
    "transition": ["aerial", "wide"],
    "abstract": [""],
}


@dataclass
class Shot:
    start: float
    end: float
    text: str
    query: str
    role: str
    allow_people: bool
    shot_type: str = ""


def _framed(query: str, role: str, counter: dict) -> tuple[str, str]:
    """Add a rotating shot-type modifier so framing varies across shots."""
    palette = SHOT_TYPES.get(role, [""])
    st = palette[counter.get(role, 0) % len(palette)]
    counter[role] = counter.get(role, 0) + 1
    return (f"{st} {query}".strip() if st else query), st


def build_shots(scenes: list[Segment], base_queries: list[str], audio_seconds: float,
                topic: str = "", roles: list[str] | None = None) -> list[Shot]:
    """Expand scenes into an editorially-directed shot list. `roles`, when given
    (e.g. from a real director plan), overrides heuristic role classification."""
    shots: list[Shot] = []
    ab_idx = 0
    prev_query = None
    counter: dict = {}
    for i, (s, q) in enumerate(zip(scenes, base_queries)):
        end = s.end if s.end is not None else audio_seconds
        dur = end - s.start
        role = roles[i] if roles else classify_role(s.text, i, len(scenes))

        # multi-clip beats: split enumerations into 2–3 short shots (varied framing)
        if role == "process" and dur >= 4:
            items = _split_items(s.text, topic)
            if len(items) >= 2:
                k = min(3, len(items))
                sub = dur / k
                for j in range(k):
                    st = s.start + j * sub
                    fq, stype = _framed(items[j], role, counter)
                    shots.append(Shot(st, st + sub, s.text, fq, role, False, stype))
                prev_query = items[k - 1]
                continue

        if role == "abstract" and roles is None:     # heuristic: use concept visuals
            query, allow = ABSTRACT_VISUALS[ab_idx % len(ABSTRACT_VISUALS)], False
            ab_idx += 1
        elif role == "abstract":                      # plan supplied a concept query
            query, allow = q, False
        elif role == "human":
            query, allow = q, True
        else:
            query, allow = q, False

        query, stype = _framed(query, role, counter)
        if query == prev_query:                      # no identical query back-to-back
            if role == "abstract":
                query = ABSTRACT_VISUALS[ab_idx % len(ABSTRACT_VISUALS)]; ab_idx += 1
            elif topic:
                query = f"{query} {topic.split()[-1]}"
        shots.append(Shot(s.start, end, s.text, query, role, allow, stype))
        prev_query = query
    return shots
