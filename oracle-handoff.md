# Oracle Handoff — Content Factory Renderer (DoodleVideos repo)

**Author:** CFO (renderer / machine-shop lane)
**Repo:** `DoodleVideos` — local `/Users/glenkirkham/yt`, remote `github.com/melodican/DoodleVideos`
**Renderer branch:** `feature/broll-renderer` @ `3695992` (pushed, in sync with origin)
**Tests:** `.venv/bin/python -m pytest tests/` → **43 passing**
**Status:** Renderer lane at **supervised-trial-ready candidate**. Major expansion paused per Oracle.

This document is the full technical state of the renderer so Oracle can reason about it without reading the code. It is the renderer-side source of truth; the code + tests are the receipts.

---

## 1. What this repo is

A faceless-YouTube automation studio. Two independent render engines share a common spine (transcription, timestamps, ffmpeg assembly, ElevenLabs VO, Claude scripting):

1. **Doodle pipeline** (`pipeline/doodle/`) — the original "What Actually Is" style: topic → Claude script → ElevenLabs VO → Whisper transcribe → one hand-drawn AI image per scene → assemble. Mature, live channel.
2. **B-roll / documentary renderer** (`pipeline/broll/`) — **the Content Factory renderer.** The cheap, fully-API alternative to Vidrush: VO + timed transcript → editorial shot list → per-shot stock footage → assemble. This is what Rise & Ruin (RR) would use. **Everything below is about this engine.**

There is also a Flask dashboard (`dashboard/app.py`) for the doodle pipeline (script/VO/thumbnail/YouTube-upload) — not part of the RR renderer lane, but in the repo.

---

## 2. The documentary renderer — architecture

**Data flow (stock/documentary path):**

```
project folder (vo.* + transcript.txt)
  → timed segments            (reuse transcript.txt = free, or Whisper)
  → group into scenes         (group_segments, seconds_per_clip, default 6s)
  → DIRECTOR: one query/beat   (Anthropic API → Claude CLI → heuristic; explicit source)
  → EDITORIAL: shot list       (roles, multi-clip beats, shot-type framing)
  → FOOTAGE: 1 clip per shot   (Pexels re-rank + diversity guards + literal fallback)
  → [captions off for RR]      (PIL PNG overlay when on — no libass needed)
  → ASSEMBLE                    (ffmpeg: normalize each clip to its shot duration,
                                 concat, mux VO) → video_broll.mp4
```

**Modules (`pipeline/broll/`):**

| File | Responsibility |
|---|---|
| `builder.py` | `build_broll(...)` orchestrator. Reuses `transcript.txt` when present (no Whisper cost). |
| `channel.py` | `RenderOptions` + `load_channel()` — per-channel blueprints (captions/motion/source/pacing). |
| `visual_plan.py` | The **director**: `plan_queries()` → (queries, source). API → CLI → heuristic, explicit. |
| `director.py` | **Editorial layer**: `classify_role()`, `build_shots()` → shot list (roles, multi-clip, shot-type). |
| `footage.py` | Pexels search + **re-rank/select** (`select_best`), diversity guards, `fetch()` with literal fallback, placeholder degrade. |
| `captions.py` | Caption chunking + `caption_png()` (PIL) + `to_ass()`. `STYLES` (bold/minimal/lower). |
| `assemble.py` | ffmpeg assembly: image-or-video visuals, optional Ken Burns, caption overlay, concat, VO mux. |
| `run.py` | CLI. Loads `.env`. `--channel`, `--plan`, `--require-director`, `--source`, `--max-scenes`, etc. |

Shared from `pipeline/doodle/`: `transcribe.py` (Whisper), `timestamps.py` (`parse`, `group_segments`, `Segment`), `assemble.audio_duration`.

---

## 3. The director (footage query intelligence)

`visual_plan.plan_queries(scenes, topic, require_director)` returns `(queries, source)` and tries, **in order, reporting which ran**:

1. **`anthropic-api`** — Anthropic Messages API (`ANTHROPIC_API_KEY`). **Works everywhere, including inside nested Claude sessions.** This is the production director path.
2. **`claude-cli`** — Claude Code CLI on the subscription (no API credits). **Cannot run *inside* a Claude Code session** (hence the API path exists).
3. **`heuristic`** — deterministic keyword extractor (`keywords_for`). Offline fallback.

- **No hidden degradation** — the chosen source is returned and logged by the builder.
- **`require_director=True`** makes an LLM director mandatory: raises rather than silently using the heuristic. **RR production must set this.**

The director prompt asks for one concrete, literal, filmable query per beat (avoiding abstract ideas and generic "people looking at camera").

---

## 4. Editorial layer (`director.py`)

