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
    assert segs[1].filename == "001.png"


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
    # real-timestamp sync: each image holds from its start to the next one's
    durs = compute_durations(segs, 80.0, sync="timestamps")
    assert durs[0] == ("000.png", 7)
    assert durs[-1][1] == 18.0  # 80 - 62
    # proportional sync fills (about) the whole audio by word count
    pro = compute_durations(segs, 80.0, sync="proportional")
    assert abs(sum(d for _, d in pro) - 80.0) < 0.5
    concat = build_concat_file(durs, "imgs")
    assert concat.count("file '") == len(durs) + 1  # last-file repeat
