"""Reusable build pipeline: a project folder (+ voiceover) -> synced doodle video.

Shared by the CLI and the web dashboard. Reports progress via a callback so a UI
can show live status (transcribing / image N of M / assembling).
"""
from __future__ import annotations
import os, pathlib
from . import transcribe, images, assemble
from .timestamps import group_segments
from .image_prompts import write_manifest, batch_prompt, per_segment_prompts


def _noop(stage: str, detail: str = "") -> None:
    pass


def find_audio(proj: pathlib.Path):
    for pat in ("vo.*", "*.mp3", "*.wav", "*.m4a"):
        cands = [p for p in sorted(proj.glob(pat)) if p.is_file()]
        if cands:
            return cands[0]
    return None


class NeedImages(RuntimeError):
    """Raised when images can't be produced (no API key and none supplied)."""


def build_project(project_dir: str, audio_path: str | None = None,
                  images_in: str | None = None, progress=None) -> str:
    """Transcribe the VO, generate doodles, assemble a synced 16:9 mp4.
    Returns the path to video.mp4. Calls progress(stage, detail)."""
    progress = progress or _noop
    proj = pathlib.Path(project_dir); proj.mkdir(parents=True, exist_ok=True)

    vo = pathlib.Path(audio_path) if audio_path else find_audio(proj)
    if not vo or not vo.exists():
        raise FileNotFoundError(f"no voiceover found in {proj} (expected vo.mp3)")

    progress("transcribe", f"Transcribing {vo.name}…")
    segs = transcribe.transcribe(str(vo))
    # merge short segments into longer scenes -> fewer images (less cost + time)
    segs = group_segments(segs, float(os.getenv("SECONDS_PER_IMAGE", "4")))
    (proj / "transcript.txt").write_text(transcribe.to_transcript_text(segs), encoding="utf-8")
    write_manifest(segs, str(proj / "image_manifest.json"))
    (proj / "batch_prompt.txt").write_text(batch_prompt(segs), encoding="utf-8")
    progress("segments", f"{len(segs)} segments")

    images_dir = proj / "images"
    if images_in:
        images.rename_by_order(images_in, segs, str(images_dir))
    elif images.available():
        prompts = per_segment_prompts(segs)
        n = len(prompts)
        images.generate(prompts, str(images_dir),
                        on_progress=lambda i, _n: progress("images", f"Generating image {i}/{n}"))
    else:
        raise NeedImages("no OPENAI_API_KEY and no images supplied — see batch_prompt.txt")

    miss = images.missing(segs, str(images_dir))
    if miss:
        raise RuntimeError(f"missing {len(miss)} images: {miss[:5]}")

    progress("assemble", "Assembling video…")
    video = assemble.render(segs, str(images_dir), str(vo),
                            out_path=str(proj / "video.mp4"), sync="timestamps")
    progress("done", video)
    return video
