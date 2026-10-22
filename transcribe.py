"""Transcribe a stream VOD with word-level timestamps.

Usage: python transcribe.py work/vod.mp4 work/transcript.json [--model small.en]

The JSON holds every word with start/end seconds. edit.py reads it to bleep
curse words, and it doubles as a searchable log for picking moments.
"""
import argparse
import json
import subprocess
import sys
import time

import numpy as np
from faster_whisper import WhisperModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=args.threads)
    t0 = time.time()
    # Decode with the ffmpeg CLI: auto-editor pins its own PyAV build, which
    # faster-whisper's decoder can't use.
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", args.video, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segments, info = model.transcribe(
        audio,
        word_timestamps=True,
        vad_filter=True,
        # Keep swearing as spoken so the bleep pass can find it.
        suppress_tokens=[],
    )
    out = {"duration": info.duration, "segments": []}
    for seg in segments:
        out["segments"].append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for w in (seg.words or [])],
        })
        print(f"[{seg.start:7.1f}] {seg.text.strip()}", flush=True)
        # Save as we go so a long run can be inspected early.
        if len(out["segments"]) % 25 == 0:
            with open(args.out, "w") as f:
                json.dump(out, f)
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"done in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
