"""Reference-image style lock: resolution precedence + plumbing."""
import pathlib
import pytest

from pipeline.doodle import builder, images


def test_reference_precedence_override_wins(tmp_path):
    proj = tmp_path / "p"; proj.mkdir()
    (proj / "reference.png").write_bytes(b"x")
    override = tmp_path / "custom.png"; override.write_bytes(b"y")
    assert builder.reference_for(proj, str(override)) == override


def test_reference_override_missing_is_ignored(tmp_path):
    proj = tmp_path / "p"; proj.mkdir()
    (proj / "reference.png").write_bytes(b"x")
    # a non-existent override falls through to None (not the project file)
    assert builder.reference_for(proj, str(tmp_path / "nope.png")) is None


def test_reference_finds_project_file(tmp_path):
    proj = tmp_path / "p"; proj.mkdir()
    assert builder.reference_for(proj) is None
    (proj / "reference.jpg").write_bytes(b"x")
    assert builder.reference_for(proj).name == "reference.jpg"


def test_generate_without_key_raises_even_with_reference(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("IMAGE_GEN_API_KEY", raising=False)
    ref = tmp_path / "r.png"; ref.write_bytes(b"x")
    with pytest.raises(RuntimeError):
        images.generate([{"prompt": "p", "filename": "000.png"}],
                        str(tmp_path / "out"), reference_path=str(ref))
