"""Doodle pipeline CLI — covers steps 1-7 of the doodle workflow.

  # WHOLE LOOP from a topic (steps 1->7): script -> VO -> timestamps -> prompts -> images -> assemble
  python -m pipeline.doodle.run make "Why are we the only human species left?" --minutes 6 --out output/

  # One command for steps 4->7 (you already have transcript + VO):
  python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/
      # if no image API key: writes prompts and stops at a manual checkpoint.
  python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/ --images-in raw/

  # Or run a single stage:
  python -m pipeline.doodle.run script "<topic>" --minutes 6 --timestamps --out output/
  python -m pipeline.doodle.run prompts transcript.txt --out output/
  python -m pipeline.doodle.run assemble transcript.txt images/ vo.mp3 --out output/video.mp4
"""
from __future__ import annotations
import argparse, pathlib, sys
from .timestamps import parse
from .image_prompts import write_manifest, batch_prompt, per_segment_prompts
from . import assemble, images, script_writer, voiceover, transcribe


def _emit_prompts(segs, out: pathlib.Path):
    out.mkdir(parents=True, exist_ok=True)
    manifest = write_manifest(segs, str(out / "image_manifest.json"))
    (out / "batch_prompt.txt").write_text(batch_prompt(segs), encoding="utf-8")
    return manifest


def cmd_prompts(args):
    segs = parse(pathlib.Path(args.transcript).read_text(encoding="utf-8"))
    out = pathlib.Path(args.out)
    manifest = _emit_prompts(segs, out)
    print(f"{len(segs)} segments")
    print(f"manifest:     {manifest}")
    print(f"batch prompt: {out / 'batch_prompt.txt'}")


def cmd_assemble(args):
    segs = parse(pathlib.Path(args.transcript).read_text(encoding="utf-8"))
    out = assemble.render(segs, args.images, args.audio, out_path=args.out,
                          audio_seconds=args.audio_seconds, sync=args.sync)
    print(f"rendered: {out}")


def cmd_build(args):
    """Project workflow: a folder with vo.mp3 -> transcribe -> images -> synced video."""
    proj = pathlib.Path(args.project); proj.mkdir(parents=True, exist_ok=True)
    vo = pathlib.Path(args.audio) if args.audio else None
    if vo is None:
        cands = (sorted(proj.glob("vo.*")) + sorted(proj.glob("*.mp3"))
                 + sorted(proj.glob("*.wav")) + sorted(proj.glob("*.m4a")))
        if not cands:
            print(f"[!] no voiceover found in {proj} (expected vo.mp3)"); sys.exit(2)
        vo = cands[0]
    print(f"[1/4] transcribing {vo.name} for real timestamps...")
    segs = transcribe.transcribe(str(vo))
    (proj / "transcript.txt").write_text(transcribe.to_transcript_text(segs), encoding="utf-8")
    _emit_prompts(segs, proj)
    print(f"[2/4] {len(segs)} segments -> transcript + prompts")
    images_dir = proj / "images"
    print("[3/4] images:")
    _fill_images(segs, proj, images_dir, args.images_in)
    video = assemble.render(segs, str(images_dir), str(vo),
                            out_path=str(proj / "video.mp4"), sync="timestamps")
    print(f"[4/4] rendered: {video}")


def cmd_script(args):
    text = script_writer.write_script(args.topic, minutes=args.minutes)
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    script_path = out / "script.txt"
    script_path.write_text(text, encoding="utf-8")
    mode = "LLM" if script_writer.available() else "offline-fallback"
    print(f"[script:{mode}] {len(text.split())} words -> {script_path}")
    if args.timestamps:
        tr = out / "transcript.txt"
        tr.write_text(script_writer.estimate_timestamps(text), encoding="utf-8")
        print(f"[timestamps] estimated transcript -> {tr}")
        print("  note: estimated timing; for tight sync use real TurboScribe output.")


def cmd_auto(args):
    segs = parse(pathlib.Path(args.transcript).read_text(encoding="utf-8"))
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    images_dir = out / "images"
    _emit_prompts(segs, out)
    print(f"[1/3] {len(segs)} segments -> prompts in {out}")

    # Step 5-6: fill the images folder by timestamp
    if args.images_in:                                   # user generated externally
        mapping = images.rename_by_order(args.images_in, segs, str(images_dir))
        print(f"[2/3] mapped {len(mapping)} images by timestamp -> {images_dir}")
    elif images.available():                             # generate via API
        made = images.generate(per_segment_prompts(segs), str(images_dir))
        print(f"[2/3] generated {len(made)} images -> {images_dir}")
    else:                                                # manual checkpoint
        print(f"[2/3] no image API key set — MANUAL CHECKPOINT:")
        print(f"      1) paste {out/'batch_prompt.txt'} into Claude Code (Higgsfield/GPT-Image-2)")
        print(f"      2) download the generated images into a folder")
        print(f"      3) re-run with:  --images-in <that_folder>")
        sys.exit(2)

    miss = images.missing(segs, str(images_dir))
    if miss:
        print(f"[!] missing {len(miss)} timestamp images: {miss[:5]}{'...' if len(miss)>5 else ''}")
        sys.exit(3)

    # Step 7: assemble (replaces manual CapCut edit)
    video = assemble.render(segs, str(images_dir), args.audio,
                            out_path=str(out / "video.mp4"),
                            audio_seconds=args.audio_seconds, sync="proportional")
    print(f"[3/3] rendered: {video}")


