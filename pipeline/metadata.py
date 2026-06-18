"""[7] METADATA — SEO description (with source links), tags, and chapters."""
from __future__ import annotations
import re


def _slug_tags(title: str, sources: list[dict]) -> list[str]:
    base = ["space", "space documentary", "astronomy", "NASA", "universe",
            "cosmos", "space mysteries", "deep space"]
    words = re.findall(r"[A-Za-z]{4,}", title.lower())
    base += [w for w in words if w not in {"just", "first", "time", "what", "they"}]
    seen, out = set(), []
    for t in base:
        if t not in seen:
            seen.add(t); out.append(t)
    return out[:20]


def build(title: str, script_text: str, sources: list[dict]) -> dict:
    src_block = "\n".join(f"[{i}] {s['source_name']} — {s['source_url']}"
                          for i, s in enumerate(sources, 1))
    description = (
        f"{title}\n\n"
        "A calm, cinematic look at one of the universe's strangest real stories. "
        "Every claim in this video is grounded in published science — sources below.\n\n"
        f"SOURCES\n{src_block}\n\n"
        "#space #astronomy #NASA #universe\n"
    )
    # Chapters: cold open + one per beat + climax
    chapters = [{"t": "0:00", "label": "The signal"}]
    for i, s in enumerate(sources, 1):
        chapters.append({"t": f"{i*3}:00", "label": s["source_name"]})
    return {"description": description,
            "tags": _slug_tags(title, sources),
            "chapters": chapters}
