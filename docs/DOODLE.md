# Doodle (MS-Paint explainer) pipeline — the Axen / Ink Explainer style

Why: this niche has the fastest traction we found (Axen ~$13k/mo on 9 videos).
The hand-drawn look is the moat. This pipeline makes it reproducible and aims at
full autonomy.

## Your 7 steps → what's automated here

| # | Step | Tool | Status in this repo |
|---|------|------|---------------------|
| 1 | Script | LLM | ✅ `doodle.run script "<topic>"` (Anthropic API, else offline draft) |
| 2 | Voiceover | ElevenLabs | ✅ auto via `ELEVENLABS_API_KEY`, else `--audio vo.mp3` |
| 3 | Transcript w/ timestamps | TurboScribe | export to `transcript.txt`, **or** estimated automatically |
| 4 | One image prompt per timestamp | — | ✅ `doodle.run prompts` builds them (locked style) |
| 5 | Generate images | Higgsfield / GPT Image 2 | ✅ auto via `OPENAI_API_KEY`, else manual checkpoint |
| 6 | Rename images by timestamp | — | ✅ `--images-in` maps a downloaded folder by order → `M_SS.png` |
| 7 | **Edit images + VO on a timeline** | ~~CapCut (manual)~~ | ✅ **assembled with ffmpeg** — no manual editing |

## Recommended workflow: bring-your-own script + VO (true sync)

Each video lives in its own folder under `projects/`. Write the script (e.g. in
n8n), generate the ElevenLabs voiceover, drop the audio in, and build:

```bash
mkdir -p projects/why-cities-never-sleep
# put your ElevenLabs audio there as vo.mp3 (script.txt optional, for your records)
python -m pipeline.doodle.run build projects/why-cities-never-sleep
open projects/why-cities-never-sleep/video.mp4
```

`build` transcribes the VO with Whisper (real per-line timestamps), generates one
doodle per line, and assembles a **frame-synced** 16:9 video — everything stays in
that project folder. Needs `OPENAI_API_KEY` (transcription + images). No image key?
It stops at the manual checkpoint; resume with `--images-in <folder>`.

## Usage

### Whole loop from a topic (steps 1→7)
```bash
python -m pipeline.doodle.run make "Why are we the only human species left?" \
    --minutes 6 --out output/
```
Chains script → VO → estimated timestamps → prompts → images → assemble. Each
external stage gracefully degrades when its key is missing:
- no `ANTHROPIC_API_KEY` → offline script draft
- no `ELEVENLABS_API_KEY` → VO skipped (pass `--audio vo.mp3`, or set the key)
- no image key → stops at the manual checkpoint; resume with `--images-in <folder>`

With all keys set (and `ffmpeg` on PATH) it runs topic → finished `video.mp4`
unattended.

### Step 1: topic → doodle script
```bash
python -m pipeline.doodle.run script "Why are we the only human species left?" \
    --minutes 6 --timestamps --out output/
#   -> output/script.txt       (narration; Axen/Ink voice)
#   -> output/transcript.txt    (estimated timestamps — feeds steps 4-7 directly)
```
Uses the Anthropic API when `ANTHROPIC_API_KEY` is set; otherwise writes a styled
offline draft so the loop still runs. `--timestamps` estimates timing from word
count (≈150 wpm) so you can run the whole 1→7 loop without TurboScribe — for
frame-tight sync, generate the VO and use real TurboScribe output instead.

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