Raw per-beat queries give generic, repetitive B-roll. The editorial layer adds:

- **Scene-purpose roles** — `classify_role()` tags each beat: `establishing / process / human / abstract / reveal / transition`. Role drives visual strategy, framing, and whether people are wanted.
- **Multi-clip beats** — enumeration/process beats ("one fishes, one builds, one collects") become 2–3 short shots instead of one repeated long clip. A director plan can supply **curated** sub-queries per beat (`queries: [...]`); otherwise a keyword split is used.
- **Shot-type framing** — `SHOT_TYPES` rotates framings per role (aerial / wide / close-up / macro / drone) so even a repeated subject changes framing.
- **`Shot`** carries `base_query` (unframed literal) for the footage fallback.

Output: a list of `Shot(start, end, text, query, role, allow_people, shot_type, base_query)`. Each shot is fetched and assembled as one scene.

---

## 5. Footage intelligence (`footage.py`)

- **Multi-candidate re-rank** — `select_best()` scores candidates on slug/query overlap + HD-landscape, not "first hit".
- **Generic-people suppression** — penalises stock-people clips unless the beat/role wants people.
- **De-dup** — never reuses the same clip id.
- **Diversity guards** — penalises repeating a recent **concept** (`avoid_slugs`) and a recent **visual object class** (`avoid_classes`). Classes: `document / money / human / institutional / environment / object / symbolic`. Builder keeps rolling windows (last 3 concepts, last 2 classes).
- **Literal-subject fallback** — if the best match for a framed query has **zero** slug overlap, `fetch()` retries the unframed `base_query` and keeps whichever actually matches (kills wrong-subject picks).
- **Graceful degrade** — no key / no result → labelled placeholder card (never breaks a run). `drawtext` label only if the ffmpeg build supports it.

Footage source: **Pexels video API** (free key). Public-domain archival + AI stills are the planned additional lanes (source-router, not yet built).

---

## 6. Captions (`captions.py`) — per-channel, default OFF

- Captions are a **channel-level option, not a universal default.** RR = **off** (clean long-form frame; viewers use YouTube CC).
- When on: narration is split into short chunks; each rendered as a **transparent PIL PNG** and composited with the ffmpeg `overlay` filter. **No libass/freetype needed** — this was required because the local ffmpeg lacks both (see §11).
- `STYLES` = bold / minimal / lower. Frame-accurate to the VO (verified).

---

## 7. Assembly (`assemble.py`)

- Each shot's visual (stock clip **or** still image) is scaled-to-cover + centre-cropped to **1920×1080 / 30fps**, looped/trimmed to the shot's spoken duration, audio stripped.
- Optional **Ken Burns** (zoompan) on stills — **off by default (perf-heavy, see §11).**
- Captions baked per-shot via overlay (when on). Scenes concatenated; VO muxed. `-preset veryfast`.
- Output: `projects/<slug>/video_broll.mp4` (kept separate from the doodle `video.mp4`).

---

## 8. Channel blueprints (`config/channels/*.yaml`)

Per-channel/format render options (`RenderOptions`): `source`, `captions`, `caption_style`, `motion`, `seconds_per_clip`, `require_director`. Defaults have **captions OFF** — nothing forces captions into the render path.

**`config/channels/rise-and-ruin.yaml`:**
```yaml
name: Rise & Ruin
format: long_form_documentary
render:
  source: stock          # real footage per beat (Pexels + archival)
  captions: "off"        # long-form docs read better without burned-in text
  caption_style: bold    # unused while off; kept for A/B
  motion: true           # Ken Burns on any still images
  seconds_per_clip: 6
```
(Also `what-actually-is.yaml` for the doodle-style channel.)

---

## 9. Director plan format (provided-plan path)

An agent/LLM/human director can supply a plan (one entry per grouped scene). Used via `--plan file.json` or `director_plan=` in `build_broll`. Treated as a real director source (`provided-plan (director)`), satisfies `require_director`. Example at **`docs/director-plan.example.json`**:

```json
[
  {"role": "establishing", "query": "tropical island aerial"},
  {"role": "process", "queries": ["man fishing ocean", "building wooden shelter", "gathering firewood forest"]},
  {"role": "reveal", "query": "income tax form"}
]
```
- `query` = single beat query; `queries: [...]` = curated multi-clip beat (2–4 sub-shots).
- `role` = editorial role (drives framing / people / abstract handling).

---

## 10. How to run

```bash
# Rise & Ruin documentary render (real director required):
export ANTHROPIC_API_KEY=...          # or in .env — enables the automated director
python -m pipeline.broll.run build projects/<slug> \
    --channel rise-and-ruin --topic "<topic>" --require-director

# With an explicit director plan (agent-authored):
python -m pipeline.broll.run build projects/<slug> \
    --channel rise-and-ruin --plan docs/director-plan.example.json --require-director

# Short excerpt for review:
... --max-scenes 15
```

