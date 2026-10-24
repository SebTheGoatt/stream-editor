"""Transcribe a stream VOD on the GPU (AMD ROCm or NVIDIA CUDA) with word-level timestamps.

Usage: python transcribe_gpu.py work/vod.mp4 work/transcript.json [--model medium.en]
       python transcribe_gpu.py work/vod.mp4 work/mic.json --track 1 --label mic   # one OBS audio track

Same JSON as transcribe.py, so find_moments.py and edit.py read it unchanged. With --track, only
that audio stream is transcribed (0 = OBS track 1) and every word is tagged with --label, so the
editor can bleep just the voice that said it.
faster-whisper only runs on NVIDIA GPUs; this uses openai-whisper on PyTorch,
which also runs on AMD cards through the ROCm build of PyTorch.
"""
import argparse
import json
import subprocess
import sys
import time

import numpy as np
import torch
import whisper


def load_track(video, track):
    """One audio stream of the file as 16 kHz mono float32, the way whisper.load_audio does it."""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-map", f"0:a:{track}", "-ac", "1", "-ar",
                          str(whisper.audio.SAMPLE_RATE), "-f", "s16le", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--model", default="medium.en")
    ap.add_argument("--track", type=int, help="audio stream to transcribe (0 = OBS track 1); default: the first")
    ap.add_argument("--label", help="tag every word with this voice name, e.g. mic or friends")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device} {torch.cuda.get_device_name(0) if device == 'cuda' else ''}", flush=True)
    model = whisper.load_model(args.model, device=device)
    t0 = time.time()
    audio = whisper.load_audio(args.video) if args.track is None else load_track(args.video, args.track)
    res = model.transcribe(
        audio,
        word_timestamps=True,
        fp16=device == "cuda",
        # Keep swearing as spoken so the bleep pass can find it.
        suppress_tokens="",
        condition_on_previous_text=False,
        verbose=False,
    )
    out = {"duration": len(audio) / whisper.audio.SAMPLE_RATE, "segments": []}
    for seg in res["segments"]:
        out["segments"].append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
            "words": [{"w": w["word"].strip(), "s": round(w["start"], 2), "e": round(w["end"], 2),
                       **({"track": args.label} if args.label else {})}
                      for w in seg.get("words", [])],
        })
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"done in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
