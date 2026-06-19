"""[ASSEMBLE] Autonomous replacement for the manual CapCut edit.

Given images named by timestamp (e.g. 0_07.png) + the VO audio, build the final
mp4 with ffmpeg: each image is shown from its timestamp until the next one's, and
the last image holds until the audio ends. No manual timeline editing.
"""
from __future__ import annotations
import pathlib, subprocess, shutil
from .timestamps import Segment


def compute_durations(segments: list[Segment], audio_seconds: float) -> list[tuple[str, float]]:
    """Distribute the full audio across images in proportion to each segment's
    word count.

    The narration is read at a roughly uniform pace, so an image whose line has
    twice the words should stay on screen about twice as long. This keeps frames
    in sync with any voiceover of the same text (e.g. dropped-in ElevenLabs
    audio) without needing exact per-word timestamps."""
    weights = [max(1, len(s.text.split())) for s in segments]
    total = sum(weights) or 1
    return [(s.filename, max(0.3, round(audio_seconds * w / total, 3)))
            for s, w in zip(segments, weights)]


def build_concat_file(durations: list[tuple[str, float]], images_dir: str) -> str:
    """Build ffmpeg concat-demuxer text. Each image needs a trailing repeat line.

    Uses absolute paths because ffmpeg's concat demuxer resolves relative entries
    against the script file's own directory, which would double the path.
    """
    d = pathlib.Path(images_dir)
    lines = []
    for fname, dur in durations:
        p = (d / fname).resolve().as_posix()
        lines.append(f"file '{p}'")
        lines.append(f"duration {dur}")
    # concat demuxer quirk: repeat the last file with no duration
    if durations:
        lines.append(f"file '{(d / durations[-1][0]).resolve().as_posix()}'")
    return "\n".join(lines) + "\n"


def audio_duration(audio_path: str) -> float:
    """Probe audio length with ffprobe."""
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found; pass audio_seconds explicitly.")
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path])
    return float(out.strip())


def render(segments: list[Segment], images_dir: str, audio_path: str,
           out_path: str = "output/video.mp4", audio_seconds: float | None = None,
           fps: int = 30) -> str:
    """Assemble images + VO into a 16:9 mp4. Requires ffmpeg on PATH."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH.")
    secs = audio_seconds if audio_seconds is not None else audio_duration(audio_path)
    durations = compute_durations(segments, secs)
    concat_path = pathlib.Path(images_dir) / "_concat.txt"
    concat_path.write_text(build_concat_file(durations, images_dir))
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-i", audio_path,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,"
               "crop=1920:1080,format=yuv420p",
        "-r", str(fps), "-c:v", "libx264", "-c:a", "aac",
        "-shortest", out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path
