"""Orchestrator: chains the 9 pipeline stages for one video.

Usage:
    python -m pipeline.run --dry-run      # run all stages except upload
    python -m pipeline.run                # full run incl. scheduled upload
"""
from __future__ import annotations
import argparse, logging
from dataclasses import dataclass, field

from . import ideate, research, script, voice, video, thumbnail, metadata, qa, upload

log = logging.getLogger("pipeline")


@dataclass
class Job:
    """Carries state across stages for a single video."""
    title: str = ""
    topic: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)   # grounded facts + citations
    script_text: str = ""
    voice_path: str = ""
    video_path: str = ""
    thumbnail_paths: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)       # description, tags, chapters
    qa_passed: bool = False


def run(dry_run: bool = False) -> Job:
    job = Job()
    job.topic, job.title = ideate.pick_topic()          # [1]
    job.sources = research.gather(job.topic)            # [2] GROUNDING
    job.script_text = script.write(job.title, job.sources)  # [3]
    job.voice_path = voice.synthesize(job.script_text)  # [4]
    job.video_path = video.render(job.voice_path, job.sources)  # [5] Vid Rush
    job.thumbnail_paths = thumbnail.make(job.title)     # [6]
    job.meta = metadata.build(job.title, job.script_text, job.sources)  # [7]
    job.qa_passed = qa.check(job)                       # [8] policy + fact gate
    if not job.qa_passed:
        log.warning("QA failed — holding for review: %s", job.title)
        return job
    if dry_run:
        log.info("DRY RUN complete — skipping upload: %s", job.title)
        return job
    upload.publish(job)                                 # [9]
    return job


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(dry_run=args.dry_run)
