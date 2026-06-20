"""Tests for the YouTube upload helper (no network / no real OAuth)."""
import os, pathlib
import pytest

from pipeline.doodle import youtube_upload as yt


def test_parse_tags_handles_list_and_csv():
    assert yt._parse_tags("finance, money,  taxes ") == ["finance", "money", "taxes"]
    assert yt._parse_tags(["a", " b ", ""]) == ["a", "b"]
    assert yt._parse_tags("") == []
    assert yt._parse_tags(None) == []


def test_paths_honor_env(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_CLIENT_SECRETS", str(tmp_path / "cs.json"))
    monkeypatch.setenv("YT_TOKEN_STORE", str(tmp_path / "tok.json"))
    assert yt.client_secrets_path() == tmp_path / "cs.json"
    assert yt.token_path() == tmp_path / "tok.json"
    assert yt.configured() is False
    (tmp_path / "cs.json").write_text("{}")
    assert yt.configured() is True


def test_relative_paths_resolve_under_repo_root(monkeypatch):
    monkeypatch.setenv("YT_CLIENT_SECRETS", "client_secret.json")
    p = yt.client_secrets_path()
    assert p.is_absolute()
    assert p.name == "client_secret.json"


def test_get_credentials_without_secrets_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_CLIENT_SECRETS", str(tmp_path / "missing.json"))
    monkeypatch.setenv("YT_TOKEN_STORE", str(tmp_path / "tok.json"))
    with pytest.raises(yt.NeedsAuthSetup):
        yt.get_credentials()


def test_upload_missing_video_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_CLIENT_SECRETS", str(tmp_path / "cs.json"))
    (tmp_path / "cs.json").write_text("{}")
    with pytest.raises(FileNotFoundError):
        yt.upload(str(tmp_path / "nope.mp4"), title="x")
