"""Assemble a human-reviewable video brief (markdown) from pipeline state."""
from __future__ import annotations
import pathlib, datetime, re

_OUT = pathlib.Path(__file__).parent.parent / "output"


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def write_brief(job) -> str:
    _OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    path = _OUT / f"{stamp}_{_slugify(job.title)}.md"
    md = []
    md.append(f"# {job.title}\n")
    md.append(f"*Topic:* `{job.topic.get('id')}`  ·  *Anchor:* {job.topic.get('anchor')}\n")
    md.append("## Grounded facts (each must appear in the script)\n")
    for i, s in enumerate(job.sources, 1):
        md.append(f"{i}. {s['claim']}  \n   — [{s['source_name']}]({s['source_url']})")
    md.append("\n## Thumbnail concepts\n")
    for tn in job.thumbnail_paths:
        md.append(f"- **{tn['variant']}**: {tn['caption']} — {tn['subject']} ({tn['style']})")
    md.append("\n## Script\n")
    md.append("```\n" + job.script_text + "\n```")
    md.append("\n## Metadata\n")
    md.append("**Tags:** " + ", ".join(job.meta.get("tags", [])))
    md.append("\n**Description:**\n```\n" + job.meta.get("description", "") + "\n```")
    md.append("**Chapters:** " + " | ".join(f"{c['t']} {c['label']}" for c in job.meta.get("chapters", [])))
    path.write_text("\n".join(md), encoding="utf-8")
    return str(path)
