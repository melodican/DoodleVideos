"""B-roll renderer: pure-logic tests (no network, no ffmpeg)."""
from pipeline.doodle.timestamps import parse
from pipeline.broll import captions, visual_plan, footage, assemble, channel, director

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


def test_plan_queries_reports_source_and_falls_back(monkeypatch):
    # no API key + CLI unavailable -> explicit heuristic source, not a silent fallback
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(visual_plan.script_writer, "claude_code_available", lambda: False)
    segs = parse(T)
    qs, source = visual_plan.plan_queries(segs)
    assert len(qs) == len(segs) and all(qs)
    assert source.startswith("heuristic")            # explicit about what ran


def test_require_director_raises_instead_of_degrading(monkeypatch):
    import pytest
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(visual_plan.script_writer, "claude_code_available", lambda: False)
    with pytest.raises(RuntimeError):
        visual_plan.plan_queries(parse(T), require_director=True)


def test_keywords_topic_fallback_on_abstract_lines():
    # an abstract line yields no concrete noun -> lean on the topic, not generic words
    q = visual_plan.keywords_for("the concept is basically identical", topic="tax")
    assert "tax" in q


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


def test_footage_reranks_and_penalises_generic_people():
    island = {"id": 1, "url": "https://www.pexels.com/video/aerial-desert-island-1/",
              "width": 1920, "height": 1080, "duration": 10,
              "video_files": [{"link": "a.mp4", "width": 1920, "height": 1080}]}
    people = {"id": 2, "url": "https://www.pexels.com/video/man-woman-looking-studio-2/",
              "width": 1920, "height": 1080, "duration": 10,
              "video_files": [{"link": "b.mp4", "width": 1920, "height": 1080}]}
    best = footage.select_best([people, island], "desert island")
    assert best["id"] == 1                          # slug-match beats generic people
    # de-dup: once seen, the next best is returned
    seen = {1}
    assert footage.select_best([people, island], "desert island", seen)["id"] == 2


def test_footage_score_people_ok_when_query_wants_people():
    people = {"id": 3, "url": "https://www.pexels.com/video/crowd-of-people-city-3/",
              "width": 1920, "height": 1080, "duration": 8, "video_files": []}
    # query about people should NOT be penalised for a people slug
    assert footage._score(people, {"crowd", "people"}) > 0
    # allow_people also lifts the penalty even without people query words
    assert footage._score(people, {"office"}, allow_people=True) > \
           footage._score(people, {"office"}, allow_people=False)


def test_footage_avoid_penalises_concept_repetition():
    v = {"id": 9, "url": "https://www.pexels.com/video/tax-form-desk-9/",
         "width": 1920, "height": 1080, "duration": 8, "video_files": []}
    base = footage._score(v, {"tax", "form"})
    repeated = footage._score(v, {"tax", "form"}, avoid=frozenset({"tax", "form", "desk"}))
    assert repeated < base                            # same concept as prev shot is penalised


# --- editorial director layer -------------------------------------------------
def test_classify_role():
    assert director.classify_role("Imagine you find a desert island", 0, 5) == "establishing"
    assert director.classify_role("One person fishes, one builds, one collects wood", 2, 5) == "process"
    assert director.classify_role("The concept is basically identical", 3, 5) == "abstract"
    assert director.classify_role("Here's the weird part about it", 1, 5) == "reveal"


def test_build_shots_splits_enumeration_beats():
    segs = parse("(0:00) Imagine a small island community.\n"
                 "(0:06) One person fishes, one person builds shelters, one collects firewood.\n"
                 "(0:18) The concept is basically identical everywhere.")
    shots = director.build_shots(segs, ["island", "fishing island", "tax money"],
                                 audio_seconds=26, topic="tax")
    # the enumeration beat became multiple shots (multi-clip); total > scene count
    assert len(shots) > len(segs)
    roles = {s.role for s in shots}
    assert "process" in roles and "abstract" in roles
    # abstract beat avoids generic literal query, uses a concept visual (no "people")
    ab = [s for s in shots if s.role == "abstract"][0]
    assert ab.allow_people is False and ab.query in director.ABSTRACT_VISUALS


def test_build_shots_no_identical_query_back_to_back():
    segs = parse("(0:00) money one.\n(0:05) money two.\n(0:10) money three.")
    shots = director.build_shots(segs, ["money", "money", "money"], audio_seconds=15, topic="tax")
    qs = [s.query for s in shots]
    assert all(a != b for a, b in zip(qs, qs[1:]))    # no repeat adjacent


def test_footage_classify_class_and_diversity_penalty():
    assert footage.classify_class({"tax", "form"}) == "document"
    assert footage.classify_class({"aerial", "city", "skyline"}) == "institutional"
    assert footage.classify_class({"desert", "island"}) == "environment"
    v = {"id": 5, "url": "https://www.pexels.com/video/tax-form-desk-5/",
         "width": 1920, "height": 1080, "duration": 8, "video_files": []}
    base = footage._score(v, {"tax"})
    penalised = footage._score(v, {"tax"}, avoid_classes=frozenset({"document"}))
    assert penalised < base                           # same object class as recent -> penalised


def test_build_shots_varies_shot_type_and_takes_role_override():
    segs = parse("(0:00) one.\n(0:06) two.\n(0:12) three.")
    # force all establishing via role override -> framing should rotate (aerial/wide/drone)
    shots = director.build_shots(segs, ["city", "city", "city"], audio_seconds=18,
                                 roles=["establishing", "establishing", "establishing"])
    assert all(s.role == "establishing" for s in shots)
    assert len({s.shot_type for s in shots}) > 1       # shot-type varies across shots


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
