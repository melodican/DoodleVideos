"""Smoke tests — pipeline runs offline and produces a QA-passing brief."""
import os, pathlib
from pipeline import run as runner


def test_dry_run_produces_brief(tmp_path, monkeypatch):
    job = runner.run(dry_run=True, seed=1)
    assert job.title
    assert job.sources, "must have grounded sources"
    assert job.qa_passed, "QA gate should pass for seeded run"
    assert pathlib.Path(job.brief_path).exists()


def test_every_source_is_cited():
    job = runner.run(dry_run=True, seed=3)
    for i, _ in enumerate(job.sources, 1):
        assert f"[{i}]" in job.script_text


def test_speculation_flagged():
    job = runner.run(dry_run=True, seed=5)
    assert "[SPECULATION]" in job.script_text
