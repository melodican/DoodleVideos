"""Thumbnail composition (offline, PIL)."""
import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image
from pipeline.doodle import thumbnail


def _frame(path, w=1536, h=1024, colour=(120, 180, 230)):
    Image.new("RGB", (w, h), colour).save(path)


def test_make_thumbnail_is_1280x720(tmp_path):
    src = tmp_path / "000.png"; _frame(src)
    out = thumbnail.make_thumbnail(str(src), "What actually is inflation?", str(tmp_path / "t.png"))
    im = Image.open(out)
    assert im.size == (1280, 720)
    assert (tmp_path / "t.png").stat().st_size > 0


def test_long_title_still_fits(tmp_path):
    src = tmp_path / "000.png"; _frame(src)
    long = "Why the government keeps printing money and what it quietly does to your savings"
    out = thumbnail.make_thumbnail(str(src), long, str(tmp_path / "t2.png"))
    assert Image.open(out).size == (1280, 720)


def test_empty_title_uses_fallback(tmp_path):
    src = tmp_path / "000.png"; _frame(src, w=400, h=400)   # also exercises upscaling
    out = thumbnail.make_thumbnail(str(src), "   ", str(tmp_path / "t3.png"))
    assert Image.open(out).size == (1280, 720)
