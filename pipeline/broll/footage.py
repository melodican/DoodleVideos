"""[BROLL] FOOTAGE — fetch a stock clip per scene from Pexels (free API).

`PEXELS_API_KEY` (free at pexels.com/api) enables real footage. With no key we
fall back to a generated placeholder card so the whole pipeline still runs.

Selection is not "take the first hit": for each query we fetch several candidates
and re-rank them by how well the clip's Pexels slug matches the query, penalising
generic "stock people" clips on non-people queries and de-duplicating across the
build. This is the piece that replaces Vidrush's expensive web-footage step.
"""
from __future__ import annotations
import os, re, hashlib, pathlib, subprocess, shutil, functools

_SEARCH = "https://api.pexels.com/videos/search"
_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# slug words that signal generic people/portrait B-roll (the "faceless AI" look)
_PEOPLE_GENERIC = {"man", "woman", "men", "women", "people", "person", "guy", "girl",
                   "boy", "portrait", "model", "posing", "smiling", "looking", "face",
                   "young", "adult", "team", "group", "office", "studio"}
# query words that legitimately want people on screen (don't penalise then)
_PEOPLE_INTENT = {"people", "person", "man", "woman", "crowd", "worker", "family",
                  "friends", "team", "citizens", "protest", "meeting"}
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "with", "for", "video"}


@functools.lru_cache(maxsize=1)
def _has_drawtext() -> bool:
    """Not every ffmpeg build ships libfreetype (drawtext). Check once."""
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                             capture_output=True, text=True, check=True).stdout
        return " drawtext " in out
    except Exception:  # noqa: BLE001
        return False


def available() -> bool:
    return bool(os.getenv("PEXELS_API_KEY"))


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP}


def _slug_words(video: dict) -> set[str]:
    """Descriptive words from a Pexels result's page URL slug."""
    url = video.get("url", "") or ""
    slug = re.sub(r"-\d+/?$", "", url.rstrip("/").rsplit("/", 1)[-1])
    return _words(slug.replace("-", " "))


def _pick_file(video: dict) -> str | None:
    """Choose the best landscape HD-ish file link from a Pexels video result."""
    files = video.get("video_files", [])
    landscape = [f for f in files if (f.get("width") or 0) >= (f.get("height") or 0)]
    cands = landscape or files
    if not cands:
        return None
    cands.sort(key=lambda f: abs((f.get("width") or 0) - 1920))
    return cands[0].get("link")


def _score(video: dict, qwords: set[str]) -> float:
    """Higher = better match. Rewards slug overlap + HD landscape; penalises
    generic-people clips when the query isn't about people."""
    slug = _slug_words(video)
    overlap = len(qwords & slug)
    score = overlap * 10.0
    w, h = video.get("width") or 0, video.get("height") or 0
    if w >= h and w >= 1280:
        score += 3
    if 4 <= (video.get("duration") or 0) <= 60:
        score += 1
    wants_people = bool(qwords & _PEOPLE_INTENT)
    if not wants_people and (slug & _PEOPLE_GENERIC):
        score -= 6                       # deprioritise generic stock-people B-roll
    return score


def search_candidates(query: str, per_page: int = 12) -> list[dict]:
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return []
    import requests
    r = requests.get(_SEARCH, headers={"Authorization": key},
                     params={"query": query, "orientation": "landscape",
                             "per_page": per_page, "size": "medium"}, timeout=30)
    r.raise_for_status()
    return r.json().get("videos", [])


def select_best(videos: list[dict], query: str, seen_ids: set | None = None) -> dict | None:
    """Re-rank candidates and return the best unused one (for variety)."""
    qwords = _words(query)
    ranked = sorted(videos, key=lambda v: _score(v, qwords), reverse=True)
    seen = seen_ids if seen_ids is not None else set()
    for v in ranked:
        if v.get("id") not in seen and _pick_file(v):
            return v
    return ranked[0] if ranked and _pick_file(ranked[0]) else None


def search(query: str) -> str | None:
    """Back-compat: best single stock-video URL for `query`, or None."""
    best = select_best(search_candidates(query), query)
    return _pick_file(best) if best else None


def download(url: str, out_path: str) -> str:
    import requests
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    return str(out)


def _placeholder(query: str, out_path: str, seconds: float = 5.0) -> str:
    """Make a coloured card clip labelled with the query (no key / no result)."""
    h = int(hashlib.md5(query.encode()).hexdigest(), 16)
    r, g, b = 40 + h % 90, 40 + (h >> 8) % 90, 60 + (h >> 16) % 90
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    label = query.replace("'", "").replace(":", " ").upper()[:40]
    draw = ""
    if pathlib.Path(_FONT).exists() and _has_drawtext():
        draw = (f",drawtext=fontfile='{_FONT}':text='{label}':fontcolor=white@0.85:"
                f"fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2")
    subprocess.run([
        "ffmpeg", "-y", "-nostdin", "-f", "lavfi",
        "-i", f"color=c=0x{r:02x}{g:02x}{b:02x}:s=1920x1080:d={max(1, seconds)}",
        "-vf", f"format=yuv420p{draw}", "-r", "30", "-c:v", "libx264", str(out),
    ], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    return str(out)


def fetch(query: str, out_path: str, seconds: float = 5.0,
          seen_ids: set | None = None) -> dict:
    """Get the best clip for `query`. Returns {path, source, query, score, id}.
    Never raises on a missing key / no result — falls back to a placeholder."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH.")
    try:
        best = select_best(search_candidates(query), query, seen_ids)
        if best:
            link = _pick_file(best)
            if link:
                if seen_ids is not None:
                    seen_ids.add(best.get("id"))
                return {"path": download(link, out_path), "source": "pexels",
                        "query": query, "score": _score(best, _words(query)),
                        "id": best.get("id")}
    except Exception:  # noqa: BLE001 - degrade to placeholder, never break the run
        pass
    return {"path": _placeholder(query, out_path, seconds), "source": "placeholder",
            "query": query, "score": 0.0, "id": None}
