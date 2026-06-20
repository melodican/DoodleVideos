# CLAUDE.md — project handoff & context

Read this first. It captures everything a fresh session needs to continue work.

## What this is
A **faceless YouTube automation** studio. The active channel is **"What Actually Is"**
— finance/money explainers in an **"explain like you're five" hand-drawn doodle** style
(modeled on viral channels like Zenn / Crayon Capital). Goal: produce videos cheaply and
mostly automatically so the owner can build a portfolio of channels.

There is also an earlier **space/cosmic documentary** pipeline (`pipeline/run.py`,
`config/channel.yaml`) — kept, but the doodle pipeline is the one in active use.

## The doodle pipeline (the important part)
Flow: **topic → script (Claude) → ElevenLabs voiceover → transcribe → one doodle image
per scene → assemble synced 16:9 MP4.**

- `pipeline/doodle/builder.py` — `build_project(project_dir, audio_path, progress=...)`:
  transcribe VO (Whisper) → group into scenes → generate images → assemble. Reusable by
  CLI and dashboard. Reports progress via callback.
- `pipeline/doodle/transcribe.py` — OpenAI Whisper (`whisper-1`, verbose_json) → real
  per-segment timestamps. This is what gives **exact image↔voice sync**.
- `pipeline/doodle/timestamps.py` — `Segment`, `parse()`, `group_segments(min_seconds)`.
  Image filenames are index-based (`000.png`).
- `pipeline/doodle/image_prompts.py` — `scene_line()` + the locked style block from
  `config/styles/doodle.yaml`, combined per scene. Also a batch prompt for manual Higgsfield.
- `pipeline/doodle/images.py` — OpenAI GPT-Image (`gpt-image-1`). Parallel generation
  (`IMAGE_CONCURRENCY`, default 5). Honors `IMAGE_QUALITY`, `IMAGE_SIZE`. `rename_by_order()`
  supports the manual Higgsfield route (`--images-in`).
- `pipeline/doodle/assemble.py` — ffmpeg: scale-to-fill + center-crop to 1920x1080 (no
  bars), `-nostdin` (don't eat terminal input), absolute concat paths. `sync="timestamps"`
  uses real times; `"proportional"` is the estimate fallback.
- `pipeline/doodle/script_writer.py` — script + metadata generation via the **Claude Code
  CLI** (`claude -p`) with `ANTHROPIC_API_KEY` stripped from the env so it uses the user's
  **subscription, not API credits**. `generate_via_claude_code`, `generate_metadata_via_claude_code`.
- `pipeline/doodle/voiceover.py` — ElevenLabs TTS (not yet wired into the dashboard).
- `pipeline/doodle/run.py` — CLI: `make` (topic→video), `build <projdir>`, `script`,
  `prompts`, `assemble`, `auto`.

## Dashboard (`dashboard/app.py`, Flask)
`python -m dashboard.app` → http://localhost:8000 (port 8000 default; **5000 clashes with
macOS AirPlay**). Features: sidebar project library + detail view; "Write with Claude"
(free script), "Generate description + tags" (free), upload VO → Generate Video with live
progress, live cost estimate (browser reads audio length), download MP4.

## Style learnings (hard-won — keep these)
- **Rough, imperfect hand-drawn marker look** — wobbly lines that overshoot, wonky shapes.
  Explicitly **NOT clipart / icon / vector / symmetrical** (GPT-Image drifts clean).
- **ONE main subject per frame**, big and centered (viral channels do this). If the scene
  text has several ideas, draw only the most important. Avoid cluttered collages.
- **Colour is required** (a few bold flat marker colours) — "optional" made frames B&W.
- A little detail/personality is good; don't lose the rough style.
- Pacing via `SECONDS_PER_IMAGE` (default 4 = frequent changes). All style lives in
  `config/styles/doodle.yaml` + `image_prompts.scene_line()`.
- Next style lever if needed: a **reference image** fed to the generator to lock a
  consistent hand for the whole video.

## Config / env (set in user's shell or `.env`)
- `OPENAI_API_KEY` — transcription + images (both!). User runs low on this; watch cost.
- `ELEVENLABS_API_KEY` (+ `ELEVENLABS_VOICE_ID`) — VO (currently done manually via EL web app).
- Scripts/metadata use the **Claude Code subscription** (no key needed; key is stripped).
- `IMAGE_QUALITY` (low|medium|high; medium is the good default), `SECONDS_PER_IMAGE` (4),
  `IMAGE_CONCURRENCY` (5), `IMAGE_GEN_MODEL` (gpt-image-1), `PORT` (8000).
- Each video = a folder under `projects/<slug>/` (vo.*, script.txt, transcript.txt,
  images/, video.mp4). `projects/` and `*.bundle` are gitignored.

## Environment notes (user is on macOS, Python 3.14)
- Use a venv; `python3`. python.org Python needs `Install Certificates.command` for SSL.
- Heavy deps (google/cryptography) aren't needed for the doodle pipeline — core is
  `pyyaml requests python-dotenv flask`.
- Tests: `python -m pytest tests/` (18 passing). Commit messages end with the
  Co-Authored-By / Claude-Session trailers.

## Done
Niche research (NexLev), space + doodle pipelines, real-sync via Whisper, dashboard
(library, script/metadata gen, cost estimate, dark UI), parallel image gen, scene grouping,
finance niche config (`config/niches/finance.yaml`), channel live: @WhatActuallyIs-o3r
(videos: tax, inflation, space).

## Next / backlog
1. **ElevenLabs in the dashboard** — generate the VO from the script (remove the manual EL hop).
2. **One-click YouTube upload** — publish from the project detail view (YouTube Data API).
3. Optional: per-project `SECONDS_PER_IMAGE` slider; auto-thumbnail; reference-image style lock.
