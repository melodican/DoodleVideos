"""B-roll renderer: pure-logic tests (no network, no ffmpeg)."""
from pipeline.doodle.timestamps import parse
from pipeline.broll import captions, visual_plan, footage, assemble

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
