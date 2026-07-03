"""[BROLL] BUILDER — a project folder (+ VO) → stock-footage explainer mp4.

Flow: timed segments (reuse the transcript, or Whisper) → group into scenes →
plan one footage query per scene → fetch a Pexels clip per scene → build caption
ASS → assemble. Output: video_broll.mp4 (kept separate from the doodle video.mp4
so you can compare the two renderers side by side).

Marginal cost ≈ VO + a few pennies; the footage is free. This is the cheap,
fully-API alternative to Vidrush.
"""
from __future__ import annotations
import os, pathlib
from pipeline.doodle import transcribe
from pipeline.doodle.timestamps import parse, group_segments
from pipeline.doodle.assemble import audio_duration
from . import footage, visual_plan, captions, assemble


def _noop(stage: str, detail: str = "") -> None:
    pass


def find_audio(proj: pathlib.Path):
    for pat in ("vo.*", "*.mp3", "*.wav", "*.m4a"):
        cands = [p for p in sorted(proj.glob(pat)) if p.is_file()]
        if cands:
            return cands[0]
    return None


def build_broll(project_dir: str, audio_path: str | None = None,
                transcript_path: str | None = None, topic: str = "",
                seconds_per_clip: float | None = None, progress=None) -> str:
    """Build video_broll.mp4 for a project. Reuses transcript.txt when present
    (free, no Whisper); otherwise transcribes the VO. Calls progress(stage, detail)."""
    progress = progress or _noop
    proj = pathlib.Path(project_dir); proj.mkdir(parents=True, exist_ok=True)

    vo = pathlib.Path(audio_path) if audio_path else find_audio(proj)
    if not vo or not vo.exists():
        raise FileNotFoundError(f"no voiceover found in {proj} (expected vo.mp3)")

    # 1. timed segments — reuse an existing transcript (free) or Whisper
    tpath = pathlib.Path(transcript_path) if transcript_path else (proj / "transcript.txt")
    if tpath.exists():
        progress("transcribe", f"Using {tpath.name} (no Whisper cost)")
        fine = parse(tpath.read_text(encoding="utf-8"))
    else:
        progress("transcribe", f"Transcribing {vo.name}…")
        fine = transcribe.transcribe(str(vo))
        (proj / "transcript.txt").write_text(transcribe.to_transcript_text(fine), encoding="utf-8")

    spc = seconds_per_clip if seconds_per_clip else float(os.getenv("SECONDS_PER_CLIP", "6"))
    scenes = group_segments(fine, spc)
    secs = audio_duration(str(vo))
    progress("segments", f"{len(scenes)} scenes · {len(fine)} caption lines")

    # 2. plan one footage query per scene (Claude → heuristic fallback)
    progress("plan", "Choosing footage for each scene…")
    queries = visual_plan.plan_queries(scenes, topic=topic)

    # 3. fetch a clip per scene
    fdir = proj / "footage"
    clips, real = [], 0
    durs = assemble.scene_durations(scenes, secs)
    for i, (q, dur) in enumerate(zip(queries, durs)):
        progress("footage", f"Footage {i + 1}/{len(scenes)}: “{q}”")
        res = footage.fetch(q, str(fdir / f"{i:03d}.mp4"), seconds=dur)
        clips.append(res["path"])
        real += res["source"] == "pexels"
    progress("footage", f"{real}/{len(scenes)} real clips"
                        + ("" if footage.available() else " (set PEXELS_API_KEY for real footage)"))

    # 4. captions
    progress("captions", "Building captions…")
    chunks = captions.caption_chunks(fine, secs)
    ass = captions.to_ass(chunks, str(proj / "captions.ass"))

    # 5. assemble
    out = assemble.render(clips, scenes, ass, str(vo),
                          out_path=str(proj / "video_broll.mp4"),
                          audio_seconds=secs, progress=progress)
    progress("done", out)
    return out