**Env vars:** `PEXELS_API_KEY` (footage — in gitignored `.env`), `ANTHROPIC_API_KEY` (automated director), `OPENAI_API_KEY` (Whisper, only if no transcript.txt), `ELEVENLABS_API_KEY` (VO, if generating). `SECONDS_PER_CLIP` default 6. **All keys live only in gitignored `.env` — none committed.**

---

## 11. Environment gotchas (important — these shaped the design)

1. **Local ffmpeg (8.1.2, `/usr/local/bin`) was built WITHOUT libfreetype/libass** → no `drawtext`, no `subtitles` filter. Captions therefore use the PIL→PNG→`overlay` path (no libass). A production box with a full ffmpeg would also work; the PIL path is the portable choice.
2. **zoompan (Ken Burns) is slow** — ~7 min to render ~90s at 2688-wide pre-scale. Motion is **off by default**; a perf pass is deferred (not started).
3. **Claude Code CLI cannot run inside a Claude Code session** — this is why the Anthropic-**API** director path exists and is the production path.

---

## 12. Cost model

- Footage: **free** (Pexels). VO: ElevenLabs (pennies, already existed for test asset). Whisper: skipped when `transcript.txt` exists. Director: ~1 cheap LLM call per video (API) or subscription (CLI).
- **~£0 marginal footage; well under £1/video all-in vs Vidrush ~£17/video (£500/30).** This is the core reason the engine exists — kill the marginal cost so channels can scale speculatively.

---

## 13. What is PROVEN

- Clean broadcast-spec 1080p30 h264+aac output; heterogeneous visuals (stock + stills) through one path; frame-accurate VO sync.
- Captions on/off/style per channel, working on a libass-less ffmpeg.
- Footage re-ranking, generic-people suppression, de-dup, concept + object-class + shot-type diversity, literal-subject fallback.
- Editorial roles, multi-clip beats (curated + heuristic).
- **Director-on output** (via a real director plan): variety lifts materially and intentionally — literal island aerial for the intro, pizza+Monopoly-money for the "paycheck pizza" metaphor, no same-clip/same-class back-to-back.
- Governance: explicit director source, `require_director` gate, keys only in `.env`.

## 14. What is STILL UNPROVEN

- **The *automated* API director run end-to-end here.** The code path exists and works in nested sessions *if a key is set*, but every director-on result to date used a **hand-authored plan** (CFO acting as director stand-in) because no `ANTHROPIC_API_KEY` was available in this environment. Needs one clean automated run.
- **Full automated director-on render** start-to-finish (script → auto-director → footage → MP4).
- **Real Rise & Ruin content** — only tested on the *What Actually Is: Tax* asset with RR render settings; no actual RR script/VO.
- **Performance at long-form length** with motion on.
- **Residual relevance-vs-diversity tension** — the object-class penalty can occasionally deprioritise a genuinely relevant shot (flagged, not fixed; parked per pause). This, not query quality, caused the one "capitol → person" swap in the earlier render.

## 15. Exact conditions for supervised Rise & Ruin use

1. `ANTHROPIC_API_KEY` set in the production/n8n runtime (non-nested) → automated director runs.
2. `require_director: true` in the RR blueprint — no heuristic-only production run.
3. `PEXELS_API_KEY` present in the runtime (in `.env` locally).
4. Real RR script + VO + timed transcript as input (Whisper or supplied).
5. `captions: off`, `source: stock` (already the RR blueprint).
6. **Human review gate** on output — supervised, not autonomous; motion stays off until the perf pass.
7. **One clean automated director-on render reviewed and approved** before first publish (closes the unproven-automated-path item in §14).

---

## 16. Next queue (parked — not started; awaiting Oracle priority)

- Soften class-diversity penalty when a candidate's query-overlap is high (relevance overrides diversity) — fixes the §14 tension.
- Automated director-on smoke render once a key is available.
- Source router: AI stills / public-domain archival as additional lanes (was gated).
- Ken Burns / zoompan performance pass.

## 17. Related branches (context)

Renderer work is on `feature/broll-renderer`. Separate, earlier dashboard features (not RR-renderer): `feature/elevenlabs-dashboard`, `feature/youtube-upload`, `feature/mac-launcher`, `feature/pacing-slider`, `feature/auto-thumbnail`, `feature/reference-style-lock`, and `integration/all-features` (those six merged). `main` is the base.

---

*Receipts: code on `feature/broll-renderer` @ `3695992`; 43 tests passing; keys only in gitignored `.env`.*