def _fill_images(segs, out: pathlib.Path, images_dir: pathlib.Path, images_in):
    """Steps 5-6: fill images_dir by timestamp. Returns True if complete,
    or exits at the manual checkpoint when no source/key is available."""
    if images_in:
        n = len(images.rename_by_order(images_in, segs, str(images_dir)))
        print(f"      mapped {n} images by timestamp -> {images_dir}")
    elif images.available():
        n = len(images.generate(per_segment_prompts(segs), str(images_dir)))
        print(f"      generated {n} images -> {images_dir}")
    else:
        print("      no image API key — MANUAL CHECKPOINT:")
        print(f"        1) paste {out/'batch_prompt.txt'} into Claude Code (Higgsfield/GPT-Image-2)")
        print(f"        2) download the images into a folder")
        print("        3) re-run this command adding:  --images-in <that_folder>")
        sys.exit(2)
    miss = images.missing(segs, str(images_dir))
    if miss:
        print(f"[!] missing {len(miss)} timestamp images: {miss[:5]}{'...' if len(miss)>5 else ''}")
        sys.exit(3)
    return True


def cmd_make(args):
    """Steps 1->7 from a topic."""
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)

    # [1] script
    text = script_writer.write_script(args.topic, minutes=args.minutes)
    (out / "script.txt").write_text(text, encoding="utf-8")
    smode = "LLM" if script_writer.available() else "offline"
    print(f"[1/6] script ({smode}): {len(text.split())} words -> {out/'script.txt'}")

    # [2] voiceover
    audio = args.audio
    if audio:
        print(f"[2/6] VO: using provided {audio}")
    elif voiceover.available():
        audio = voiceover.synthesize(text, str(out / "vo.mp3"))
        print(f"[2/6] VO: synthesized -> {audio}")
    else:
        print("[2/6] VO: skipped (no ELEVENLABS_API_KEY / TTS_API_KEY)")

    # [3] timestamps (estimated from the script)
    transcript = script_writer.estimate_timestamps(text)
    (out / "transcript.txt").write_text(transcript, encoding="utf-8")
    segs = parse(transcript)
    print(f"[3/6] timestamps: {len(segs)} segments -> {out/'transcript.txt'} (estimated)")

    # [4] prompts
    _emit_prompts(segs, out)
    print(f"[4/6] prompts -> {out/'batch_prompt.txt'}, {out/'image_manifest.json'}")

    # [5-6] images
    print("[5/6] images:")
    _fill_images(segs, out, out / "images", args.images_in)

    # [7] assemble
    if not audio:
        print("[6/6] assemble: skipped — no VO. Set ELEVENLABS_API_KEY or pass --audio, "
              "then re-run (images are cached).")
        sys.exit(2)
    video = assemble.render(segs, str(out / "images"), audio,
                            out_path=str(out / "video.mp4"), sync="proportional")
    print(f"[6/6] rendered: {video}")


def main():
    ap = argparse.ArgumentParser(description="Doodle explainer pipeline (steps 1-7)")
    sub = ap.add_subparsers(required=True)

    mk = sub.add_parser("make", help="whole loop from a topic (steps 1->7)")
    mk.add_argument("topic")
    mk.add_argument("--minutes", type=float, default=6)
    mk.add_argument("--out", default="output")
    mk.add_argument("--images-in", default=None,
                    help="folder of externally-generated images (mapped by order)")
    mk.add_argument("--audio", default=None, help="use an existing VO file instead of ElevenLabs")
    mk.set_defaults(func=cmd_make)

    s = sub.add_parser("script", help="topic -> doodle narration (LLM or offline)")
    s.add_argument("topic")
    s.add_argument("--minutes", type=float, default=6)
    s.add_argument("--out", default="output")
    s.add_argument("--timestamps", action="store_true",
                   help="also write an estimated TurboScribe-shaped transcript.txt")
    s.set_defaults(func=cmd_script)

    p = sub.add_parser("prompts"); p.add_argument("transcript")
    p.add_argument("--out", default="output"); p.set_defaults(func=cmd_prompts)

    a = sub.add_parser("assemble"); a.add_argument("transcript")
    a.add_argument("images"); a.add_argument("audio")
    a.add_argument("--out", default="output/video.mp4")
    a.add_argument("--audio-seconds", type=float, default=None)
    a.add_argument("--sync", choices=["timestamps", "proportional"], default="timestamps")
    a.set_defaults(func=cmd_assemble)

    b = sub.add_parser("build", help="project folder w/ vo -> transcribe -> synced video")
    b.add_argument("project")
    b.add_argument("--audio", default=None, help="path to VO (default: vo.* in the project folder)")
    b.add_argument("--images-in", default=None, help="folder of pre-made images (mapped by order)")
    b.set_defaults(func=cmd_build)

    u = sub.add_parser("auto", help="one command: prompts -> images -> assemble")
    u.add_argument("transcript"); u.add_argument("audio")
    u.add_argument("--out", default="output")
    u.add_argument("--images-in", default=None,
                   help="folder of externally-generated images (mapped by order)")
    u.add_argument("--audio-seconds", type=float, default=None)
    u.set_defaults(func=cmd_auto)

    args = ap.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
