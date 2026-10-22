"""Grid of timestamped frames, for finding visual beats (deaths, kills, menus) fast.

Usage:
  python tools/contact_sheet.py work/stream.mp4 --start 1338 --dur 36 --out work/sheet.png
  python tools/contact_sheet.py out/edit_preview.mp4 --every 3 --out work/check.png   # review a whole edit

Each tile is stamped with its time in the source, so you can copy it straight into a plan.
"""
import argparse
import math
import os
import subprocess

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts", "Anton-Regular.ttf")


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, help="seconds to cover (default: to the end)")
    ap.add_argument("--every", type=float, default=1.0, help="seconds between tiles")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--width", type=int, default=256, help="tile width in pixels")
    ap.add_argument("--out", default="sheet.png")
    args = ap.parse_args()

    dur = args.dur or (duration(args.video) - args.start)
    n = max(1, int(dur / args.every))
    rows = math.ceil(n / args.cols)
    font = FONT.replace("\\", "/").replace(":", "\\:")
    stamp = (f"drawtext=fontfile='{font}':text='%{{eif\\:{args.start}+t\\:d}}':x=4:y=4:fontsize=22:"
             "fontcolor=yellow:borderw=2")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(args.start), "-t", str(dur), "-i", args.video,
                    "-vf", f"fps=1/{args.every},scale={args.width}:-1,{stamp},tile={args.cols}x{rows}",
                    "-frames:v", "1", args.out], check=True)
    print(args.out)


if __name__ == "__main__":
    main()
