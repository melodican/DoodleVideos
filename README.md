# YouTube Automation — Cosmic Documentary Channel

Fully automated faceless-channel pipeline for the **space / cosmic-mystery documentary**
niche. Designed to be driven by Claude Code on a daily schedule, end-to-end:

> ideate → research (+grounding) → script → voice → video (Vid Rush) → thumbnail → metadata → QA → upload

## Why this niche
- **Fast traction:** highest outlier scores among automatable niches (modeled on Cosmicus, Lone Colonist).
- **High RPM:** family-safe / advertiser-friendly; ~$5–5.5 explainer, ~$7.7 sleep variant.
- **High watch time:** 18–24 min docs with 3–4 mid-rolls.
- **Automation-safe:** public-domain footage (NASA / ESA / JWST), evergreen, infinite topics, zero copyright/news dependency.

## Two channel styles
- **Space documentary** (Vid Rush footage) — see `docs/PIPELINE.md`.
- **Doodle explainer** (MS-Paint / Axen-Ink style, Higgsfield + ffmpeg) — see `docs/DOODLE.md`.
  Fully scripted assembly replaces the manual CapCut edit.

## Pipeline stages
See `docs/PIPELINE.md`. Each stage is a module in `pipeline/` and is chained by `pipeline/run.py`.

## Quick start
```bash
cp .env.example .env        # add API keys
pip install -r requirements.txt
python -m pipeline.run --dry-run     # run the chain without uploading
```

## Status
**Runnable offline.** `python -m pipeline.run --dry-run --seed 1` produces a complete,
QA-passing video brief in `output/` (title, cited facts, script, thumbnail concepts,
description, tags, chapters) with no API keys.

Stages 1-3, 6-8 are implemented (ideation, grounding, script, thumbnail concepts,
metadata, QA gate). Stages 4/5/9 (voice, Vid Rush render, YouTube upload) gracefully
skip until their API keys are set in `.env`, then drop in via the documented TODOs.

Run tests: `python -m pytest tests/`

## Doodle (Axen/Ink) channel
Second pipeline for the MS-Paint explainer niche. One command covers steps 4-7:
```bash
python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/
```
See `docs/DOODLE.md`.
