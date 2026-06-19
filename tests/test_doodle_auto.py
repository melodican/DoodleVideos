"""Tests for the 4->7 doodle runner: rename-by-order, missing-check, manual checkpoint."""
import subprocess, sys, pathlib
from pipeline.doodle.timestamps import parse
from pipeline.doodle import images

TRANSCRIPT = "0:00 Intro\n0:05 Middle bit\n0:11 The ending\n"


def _segs():
    return parse(TRANSCRIPT)


def test_rename_by_order(tmp_path):
    segs = _segs()
    src = tmp_path / "raw"; src.mkdir()
    # create 3 fake images in non-timestamp order; natural sort -> 1,2,10
    for n in ("img1.png", "img2.png", "img10.png"):
        (src / n).write_bytes(b"x")
    dst = tmp_path / "images"
    mapping = images.rename_by_order(str(src), segs, str(dst))
    assert set(mapping) == {"0:00", "0:05", "0:11"}
    assert (dst / "000.png").exists()
    assert (dst / "002.png").exists()
    assert images.missing(segs, str(dst)) == []


def test_rename_count_mismatch_raises(tmp_path):
    segs = _segs()
    src = tmp_path / "raw"; src.mkdir()
    (src / "only1.png").write_bytes(b"x")
    try:
        images.rename_by_order(str(src), segs, str(tmp_path / "out"))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_missing_reports_gaps(tmp_path):
    segs = _segs()
    d = tmp_path / "images"; d.mkdir()
    (d / "000.png").write_bytes(b"x")
    assert images.missing(segs, str(d)) == ["001.png", "002.png"]


def test_auto_manual_checkpoint(tmp_path):
    """With no API key and no --images-in, auto stops at the manual checkpoint (exit 2)."""
    t = tmp_path / "t.txt"; t.write_text(TRANSCRIPT)
    r = subprocess.run(
        [sys.executable, "-m", "pipeline.doodle.run", "auto", str(t),
         str(tmp_path / "vo.mp3"), "--out", str(tmp_path / "out")],
        cwd=pathlib.Path(__file__).parent.parent, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert r.returncode == 2, r.stderr
    assert "MANUAL CHECKPOINT" in r.stdout
    assert (tmp_path / "out" / "batch_prompt.txt").exists()
