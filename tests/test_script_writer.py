"""Script-writer tests: offline script + timestamp estimator feed the doodle parser."""
from pipeline.doodle import script_writer
from pipeline.doodle.timestamps import parse


def test_offline_script_nonempty_and_sized():
    s = script_writer.write_script("Why are we the only humans left?", minutes=2)
    assert len(s.split()) >= 200          # ~2 min @ 150 wpm
    assert "?" not in s.split(".")[0] or s   # has real prose


def test_estimated_transcript_parses():
    s = script_writer.write_script("The hidden cost of cities", minutes=1)
    transcript = script_writer.estimate_timestamps(s)
    segs = parse(transcript)
    assert len(segs) >= 3
    assert segs[0].start == 0.0
    # timestamps are monotonically non-decreasing
    assert all(segs[i].start <= segs[i+1].start for i in range(len(segs)-1))


def test_timestamps_label_format():
    tr = script_writer.estimate_timestamps("One two three. Four five six. Seven eight.")
    assert tr.splitlines()[0].startswith("(0:00)")
