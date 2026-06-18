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
| 5 | Generate images | Higgsfield / GPT Image 2 | external; feed it `image_manifest.json` or `batch_prompt.txt` |
| 6 | Rename images by timestamp | — | name them `M_SS.png` (e.g. `0_07.png`) — matches `Segment.filename` |
| 7 | **Edit images + VO on a timeline** | ~~CapCut (manual)~~ | ✅ **`doodle.run assemble`** does this with ffmpeg — no manual editing |

## Usage
```bash
# Step 4: from the TurboScribe transcript, emit prompts for Higgsfield
python -m pipeline.doodle.run prompts transcript.txt --out output/
#   -> output/image_manifest.json  (one {timestamp, filename, prompt} per image)
#   -> output/batch_prompt.txt     (single paste-in prompt: instructions+style+script)

# Step 7: once images are generated and named 0_00.png, 0_07.png, ...
python -m pipeline.doodle.run assemble transcript.txt images/ vo.mp3 --out output/video.mp4
```

## Consistency
- The locked style block lives in `config/styles/doodle.yaml` and is appended to
  every prompt so all frames share one look.
- Set `style.reference_image` to a saved frame and pass it to Higgsfield for even
  tighter cross-frame consistency.

## Requirements (in your runtime env)
- `ffmpeg` + `ffprobe` on PATH (assembly).
- Higgsfield (image gen), ElevenLabs (VO), TurboScribe (timestamps).
