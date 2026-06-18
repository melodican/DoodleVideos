# Doodle (MS-Paint explainer) pipeline — the Axen / Ink Explainer style

Why: this niche has the fastest traction we found (Axen ~$13k/mo on 9 videos).
The hand-drawn look is the moat. This pipeline makes it reproducible and aims at
full autonomy.

## Your 7 steps → what's automated here

| # | Step | Tool | Status in this repo |
|---|------|------|---------------------|
| 1 | Script | LLM | use `pipeline/script.py` (or paste your own) |
| 2 | Voiceover | ElevenLabs | external (your env); save as `vo.mp3` |
| 3 | Transcript w/ timestamps | TurboScribe | export to `transcript.txt` |
| 4 | One image prompt per timestamp | — | ✅ `doodle.run prompts` builds them (locked style) |
| 5 | Generate images | Higgsfield / GPT Image 2 | ✅ auto via `OPENAI_API_KEY`, else manual checkpoint |
| 6 | Rename images by timestamp | — | ✅ `--images-in` maps a downloaded folder by order → `M_SS.png` |
| 7 | **Edit images + VO on a timeline** | ~~CapCut (manual)~~ | ✅ **assembled with ffmpeg** — no manual editing |

## Usage

### One command (steps 4→7)
```bash
python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/
```
- **With an image API key** (`OPENAI_API_KEY` / `IMAGE_GEN_API_KEY`): generates every
  frame, then assembles `output/video.mp4`. Fully autonomous.
- **Without a key**: writes the prompts and stops at a **manual checkpoint** (exit 2).
  Generate the images in Higgsfield, download the folder, then resume:
  ```bash
  python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/ --images-in raw_images/
  ```
  `--images-in` maps the downloaded images onto timestamp filenames **in order**
  (generation order == script order) and fails loudly on a count mismatch.

### Individual stages
```bash
python -m pipeline.doodle.run prompts   transcript.txt --out output/
python -m pipeline.doodle.run assemble  transcript.txt images/ vo.mp3 --out output/video.mp4
```

## Consistency
- The locked style block lives in `config/styles/doodle.yaml` and is appended to
  every prompt so all frames share one look.
- Set `style.reference_image` to a saved frame and pass it to Higgsfield for even
  tighter cross-frame consistency.

## Requirements (in your runtime env)
- `ffmpeg` + `ffprobe` on PATH (assembly).
- Higgsfield (image gen), ElevenLabs (VO), TurboScribe (timestamps).
