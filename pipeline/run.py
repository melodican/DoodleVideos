"""Orchestrator: chains the pipeline stages for one video.

Usage:
    python -m pipeline.run --dry-run        # ideate->research->script->meta->QA, write brief, no publish
    python -m pipeline.run --dry-run --seed 1   # deterministic (testing)
    python -m pipeline.run                  # full run incl. voice/video/upload (needs API keys)
"""
from __future__ import annotations
import argparse, logging
from dataclasses import dataclass, field

from . import ideate, research, script, voice, video, thumbnail, metadata, qa, upload, brief

log = logging.getLogger("pipeline")


@dataclass
class Job:
    title: str = ""
    topic: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)
    script_text: str = ""
    voice_path: str | None = None
    video_path: str | None = None
    thumbnail_paths: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    qa_passed: bool = False
    brief_path: str = ""


def run(dry_run: bool = False, seed: int | None = None) -> Job:
    job = Job()
    job.topic, job.title = ideate.pick_topic(seed=seed)          # [1]
    log.info("title: %s", job.title)
    job.sources = research.gather(job.topic)                     # [2] GROUNDING
    job.script_text = script.write(job.title, job.sources)       # [3]
    job.thumbnail_paths = thumbnail.make(job.title, job.topic)   # [6 concept]
    job.meta = metadata.build(job.title, job.script_text, job.sources)  # [7]
    job.qa_passed = qa.check(job)                                # [8]
    job.brief_path = brief.write_brief(job)
    log.info("brief written: %s", job.brief_path)
    if not job.qa_passed:
        log.warning("QA failed — holding for review."); return job
    if dry_run:
        log.info("DRY RUN complete — skipping voice/video/upload."); return job
    job.voice_path = voice.synthesize(job.script_text)           # [4]
    job.video_path = video.render(job.voice_path, job.sources)   # [5]
    vid_id = upload.publish(job)                                 # [9]
    if vid_id:
        ideate.record_published(job.topic, job.title)
    return job


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    run(dry_run=args.dry_run, seed=args.seed)
