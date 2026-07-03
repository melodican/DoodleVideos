"""B-roll renderer: pure-logic tests (no network, no ffmpeg)."""
from pipeline.doodle.timestamps import parse
from pipeline.broll import captions, visual_plan, footage, assemble, channel

T = """(0:00) Imagine you and four friends find a desert island with no taxes.
(0:06) Within a week you would invent taxes all over again.
(0:12) The path between the beach and the spring is full of rocks and mud."""


def test_caption_chunks_split_and_timed():
    segs = parse(T)
    chunks = captions.caption_chunks(segs, audio_seconds=18, max_words=4)
    # every chunk has <=4 words and sits inside its segment's time
    assert chunks and all(len(t.split()) <= 4 for _, _, t in chunks)
    assert all(s <= e for s, e, _ in chunks)
    # chunks are ordered in time
    starts = [s for s, _, _ in chunks]
    assert starts == sorted(starts)


def test_ass_time_format():
    assert captions._ass_time(0) == "0:00:00.00"
    assert captions._ass_time(75.5) == "0:01:15.50"
    assert captions._ass_time(3661.25) == "1:01:01.25"


def test_to_ass_writes_styled_file(tmp_path):
    segs = parse(T)
    chunks = captions.caption_chunks(segs, audio_seconds=18)
    out = captions.to_ass(chunks, str(tmp_path / "c.ass"))
    text = open(out).read()
    assert "[V4+ Styles]" in text and "Dialogue:" in text
    assert "ISLAND" in text  # uppercased for punch


def test_keywords_drops_stopwords_and_prefers_concrete():
    q = visual_plan.keywords_for("Within a week you would invent taxes all over again")
    assert "taxes" in q
    assert "would" not in q and "again" not in q


def test_plan_queries_heuristic_one_per_scene():
    segs = parse(T)
    qs = visual_plan.plan_queries(segs, use_claude=False)
    assert len(qs) == len(segs)
    assert all(isinstance(q, str) and q for q in qs)


def test_footage_available_and_pick_file(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert footage.available() is False
    video = {"video_files": [
        {"link": "sd.mp4", "width": 640, "height": 360},
        {"link": "hd.mp4", "width": 1920, "height": 1080},
        {"link": "uhd.mp4", "width": 3840, "height": 2160},
    ]}
    assert footage._pick_file(video) == "hd.mp4"   # closest to 1920 wide
    assert footage._pick_file({"video_files": []}) is None


def test_scene_durations_use_real_times():
    segs = parse(T)
    durs = assemble.scene_durations(segs, audio_seconds=18)
    assert durs[0] == 6.0 and durs[1] == 6.0
    assert durs[-1] == 6.0  # last segment runs to audio end (18 - 12)


def test_caption_png_renders_file(tmp_path):
    out = captions.caption_png("no taxes here", str(tmp_path / "c.png"), style="minimal")
    from PIL import Image
    im = Image.open(out)
    assert im.size == (1920, 1080) and im.mode == "RGBA"


def test_render_options_default_captions_off():
    opts = channel.RenderOptions()
    assert opts.captions == "off" and opts.captions_on is False   # not forced on
    assert channel.RenderOptions(captions="on").captions_on is True


def test_render_options_from_dict_ignores_unknown():
    opts = channel.render_options_from_dict({"captions": "on", "motion": True, "bogus": 1})
    assert opts.captions_on is True and opts.motion is True


def test_load_channel_blueprints():
    # long-form documentary blueprint: captions OFF
    doc = channel.load_channel("rise-and-ruin")
    assert doc.captions_on is False and doc.source == "stock"
    # explainer blueprint: captions ON
    exp = channel.load_channel("what-actually-is")
    assert exp.captions_on is True and exp.source == "images"


def test_scene_overlays_are_local_and_windowed():
    segs = parse(T)  # scene 0 = 0..6, scene 1 = 6..12
    chunks = [(0.0, 3.0, "a.png"), (3.0, 6.0, "b.png"), (7.0, 9.0, "c.png")]
    ov0 = assemble.scene_overlays(segs[0], 6.0, chunks)
    assert [p for _, _, p in ov0] == ["a.png", "b.png"]      # only scene-0 chunks
    assert ov0[0][:2] == (0.0, 3.0)                          # local time
    ov1 = assemble.scene_overlays(segs[1], 6.0, chunks)
    assert [p for _, _, p in ov1] == ["c.png"]
    assert ov1[0][:2] == (1.0, 3.0)                          # 7..9 global -> 1..3 local
