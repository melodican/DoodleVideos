# Setup & first run

> Secrets live only in `.env` (gitignored). Never paste keys into chat or commit them.

## 1. Install
```bash
pip install -r requirements.txt
# ffmpeg + ffprobe on PATH (assembly):
#   Windows: winget install Gyan.FFmpeg
#   macOS:   brew install ffmpeg
cp .env.example .env
```

## 2. Keys (`.env`)
| Var | Unlocks | Without it |
|-----|---------|------------|
| `ANTHROPIC_API_KEY` (+ `LLM_MODEL=claude-sonnet-4-6`) | script (step 1) | offline draft |
| `OPENAI_API_KEY` (+ `IMAGE_GEN_MODEL`, `IMAGE_QUALITY`, `IMAGE_SIZE`) | images (5-6) | manual Higgsfield checkpoint |
| `ELEVENLABS_API_KEY` (+ `ELEVENLABS_VOICE_ID`) | voiceover (step 2) | VO skipped (use `--audio`) |

Cost control: keep `IMAGE_QUALITY=low` while iterating (cheapest), switch to `high`
only for videos you'll publish. Images are the main cost driver, not scripts.

## 3. First video (cheap test first)
```bash
# ~1 min => ~10-12 frames, low quality => a few cents to test wiring:
python -m pipeline.doodle.run make "Why do cities never sleep?" --minutes 1 --out output/
# full run:
python -m pipeline.doodle.run make "Why are we the only human species left?" --minutes 6 --out output/
```

## Network note (cloud sessions only)
Running locally has no restrictions. Inside a Claude Code **cloud** session, add
`api.openai.com` and `api.elevenlabs.io` to the environment's egress allowlist,
or those stages will 403. (`api.anthropic.com` is already allowed.)

## Not yet automated
- YouTube upload (step 9) — produces `video.mp4`; publishing is a stub.
- Timestamps are estimated from word count; for tight sync use real TurboScribe output with `auto`.
