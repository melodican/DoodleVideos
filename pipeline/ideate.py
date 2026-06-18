"""[1] IDEATE — choose a topic and generate a curiosity-gap title.

Offline-first: works from config/seed_topics.yaml + config/title_formulas.yaml.
Live NASA feeds and an LLM title-scorer are optional enhancements (see TODOs);
when unavailable the deterministic scorer below is used so the pipeline always runs.
"""
from __future__ import annotations
import json, pathlib, random, re
import yaml

_ROOT = pathlib.Path(__file__).parent.parent
_FORMULAS = _ROOT / "config" / "title_formulas.yaml"
_TOPICS = _ROOT / "config" / "seed_topics.yaml"
_STATE = _ROOT / "state" / "published.json"


def _load(path: pathlib.Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _published_titles() -> list[str]:
    if _STATE.exists():
        return json.loads(_STATE.read_text()).get("titles", [])
    return []


def _fill(formula: str, topic: dict, banks: dict, rng: random.Random) -> str:
    """Fill {slots} from the topic first, then from slot_banks."""
    def repl(m):
        key = m.group(1)
        if key in topic and isinstance(topic[key], str):
            return topic[key]
        if key in banks:
            return rng.choice(banks[key])
        # sensible defaults for slots not in topic/banks
        return {"action": "Just Saw", "target": topic.get("object", "deep space"),
                "phenomenon": "Signal", "location": "in Deep Space", "n": "10",
                "category": "Places"}.get(key, key)
    return re.sub(r"\{(\w+)\}", repl, formula)


def _curiosity_score(title: str, published: list[str]) -> float:
    """Heuristic: reward dread/novelty words + brevity, penalize near-duplicates."""
    t = title.lower()
    score = 0.0
    for w in ("horrifying", "terrifying", "impossible", "shouldn't", "afraid",
              "first time", "what they found", "unsettling"):
        if w in t:
            score += 1.0
    if len(title) <= 70:
        score += 0.5
    # novelty: penalize overlap with already-published titles
    for p in published:
        common = set(t.split()) & set(p.lower().split())
        if len(common) >= 4:
            score -= 2.0
    return score


def pick_topic(seed: int | None = None) -> tuple[dict, str]:
    """Return (topic_dict, title). Deterministic when `seed` is given (handy for tests)."""
    rng = random.Random(seed)
    cfg = _load(_FORMULAS)
    formulas, banks = cfg["formulas"], cfg.get("slot_banks", {})
    topics = _load(_TOPICS)["topics"]
    published = _published_titles()

    # avoid re-using a topic id we've already covered recently
    used_ids = {t.get("topic_id") for t in _read_state().get("history", [])}
    candidates = [t for t in topics if t["id"] not in used_ids] or topics

    best = None
    for topic in candidates:
        for formula in formulas:
            title = _fill(formula, topic, banks, rng)
            s = _curiosity_score(title, published)
            if best is None or s > best[0]:
                best = (s, topic, title)
    _, topic, title = best
    return topic, title


def _read_state() -> dict:
    if _STATE.exists():
        return json.loads(_STATE.read_text())
    return {"titles": [], "history": []}


def record_published(topic: dict, title: str) -> None:
    """Append to dedup state after a successful publish."""
    st = _read_state()
    st.setdefault("titles", []).append(title)
    st.setdefault("history", []).append({"topic_id": topic["id"], "title": title})
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(st, indent=2))
