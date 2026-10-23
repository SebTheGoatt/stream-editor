"""Transcribe a stream VOD on the GPU (AMD ROCm or NVIDIA CUDA) with word-level timestamps.

Usage: python transcribe_gpu.py work/vod.mp4 work/transcript.json [--model medium.en]

Same JSON as transcribe.py, so find_moments.py and edit.py read it unchanged.
faster-whisper only runs on NVIDIA GPUs; this uses openai-whisper on PyTorch,
which also runs on AMD cards through the ROCm build of PyTorch.
"""
import argparse
import json
import sys
import time

import torch
import whisper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--model", default="medium.en")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device} {torch.cuda.get_device_name(0) if device == 'cuda' else ''}", flush=True)
    model = whisper.load_model(args.model, device=device)
    t0 = time.time()
    audio = whisper.load_audio(args.video)
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
            "words": [{"w": w["word"].strip(), "s": round(w["start"], 2), "e": round(w["end"], 2)}
                      for w in seg.get("words", [])],
        })
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"done in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
