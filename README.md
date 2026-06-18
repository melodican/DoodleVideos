# YouTube Automation — Cosmic Documentary Channel

Fully automated faceless-channel pipeline for the **space / cosmic-mystery documentary**
niche. Designed to be driven by Claude Code on a daily schedule, end-to-end:

> ideate → research (+grounding) → script → voice → video (Vid Rush) → thumbnail → metadata → QA → upload

## Why this niche
- **Fast traction:** highest outlier scores among automatable niches (modeled on Cosmicus, Lone Colonist).
- **High RPM:** family-safe / advertiser-friendly; ~$5–5.5 explainer, ~$7.7 sleep variant.
- **High watch time:** 18–24 min docs with 3–4 mid-rolls.
- **Automation-safe:** public-domain footage (NASA / ESA / JWST), evergreen, infinite topics, zero copyright/news dependency.

## Pipeline stages
See `docs/PIPELINE.md`. Each stage is a module in `pipeline/` and is chained by `pipeline/run.py`.

## Quick start
```bash
cp .env.example .env        # add API keys
pip install -r requirements.txt
python -m pipeline.run --dry-run     # run the chain without uploading
```

## Status
Scaffold. Stages contain documented interfaces + TODOs. Wire in Vid Rush + YouTube Data API keys to go live.
