"""[5-6] IMAGES — generate one doodle image per timestamp, named by timestamp.

Two ways to fill the images folder:
  * generate(...)        — call an image API (GPT-Image-2 / Higgsfield) per segment
                           when a key is set; each saved as e.g. ``0_07.png``.
  * rename_by_order(...) — you generated images externally (Higgsfield UI) and
                           downloaded a folder; this maps them onto the timestamp
                           filenames *in order* (generation order == script order).

``missing(...)`` verifies every expected timestamp image is present before assembly.
"""
from __future__ import annotations
import os, re, base64, pathlib, shutil
from .timestamps import Segment

_IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def available() -> bool:
    """True if an image-generation key is configured."""
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("IMAGE_GEN_API_KEY"))


def _natural_key(name: str):
    """Sort 'img2' before 'img10' and respect leading numbers."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def list_images(src_dir: str) -> list[pathlib.Path]:
    d = pathlib.Path(src_dir)
    files = [p for p in d.iterdir() if p.suffix.lower() in _IMG_EXTS]
    return sorted(files, key=lambda p: _natural_key(p.name))


def rename_by_order(src_dir: str, segments: list[Segment], dst_dir: str) -> dict:
    """Map externally-generated images (in order) onto timestamp filenames.

    Returns {timestamp_label: dst_path}. Raises if counts don't match so a
    silent off-by-one can't corrupt the whole video.
    """
    src = list_images(src_dir)
    if len(src) != len(segments):
        raise ValueError(
            f"image count {len(src)} != segment count {len(segments)}; "
            "cannot map by order. Check the generated set.")
    dst = pathlib.Path(dst_dir); dst.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for seg, img in zip(segments, src):
        target = dst / seg.filename
        shutil.copyfile(img, target)
        mapping[seg.label] = str(target)
    return mapping


def missing(segments: list[Segment], images_dir: str) -> list[str]:
    """Expected timestamp filenames that are not yet present."""
    d = pathlib.Path(images_dir)
    return [s.filename for s in segments if not (d / s.filename).exists()]


def generate(per_segment_prompts: list[dict], out_dir: str) -> list[str]:
    """Generate one image per prompt via OpenAI Images (GPT-Image-2). Saves by
    the manifest filename. No-op-raises if no key is set so callers can fall back
    to the manual checkpoint.
    """
    if not available():
        raise RuntimeError("no image API key set (OPENAI_API_KEY / IMAGE_GEN_API_KEY)")
    import requests  # local import: only needed on the live path
    key = os.getenv("OPENAI_API_KEY") or os.getenv("IMAGE_GEN_API_KEY")
    model = os.getenv("IMAGE_GEN_MODEL", "gpt-image-1")
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    made = []
    for item in per_segment_prompts:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "prompt": item["prompt"],
                  "size": "1536x1024", "n": 1},
            timeout=120,
        )
        resp.raise_for_status()
        b64 = resp.json()["data"][0]["b64_json"]
        target = out / item["filename"]
        target.write_bytes(base64.b64decode(b64))
        made.append(str(target))
    return made
