"""Runs the whole pipeline:  document  ->  60-second script (Claude)  ->  1080x1920 Reel (.mp4).

    python main.py                      # everything
    python main.py --only script        # step 1 only (then edit output/*_script.txt if you like)
    python main.py --only video         # step 2 only, using the newest script in output/

Run `python main.py --help` for all options.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time

from config import ReelsError, check_python, ensure_folders, setup_console, show

try:
    import step1_generate_script as step1
    import step2_generate_video as step2
except ImportError as exc:  # libraries not installed yet
    sys.exit(
        f"A required library is missing ('{exc.name}'). Install everything with:\n"
        "  pip install -r requirements.txt\n"
        "(See the README, section 'Install the project libraries'.)"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn a history article (PDF/TXT) into a narrated, subtitled Instagram Reel.",
        parents=[step1.build_arg_parser(add_help=False), step2.build_arg_parser(add_help=False)],
    )
    parser.add_argument(
        "--only",
        choices=["script", "video"],
        help="run just one step: 'script' (step 1) or 'video' (step 2)",
    )
    return parser.parse_args()


def main() -> int:
    setup_console()
    args = parse_args()
    started = time.time()
    try:
        check_python()
        ensure_folders()
        if shutil.which("ffmpeg") is None and args.only != "script":
            print("Note: FFmpeg was not found on your PATH; using the copy bundled with MoviePy.")

        script_path = args.script
        if args.only != "video":
            print("\n[1/2] Writing the voice-over script with Claude")
            script_path = step1.generate_script(args.input, args.model)

        video_path = None
        if args.only != "script":
            print("\n[2/2] Building the video")
            video_path = step2.generate_video(
                script_path,
                voice=args.voice,
                rate=args.rate,
                pitch=args.pitch,
                fit=args.fit,
                fps=args.fps,
                words_per_chunk=args.words,
                uppercase=not args.no_uppercase,
            )
    except ReelsError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130

    minutes, seconds = divmod(int(time.time() - started), 60)
    print(f"\nDone in {minutes} min {seconds} s.")
    if args.only != "video":
        print(f"  Script: {show(script_path)}")
    if video_path is not None:
        print(f"  Video:  {show(video_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
