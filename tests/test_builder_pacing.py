"""Per-project pacing override (SECONDS_PER_IMAGE slider)."""
from pipeline.doodle import builder


def test_scene_seconds_override_wins(monkeypatch):
    monkeypatch.setenv("SECONDS_PER_IMAGE", "4")
    assert builder.scene_seconds(8) == 8.0           # explicit override
    assert builder.scene_seconds(8.5) == 8.5


def test_scene_seconds_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("SECONDS_PER_IMAGE", "6")
    assert builder.scene_seconds(None) == 6.0
    assert builder.scene_seconds(0) == 6.0           # 0/non-positive ignored


def test_scene_seconds_default_when_unset(monkeypatch):
    monkeypatch.delenv("SECONDS_PER_IMAGE", raising=False)
    assert builder.scene_seconds(None) == 4.0
