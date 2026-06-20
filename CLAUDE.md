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
- `pipeline/doodle/voiceover.py` — ElevenLabs TTS, wired into the dashboard ("Generate
  voiceover"); auto-chunks long scripts under the 5k-char limit. `synthesize`, `available`.
- `pipeline/doodle/thumbnail.py` — PIL: compose a 1280x720 thumbnail from a doodle frame +
  bold title (free, no image API). `make_thumbnail`.
- `pipeline/doodle/youtube_upload.py` — YouTube Data API v3 upload + OAuth (Desktop-app,
  cached token). `upload`, `get_credentials`, `configured`. Setup: `docs/youtube-setup.md`.
- `pipeline/doodle/run.py` — CLI: `make` (topic→video), `build <projdir>`, `script`,
  `prompts`, `assemble`, `auto`.

## Dashboard (`dashboard/app.py`, Flask)
Launch: **double-click `Start Doodle Studio.command`** (Finder) — it spins up the venv
(installing deps on first run), starts Flask, and opens the browser. Or run
`python -m dashboard.app` → http://localhost:8000 (port 8000 default; **5000 clashes with
macOS AirPlay**). On startup it loads `.env` automatically (python-dotenv).

Builder flow (one page): "Write with Claude" (free script) → "Generate description + tags"
(free) → **pace slider** (per-build `SECONDS_PER_IMAGE`, live cost estimate) → **"Generate
voiceover"** (ElevenLabs, shown when `ELEVENLABS_API_KEY` set; or upload your own VO) →
optional **style-reference** image upload → Generate Video with live progress → download MP4.
Project detail view adds: **auto-thumbnail** (PIL compose from a doodle frame + bold title,
free) and **"Publish to YouTube"** (title/desc/tags/privacy → YouTube Data API).

Key endpoints: `/build`, `/voiceover`, `/thumbnail/<name>` + `/thumb/<name>`,
`/publish/<name>` + `/save_meta/<name>`, `/config`, `/project/<name>`. Per-project
metadata persists to `projects/<slug>/metadata.json`.

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
- `ELEVENLABS_API_KEY` (+ `ELEVENLABS_VOICE_ID`) — VO now generated **in the dashboard**
  ("Generate voiceover"); long scripts are auto-chunked under EL's 5k-char limit.
- Scripts/metadata use the **Claude Code subscription** (no key needed; key is stripped).
- YouTube upload: OAuth **Desktop-app** `client_secret.json` in repo root → token cached in
  `yt_token.json` (both gitignored). First-time setup walkthrough: `docs/youtube-setup.md`.
  Env knobs `YT_CLIENT_SECRETS` / `YT_TOKEN_STORE`.
- `IMAGE_QUALITY` (low|medium|high; medium is the good default), `SECONDS_PER_IMAGE` (4;
  also a per-build slider in the UI), `IMAGE_CONCURRENCY` (5), `IMAGE_GEN_MODEL`
  (gpt-image-1), `PORT` (8000).
- Each video = a folder under `projects/<slug>/` (vo.*, script.txt, transcript.txt,
  images/, video.mp4, plus thumbnail.png / metadata.json / reference.png when used).
  `projects/` and `*.bundle` are gitignored.

## Environment notes (user is on macOS, Python 3.14)
- Use a venv; `python3`. python.org Python needs `Install Certificates.command` for SSL.
- Doodle pipeline core: `pyyaml requests python-dotenv flask`. The dashboard's newer
  features also need `pillow` (thumbnails) and `google-api-python-client` +
  `google-auth-oauthlib` + `google-auth-httplib2` (YouTube upload) — all in
  `requirements.txt`; `pip install -r requirements.txt` (the `.command` does this on first run).
- Tests: `python -m pytest tests/` (35 passing). Commit messages end with the
  Co-Authored-By / Claude-Session trailers.

## Done
Niche research (NexLev), space + doodle pipelines, real-sync via Whisper, dashboard
(library, script/metadata gen, cost estimate, dark UI), parallel image gen, scene grouping,
finance niche config (`config/niches/finance.yaml`), channel live: @WhatActuallyIs-o3r
(videos: tax, inflation, space). **Latest batch (branch `integration/all-features`, 6 features):**
ElevenLabs VO in the dashboard; one-click YouTube upload (`youtube_upload.py` + OAuth);
`Start Doodle Studio.command` Mac launcher; per-project pace slider; auto-thumbnails
(`thumbnail.py`, PIL); reference-image style lock (`images.generate(reference_path=...)`
via the OpenAI edits endpoint).

## Next / backlog
- Merge `integration/all-features` → `main` (or the 6 `feature/*` branches individually).
- Channel-growth ideas: batch/scheduled rendering, A/B thumbnails, auto-upload on render,
  multi-channel support. (All three original backlog items are now shipped.)
