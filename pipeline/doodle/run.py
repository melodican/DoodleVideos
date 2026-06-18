"""Doodle pipeline CLI — covers steps 4-7 of the doodle workflow.

  # One command, end-to-end (steps 4->7): prompts -> images -> assemble
  python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/
      # if no image API key: writes prompts and stops at a manual checkpoint.
      # after you generate images in Higgsfield and download them:
  python -m pipeline.doodle.run auto transcript.txt vo.mp3 --out output/ --images-in raw/

  # Or run a single stage:
  python -m pipeline.doodle.run prompts transcript.txt --out output/
  python -m pipeline.doodle.run assemble transcript.txt images/ vo.mp3 --out output/video.mp4
"""
from __future__ import annotations
import argparse, pathlib, sys
from .timestamps import parse
from .image_prompts import write_manifest, batch_prompt, per_segment_prompts
from . import assemble, images, script_writer


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
                          audio_seconds=args.audio_seconds)
    print(f"rendered: {out}")


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
                            audio_seconds=args.audio_seconds)
    print(f"[3/3] rendered: {video}")


def main():
    ap = argparse.ArgumentParser(description="Doodle explainer pipeline (steps 4-7)")
    sub = ap.add_subparsers(required=True)

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
    a.set_defaults(func=cmd_assemble)

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
