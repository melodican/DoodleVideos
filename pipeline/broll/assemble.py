"""[BROLL] ASSEMBLE — stitch visuals + captions + VO into a 16:9 mp4.

Each scene's visual (a stock clip OR a still image) is scaled-to-cover and cropped
to 1920x1080 for its spoken duration; its caption chunks are composited on top with
the `overlay` filter (PIL-rendered PNGs — no libass needed). Scenes are concatenated
and the voiceover muxed. Optional Ken Burns motion on stills (perf-heavy — off by
default). ffmpeg only; no paid services.
"""
from __future__ import annotations
import pathlib, subprocess, shutil
from pipeline.doodle.timestamps import Segment
from pipeline.doodle.assemble import audio_duration

_IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")
_COVER = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p"


def scene_durations(scenes: list[Segment], audio_seconds: float) -> list[float]:
    out = []
    for s in scenes:
        end = s.end if s.end is not None else audio_seconds
        out.append(max(0.5, round(end - s.start, 3)))
    return out


def _is_image(path: str) -> bool:
    return pathlib.Path(path).suffix.lower() in _IMG_EXTS


def scene_overlays(scene: Segment, dur: float,
                   chunks: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Caption chunks that fall in this scene, expressed in the scene's LOCAL time."""
    start = scene.start
    end = start + dur
    out = []
    for cs, ce, png in chunks:
        if cs < end and ce > start:  # overlaps the scene window
            out.append((max(0.0, cs - start), min(dur, ce - start), png))
    return out


def _ken_burns(i: int) -> str:
    # alternate a slow zoom-in / zoom-out; modest pre-scale keeps it affordable
    if i % 2 == 0:
        z = "z='min(zoom+0.0009,1.3)'"
    else:
        z = "z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0009))'"
    return (f"scale=2112:1188,zoompan={z}:d={{frames}}:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,format=yuv420p")


def _render_scene(visual: str, dur: float, overlays: list[tuple[float, float, str]],
                  out_path: str, index: int, motion: bool) -> str:
    """One scene → a normalized, captioned clip of exactly `dur` seconds."""
    if _is_image(visual):
        base_in = ["-loop", "1", "-t", f"{dur}", "-i", visual]
        base_vf = _ken_burns(index).format(frames=max(15, int(dur * 30))) if motion else _COVER
    else:
        base_in = ["-stream_loop", "-1", "-t", f"{dur}", "-i", visual]
        base_vf = _COVER

    inputs = base_in
    for _, _, png in overlays:
        inputs += ["-loop", "1", "-t", f"{dur}", "-i", png]

    fc = [f"[0:v]{base_vf}[bg]"]
    label = "bg"
    for k, (ls, le, _) in enumerate(overlays):
        nxt = f"o{k}"
        fc.append(f"[{label}][{k + 1}:v]overlay=0:0:enable='between(t,{ls:.3f},{le:.3f})'[{nxt}]")
        label = nxt

    subprocess.run([
        "ffmpeg", "-y", "-nostdin", *inputs,
        "-filter_complex", ";".join(fc), "-map", f"[{label}]",
        "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        out_path,
    ], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    return out_path


def render(scene_visuals: list[str], scenes: list[Segment],
           caption_chunks: list[tuple[float, float, str]], audio_path: str, out_path: str,
           audio_seconds: float | None = None, motion: bool = False, progress=None) -> str:
    """Assemble captioned scene visuals + VO. Returns out_path."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH.")
    if len(scene_visuals) != len(scenes):
        raise ValueError(f"{len(scene_visuals)} visuals != {len(scenes)} scenes")
    secs = audio_seconds if audio_seconds is not None else audio_duration(audio_path)
    durs = scene_durations(scenes, secs)

    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    segdir = out.parent / "_segments"; segdir.mkdir(parents=True, exist_ok=True)

    seg_paths = []
    for i, (visual, scene, dur) in enumerate(zip(scene_visuals, scenes, durs)):
        if progress:
            progress("assemble", f"Rendering scene {i + 1}/{len(scenes)}")
        ov = scene_overlays(scene, dur, caption_chunks)
        seg_paths.append(_render_scene(visual, dur, ov, str(segdir / f"seg{i:03d}.mp4"), i, motion))

    concat = segdir / "_concat.txt"
    concat.write_text("".join(f"file '{pathlib.Path(p).resolve().as_posix()}'\n"
                              for p in seg_paths), encoding="utf-8")
    if progress:
        progress("mux", "Adding voiceover…")
    subprocess.run([
        "ffmpeg", "-y", "-nostdin", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", audio_path, "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(out),
    ], check=True, stdin=subprocess.DEVNULL)
    return str(out)
