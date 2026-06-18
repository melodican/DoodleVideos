"""Tests for the ElevenLabs VO stage and the whole-loop `make` orchestrator."""
import subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).parent.parent
ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}   # no API keys


def test_voiceover_unavailable_without_key():
    from pipeline.doodle import voiceover
    assert voiceover.available() is False
    try:
        voiceover.synthesize("hello", "/tmp/x.mp3")
        assert False, "expected RuntimeError without key"
    except RuntimeError:
        pass


def _run(args, **env):
    e = dict(ENV); e.update(env)
    return subprocess.run([sys.executable, "-m", "pipeline.doodle.run", *args],
                          cwd=ROOT, capture_output=True, text=True, env=e)


def test_make_stops_at_image_checkpoint(tmp_path):
    r = _run(["make", "Why do cities never sleep?", "--minutes", "1",
              "--out", str(tmp_path / "o")])
    assert r.returncode == 2, r.stderr
    assert "MANUAL CHECKPOINT" in r.stdout
    for f in ("script.txt", "transcript.txt", "batch_prompt.txt", "image_manifest.json"):
        assert (tmp_path / "o" / f).exists(), f


def test_make_maps_images_then_needs_vo(tmp_path):
    # discover segment count, fabricate that many images
    from pipeline.doodle.script_writer import write_script, estimate_timestamps
    from pipeline.doodle.timestamps import parse
    n = len(parse(estimate_timestamps(write_script("Why do cities never sleep?", minutes=1))))
    raw = tmp_path / "raw"; raw.mkdir()
    for i in range(n):
        (raw / f"img{i:03d}.png").write_bytes(b"x")
    r = _run(["make", "Why do cities never sleep?", "--minutes", "1",
              "--out", str(tmp_path / "o"), "--images-in", str(raw)])
    assert r.returncode == 2, r.stderr
    assert "assemble: skipped" in r.stdout
    assert len(list((tmp_path / "o" / "images").glob("*.png"))) == n
