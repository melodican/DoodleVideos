"""Generate one Higgsfield/GPT-Image-2 prompt per timestamp segment.

Emits both:
  - a per-segment prompt list (scene line + locked style block), and
  - a single batch prompt in the same shape the workflow pastes into Claude Code.
The locked style block (config/styles/doodle.yaml) guarantees a consistent look.
"""
from __future__ import annotations
import pathlib, json
import yaml
from .timestamps import Segment

_STYLE = pathlib.Path(__file__).parent.parent.parent / "config" / "styles" / "doodle.yaml"


def _style() -> dict:
    return yaml.safe_load(_STYLE.read_text())["style"]


def scene_line(seg: Segment) -> str:
    """One-line visual brief for a segment. TODO: optional LLM for richer scenes."""
    return ("Create ONE rough, imperfect, COLOURFUL hand-drawn marker doodle (NOT "
            "clipart, NOT a clean icon) of a SINGLE clear subject for this narration "
            "— one object, character, or scene, big and centered, with real detail "
            "and personality and a few colours. If several things are mentioned, "
            f"focus on the most important. Do NOT write the sentence: \"{seg.text}\"")


def per_segment_prompts(segments: list[Segment]) -> list[dict]:
    st = _style()
    out = []
    for s in segments:
        prompt = f"{scene_line(s)}\n\n{st['block']}"
        out.append({"timestamp": s.label, "filename": s.filename,
                    "model": st["model"], "aspect_ratio": st["aspect_ratio"],
                    "prompt": prompt})
    return out


def write_manifest(segments: list[Segment], out_path: str) -> str:
    """Write the render manifest Higgsfield consumes (one entry per image)."""
    data = per_segment_prompts(segments)
    pathlib.Path(out_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out_path


def batch_prompt(segments: list[Segment]) -> str:
    """The single paste-into-Claude-Code prompt: instructions + style + script."""
    st = _style()
    header = (
        "You are going to generate images for a YouTube script, one image for "
        "every timestamp. Read the script carefully and create a separate image "
        "for each timestamp that visually illustrates what the narrator is saying "
        f"at that exact moment. Generate each image with {st['model']} as a "
        f"{st['aspect_ratio']} wide YouTube frame.\n\n")
    script = "\n".join(f"{s.label} {s.text}" for s in segments)
    return f"{header}{st['block']}\n\nHere is the script with timestamps:\n{script}"
