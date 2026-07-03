"""B-roll explainer renderer CLI (the cheap, fully-API Vidrush alternative).

  # render a stock-footage explainer for a project that has vo.* (+ transcript.txt)
  python -m pipeline.broll.run build projects/what-actually-is-tax

  # control footage pacing / pass a topic to improve footage queries
  python -m pipeline.broll.run build projects/what-actually-is-tax \\
      --seconds-per-clip 6 --topic "what is tax"

Set PEXELS_API_KEY (free at pexels.com/api) for real footage; without it the build
still runs with labelled placeholder cards so you can judge sync + captions.
"""
from __future__ import annotations
import argparse, sys
from .builder import build_broll
from .channel import RenderOptions, load_channel


def cmd_build(args):
    # start from a channel blueprint (if given), then apply explicit flag overrides
    opts = load_channel(args.channel) if args.channel else RenderOptions()
    if args.source is not None:
        opts.source = args.source
    if args.captions is not None:
        opts.captions = args.captions
    if args.caption_style is not None:
        opts.caption_style = args.caption_style
    if args.motion:
        opts.motion = True
    if args.seconds_per_clip is not None:
        opts.seconds_per_clip = args.seconds_per_clip
    try:
        out = build_broll(args.project, audio_path=args.audio,
                          transcript_path=args.transcript, topic=args.topic,
                          seconds_per_clip=opts.seconds_per_clip, source=opts.source,
                          motion=opts.motion, captions_on=opts.captions_on,
                          caption_style=opts.caption_style, max_scenes=args.max_scenes,
                          progress=lambda stage, detail="": print(f"[{stage}] {detail}"))
        print(f"rendered: {out}")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[!] {e}"); sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description="B-roll / documentary renderer")
    sub = ap.add_subparsers(required=True)
    b = sub.add_parser("build", help="project folder w/ vo -> explainer/documentary mp4")
    b.add_argument("project")
    b.add_argument("--channel", default=None,
                   help="channel blueprint name or path (config/channels/<name>.yaml)")
    b.add_argument("--audio", default=None, help="path to VO (default: vo.* in the folder)")
    b.add_argument("--transcript", default=None, help="timed transcript (default: transcript.txt)")
    b.add_argument("--topic", default="", help="topic hint to improve footage queries")
    b.add_argument("--seconds-per-clip", type=float, default=None, help="scene length (default 6)")
    b.add_argument("--source", choices=["stock", "images"], default=None,
                   help="stock=Pexels footage; images=on-hand AI images (images/NNN.png)")
    b.add_argument("--captions", choices=["on", "off"], default=None,
                   help="burn captions (default: off / from the channel blueprint)")
    b.add_argument("--caption-style", default=None, help="bold | minimal | lower")
    b.add_argument("--motion", action="store_true", help="Ken Burns motion on still images (slow)")
    b.add_argument("--max-scenes", type=int, default=None, help="cap scene count (demo excerpts)")
    b.set_defaults(func=cmd_build)
    args = ap.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
