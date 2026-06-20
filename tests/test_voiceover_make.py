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


def test_estimate_chars_collapses_whitespace():
    from pipeline.doodle import voiceover
    assert voiceover.estimate_chars("  hello   world\n\n") == 11


def test_split_text_keeps_chunks_under_limit():
    from pipeline.doodle import voiceover
    text = "This is a sentence. " * 1000          # ~20k chars
    chunks = voiceover._split_text(text, max_chars=4800)
    assert len(chunks) > 1
    assert all(len(c) <= 4800 for c in chunks)
    # short text stays a single chunk; empty stays empty
    assert voiceover._split_text("Just one line.") == ["Just one line."]
    assert voiceover._split_text("   ") == []


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
