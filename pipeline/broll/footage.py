"""[BROLL] FOOTAGE — fetch a stock clip per scene from Pexels (free API).

`PEXELS_API_KEY` (free at pexels.com/api) enables real footage. With no key we
fall back to a generated placeholder card so the whole pipeline still runs and you
can judge sync/captions/assembly before signing up. Marginal cost: £0 (Pexels is
free); this is the piece that replaces Vidrush's expensive web-footage step.
"""
from __future__ import annotations
import os, hashlib, pathlib, subprocess, shutil

_SEARCH = "https://api.pexels.com/videos/search"
_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def available() -> bool:
    return bool(os.getenv("PEXELS_API_KEY"))


def _pick_file(video: dict) -> str | None:
    """Choose the best landscape HD-ish file link from a Pexels video result."""
    files = video.get("video_files", [])
    landscape = [f for f in files if (f.get("width") or 0) >= (f.get("height") or 0)]
    cands = landscape or files
    if not cands:
        return None
    # prefer ~1080p: closest width to 1920 without going wild
    cands.sort(key=lambda f: abs((f.get("width") or 0) - 1920))
    return cands[0].get("link")


def search(query: str, orientation: str = "landscape", per_page: int = 5) -> str | None:
    """Return a stock-video URL for `query`, or None. Requires PEXELS_API_KEY."""
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None
    import requests
    r = requests.get(_SEARCH, headers={"Authorization": key},
                     params={"query": query, "orientation": orientation,
                             "per_page": per_page, "size": "medium"}, timeout=30)
    r.raise_for_status()
    for video in r.json().get("videos", []):
        link = _pick_file(video)
        if link:
            return link
    return None


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
    if pathlib.Path(_FONT).exists():
        draw = (f",drawtext=fontfile='{_FONT}':text='{label}':fontcolor=white@0.85:"
                f"fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2")
    subprocess.run([
        "ffmpeg", "-y", "-nostdin", "-f", "lavfi",
        "-i", f"color=c=0x{r:02x}{g:02x}{b:02x}:s=1920x1080:d={max(1, seconds)}",
        "-vf", f"format=yuv420p{draw}", "-r", "30", "-c:v", "libx264", str(out),
    ], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    return str(out)


def fetch(query: str, out_path: str, seconds: float = 5.0) -> dict:
    """Get a clip for `query`. Returns {path, source, query}. Never raises on a
    missing key / no result — falls back to a placeholder so the build continues."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH.")
    try:
        url = search(query)
        if url:
            return {"path": download(url, out_path), "source": "pexels", "query": query}
    except Exception:  # noqa: BLE001 - degrade to placeholder, never break the run
        pass
    return {"path": _placeholder(query, out_path, seconds),
            "source": "placeholder", "query": query}
