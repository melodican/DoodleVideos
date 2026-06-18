"""Doodle pipeline CLI.

  # 1) From a TurboScribe transcript, emit Higgsfield prompts + batch prompt:
  python -m pipeline.doodle.run prompts transcript.txt --out output/

  # 2) After images are generated & named by timestamp (e.g. 0_07.png),
  #    assemble the final video autonomously (replaces the CapCut step):
  python -m pipeline.doodle.run assemble transcript.txt images/ vo.mp3 --out output/video.mp4
"""
from __future__ import annotations
import argparse, pathlib
from .timestamps import parse
from .image_prompts import write_manifest, batch_prompt
from . import assemble


def cmd_prompts(args):
    segs = parse(pathlib.Path(args.transcript).read_text(encoding="utf-8"))
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    manifest = write_manifest(segs, str(out / "image_manifest.json"))
    (out / "batch_prompt.txt").write_text(batch_prompt(segs), encoding="utf-8")
    print(f"{len(segs)} segments")
    print(f"manifest:     {manifest}")
    print(f"batch prompt: {out / 'batch_prompt.txt'}")


def cmd_assemble(args):
    segs = parse(pathlib.Path(args.transcript).read_text(encoding="utf-8"))
    out = assemble.render(segs, args.images, args.audio, out_path=args.out,
                          audio_seconds=args.audio_seconds)
    print(f"rendered: {out}")


def main():
    ap = argparse.ArgumentParser(description="Doodle explainer pipeline")
    sub = ap.add_subparsers(required=True)
    p = sub.add_parser("prompts"); p.add_argument("transcript")
    p.add_argument("--out", default="output"); p.set_defaults(func=cmd_prompts)
    a = sub.add_parser("assemble"); a.add_argument("transcript")
    a.add_argument("images"); a.add_argument("audio")
    a.add_argument("--out", default="output/video.mp4")
    a.add_argument("--audio-seconds", type=float, default=None)
    a.set_defaults(func=cmd_assemble)
    args = ap.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
