"""Search a stream transcript for the moments worth keeping.

Usage:
  python tools/find_moments.py work/transcript.json                      # every line, timestamped
  python tools/find_moments.py work/transcript.json --words bed died bro  # exact word times for punchlines
  python tools/find_moments.py work/transcript.json --from 1330 --to 1420
  python tools/find_moments.py work/transcript.json --loud work/stream.mp4   # loudest moments (yelling, laughing)

Times are seconds in the original stream: paste them into a plan as "start"/"end"/"at".
"""
import argparse
import json
import re
import subprocess
import sys

# Whisper writes symbols like "♪" that the Windows console codepage can't print.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def loud_spots(video, top=25):
    """Short-term loudness peaks, a decent stand-in for screams, laughs and hype."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    pts = []
    for line in p.stderr.splitlines():
        m = re.search(r"t:\s*([\d.]+).*?S:\s*(-?[\d.]+)", line)
        if m:
            pts.append((float(m.group(1)), float(m.group(2))))
    pts.sort(key=lambda x: -x[1])
    picked = []
    for t, s in pts:
        if all(abs(t - u) > 20 for u, _ in picked):
            picked.append((t, s))
        if len(picked) >= top:
            break
    return sorted(picked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--words", nargs="*", help="print the start time of each of these words")
    ap.add_argument("--from", dest="start", type=float, default=0)
    ap.add_argument("--to", dest="end", type=float, default=1e9)
    ap.add_argument("--loud", metavar="VIDEO", help="also list the loudest moments of this video")
    args = ap.parse_args()

    t = json.load(open(args.transcript))
    if args.words:
        want = {w.lower() for w in args.words}
        for seg in t["segments"]:
            for w in seg["words"]:
                if re.sub(r"[^a-z0-9]", "", w["w"].lower()) in want and args.start <= w["s"] <= args.end:
                    print(f"{w['s']:8.2f}  {w['w']:<14} | {seg['text']}")
    else:
        for seg in t["segments"]:
            if seg["end"] >= args.start and seg["start"] <= args.end:
                print(f"{seg['start']:8.1f}-{seg['end']:7.1f}  {seg['text']}")
    if args.loud:
        print("\nloudest moments (time, short-term LUFS):")
        for when, lufs in loud_spots(args.loud):
            print(f"{when:8.1f}  {lufs:6.1f}")


if __name__ == "__main__":
    main()
