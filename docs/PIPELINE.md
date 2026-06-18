# Pipeline architecture

Daily cron (or Claude Code schedule) invokes `python -m pipeline.run`.

| # | Stage | Module | Output |
|---|-------|--------|--------|
| 1 | Ideate | `ideate.py` | title + topic |
| 2 | Research (grounding) | `research.py` | sources: claim → citation |
| 3 | Script | `script.py` | 18–24 min narration |
| 4 | Voice | `voice.py` | narration audio |
| 5 | Video (Vid Rush) | `video.py` | rendered mp4 |
| 6 | Thumbnail | `thumbnail.py` | 2 variants |
| 7 | Metadata | `metadata.py` | description, tags, chapters |
| 8 | QA gate | `qa.py` | pass/hold |
| 9 | Upload | `upload.py` | published / scheduled video |

## Guardrails
1. **Grounding (stage 2):** sensational titles, factually-defensible scripts. Every claim cites a real source.
2. **QA gate (stage 8):** fact-coverage + monetization-policy + footage-licence scan. Human-in-loop for first ~20 videos, then hands-off.

## Roadmap
- Channel #2: space-*sleep* variant (RPM ~7.7, 2-hr runtime) reusing stages 2 & footage library.
