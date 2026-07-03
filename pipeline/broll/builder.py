"""[BROLL] BUILDER — a project folder (+ VO) → captioned explainer/documentary mp4.

Flow: timed segments (reuse the transcript, or Whisper) → scenes → per-scene visual
(a Pexels stock clip, or an on-hand AI image) → PIL caption PNGs → assemble with
captions baked in + VO. Output: video_broll.mp4 (kept separate from the doodle
video.mp4 so you can compare renderers).

`source="stock"` fetches footage per scene (needs PEXELS_API_KEY for real clips).
`source="images"` uses the project's existing AI images (images/NNN.png), one per
segment — a free, monetization-safe way to prove the captioned assembler end to end.

Marginal cost ≈ VO + a few pennies; footage is free. The cheap, fully-API Vidrush
alternative and the seed of the Content-Factory documentary renderer.
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


def _timed_segments(proj: pathlib.Path, vo: pathlib.Path, transcript_path: str | None,
                    progress) -> list:
    tpath = pathlib.Path(transcript_path) if transcript_path else (proj / "transcript.txt")
    if tpath.exists():
        progress("transcribe", f"Using {tpath.name} (no Whisper cost)")
        return parse(tpath.read_text(encoding="utf-8"))
    progress("transcribe", f"Transcribing {vo.name}…")
    fine = transcribe.transcribe(str(vo))
    (proj / "transcript.txt").write_text(transcribe.to_transcript_text(fine), encoding="utf-8")
    return fine


def build_broll(project_dir: str, audio_path: str | None = None,
                transcript_path: str | None = None, topic: str = "",
                seconds_per_clip: float | None = None, source: str = "stock",
                motion: bool = False, captions_on: bool = False,
                caption_style: str = "bold", require_director: bool = False,
                max_scenes: int | None = None, progress=None) -> str:
    """Build video_broll.mp4 for a project. Calls progress(stage, detail).

    Captions are OFF by default — a channel/format choice (see channel blueprints),
    not a universal default. Long-form documentaries typically render clean."""
    progress = progress or _noop
    proj = pathlib.Path(project_dir); proj.mkdir(parents=True, exist_ok=True)

    vo = pathlib.Path(audio_path) if audio_path else find_audio(proj)
    if not vo or not vo.exists():
        raise FileNotFoundError(f"no voiceover found in {proj} (expected vo.mp3)")

    fine = _timed_segments(proj, vo, transcript_path, progress)
    secs = audio_duration(str(vo))

    # scenes + visuals: on-hand AI images (one per segment) or fetched stock footage
    if source == "images":
        imgs = sorted((proj / "images").glob("*.png"))
        if not imgs:
            raise FileNotFoundError(f"no images/ in {proj} for source=images")
        n = min(len(fine), len(imgs))
        scenes = fine[:n]
        visuals = [str(imgs[i]) for i in range(n)]
    else:
        spc = seconds_per_clip if seconds_per_clip else float(os.getenv("SECONDS_PER_CLIP", "6"))
        scenes = group_segments(fine, spc)
        if max_scenes:
            scenes = scenes[:max_scenes]        # plan/fetch only what we'll use
        progress("plan", "Choosing footage for each scene…")
        queries, director = visual_plan.plan_queries(scenes, topic=topic,
                                                     require_director=require_director)
        progress("plan", f"Director: {director}")       # explicit — no hidden fallback
        durs = assemble.scene_durations(scenes, secs)
        fdir = proj / "footage"; visuals = []; real = 0; seen: set = set()
        for i, (q, dur) in enumerate(zip(queries, durs)):
            progress("footage", f"Footage {i + 1}/{len(scenes)}: “{q}”")
            res = footage.fetch(q, str(fdir / f"{i:03d}.mp4"), seconds=dur, seen_ids=seen)
            visuals.append(res["path"]); real += res["source"] == "pexels"
        progress("footage", f"{real}/{len(scenes)} real clips"
                            + ("" if footage.available() else " (set PEXELS_API_KEY for real footage)"))

    if max_scenes:                                   # demo excerpt
        scenes, visuals = scenes[:max_scenes], visuals[:max_scenes]

    # captions: opt-in per channel/format. Off = clean frame (long-form docs).
    chunks = []
    if captions_on:
        progress("captions", f"Rendering captions ({caption_style})…")
        scene_end = (scenes[-1].end if scenes[-1].end is not None else secs)
        cdir = proj / "captions"
        for i, (cs, ce, text) in enumerate(captions.caption_chunks(fine, secs)):
            if cs >= scene_end:
                break
            png = captions.caption_png(text, str(cdir / f"{i:03d}.png"), style=caption_style)
            chunks.append((cs, ce, png))
    else:
        progress("captions", "Captions off (clean frame)")

    out = assemble.render(visuals, scenes, chunks, str(vo),
                          out_path=str(proj / "video_broll.mp4"),
                          audio_seconds=secs, motion=motion, progress=progress)
    progress("done", out)
    return out
