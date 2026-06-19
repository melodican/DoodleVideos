from pipeline.doodle.timestamps import parse, to_seconds
from pipeline.doodle.image_prompts import per_segment_prompts, batch_prompt
from pipeline.doodle.assemble import compute_durations, build_concat_file

T = """(0:00) awake in bed
0:07 farms pyramids cities
[1:02] hour-ish mark
0:20 - night not downtime"""


def test_parse_sorts_and_links():
    segs = parse(T)
    assert [s.label for s in segs] == ["0:00", "0:07", "0:20", "1:02"]
    assert segs[0].end == 7 and segs[-1].end is None
    assert segs[1].filename == "0_07.png"


def test_to_seconds_hms():
    assert to_seconds("1:02") == 62
    assert to_seconds("1:00:05") == 3605


def test_prompts_one_per_segment_with_style():
    segs = parse(T); ps = per_segment_prompts(segs)
    assert len(ps) == len(segs)
    assert "MS-Paint" in ps[0]["prompt"] or "MS Paint" in ps[0]["prompt"]
    assert ps[0]["aspect_ratio"] == "16:9"


def test_durations_and_concat():
    segs = parse(T)
    durs = compute_durations(segs, audio_seconds=80.0)
    assert durs[0][0] == "0_00.png"
    # word-proportional distribution fills (about) the whole audio
    assert abs(sum(d for _, d in durs) - 80.0) < 0.5
    # the shortest line ("hour-ish mark", 2 words) gets the least screen time
    assert durs[-1][1] == min(d for _, d in durs)
    concat = build_concat_file(durs, "imgs")
    assert concat.count("file '") == len(durs) + 1  # last-file repeat
