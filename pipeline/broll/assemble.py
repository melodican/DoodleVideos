"""[BROLL] ASSEMBLE — stitch stock clips + captions + VO into a 16:9 mp4.

Per scene: scale-to-cover + centre-crop the clip to 1920x1080, loop/trim it to the
scene's spoken duration, drop its audio. Concat all scenes, burn the caption ASS,
and mux the voiceover. ffmpeg only — no paid services.
"""
from __future__ import annotations
import pathlib, subprocess, shutil
from pipeline.doodle.timestamps import Segment
from pipeline.doodle.assemble import audio_duration

_NORM_VF = ("scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,fps=30,format=yuv420p")


def scene_durations(scenes: list[Segment], audio_seconds: float) -> list[float]:
    out = []
    for s in scenes:
        end = s.end if s.end is not None else audio_seconds
        out.append(max(0.5, round(end - s.start, 3)))
    return out


def _normalize(clip: str, dur: float, out_path: str) -> str:
    """One scene clip → exactly `dur` seconds at 1920x1080/30fps, looped if short."""
    subprocess.run([
        "ffmpeg", "-y", "-nostdin",
        "-stream_loop", "-1", "-t", f"{dur}", "-i", clip, "-an",
        "-vf", _NORM_VF, "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_path,
    ], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    return out_path


def render(scene_clips: list[str], scenes: list[Segment], captions_ass: str | None,
           audio_path: str, out_path: str, audio_seconds: float | None = None,
           progress=None) -> str:
    """Assemble normalized scene clips + captions + VO. Returns out_path."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH.")
    if len(scene_clips) != len(scenes):
        raise ValueError(f"{len(scene_clips)} clips != {len(scenes)} scenes")
    secs = audio_seconds if audio_seconds is not None else audio_duration(audio_path)
    durs = scene_durations(scenes, secs)

    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    segdir = out.parent / "_segments"; segdir.mkdir(parents=True, exist_ok=True)

    seg_paths = []
    for i, (clip, dur) in enumerate(zip(scene_clips, durs)):
        if progress:
            progress("normalize", f"Preparing clip {i + 1}/{len(scene_clips)}")
        seg_paths.append(_normalize(clip, dur, str(segdir / f"seg{i:03d}.mp4")))

    concat = segdir / "_concat.txt"
    concat.write_text("".join(f"file '{pathlib.Path(p).resolve().as_posix()}'\n"
                              for p in seg_paths), encoding="utf-8")

    if progress:
        progress("assemble", "Burning captions + voiceover…")
    vf = []
    if captions_ass:
        ass = pathlib.Path(captions_ass).resolve().as_posix()
        vf = ["-vf", f"subtitles='{ass}'"]
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", audio_path, *vf,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(out),
    ]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    return str(out)
