"""Second bleep pass: re-transcribe every kept moment on its own and bleep swears the first pass missed.

Usage (needs whisper, so run it with the GPU env):
  .venv-gpu/Scripts/python.exe tools/bleep_pass.py plans/cave-dweller-part1.json plans/cave-dweller-part2.json

A full-stream transcript leans on context and drops or softens words. Short, context-free passes over
each segment catch many of them. New swears go into the plan's "bleeps" list (source seconds),
which edit.py bleeps alongside the transcript's own. Slurs it hears are only reported: cut those
lines with the segment's "cuts" list. Whisper can also hear a slur as "thing", so check the finished
master with Resolve's subtitles too (see the sebthegoat-edit skill).
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from edit import DEFAULT_BLEEP, bleep_words  # noqa: E402

SLURS = ["nigg*", "fag*", "retard*"]


def matches(word, patterns):
    bare = re.sub(r"[^a-z]", "", word.lower())
    return bool(bare) and any(fnmatch.fnmatch(bare, p) for p in patterns)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--model", default="medium.en")
    args = ap.parse_args()

    import torch
    import whisper
    model = whisper.load_model(args.model, device="cuda" if torch.cuda.is_available() else "cpu")
    for plan_path in args.plans:
        base = os.path.dirname(os.path.abspath(plan_path))
        text = open(plan_path, encoding="utf-8").read()
        cfg = json.loads(text)
        src = os.path.normpath(os.path.join(base, cfg["source"]))
        transcript = json.load(open(os.path.join(base, cfg["transcript"]), encoding="utf-8"))
        patterns = cfg.get("bleep_words", DEFAULT_BLEEP)
        # Separate OBS tracks: check each voice on its own track, and tag its bleeps with that voice.
        tracks = cfg.get("audio_tracks") or {}
        voices = [(n, tracks[n]) for n in ("mic", "friends") if n in tracks] or [(None, None)]
        new = []
        for voice, stream in voices:
            known = bleep_words(transcript, 0, 1e9, patterns, voice) + [
                tuple(x[:2]) for x in cfg.get("bleeps", []) if len(x) < 3 or x[2] == voice]
            mine = []
            for seg in cfg["segments"]:
                if "clip" in seg:
                    continue
                a, b = seg["start"], seg["end"]
                with tempfile.TemporaryDirectory() as tmp:
                    wav = os.path.join(tmp, "seg.wav")
                    pick = ["-map", f"0:a:{stream}"] if stream is not None else ["-vn"]
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", src, *pick,
                                    "-ac", "1", "-ar", "16000", wav], check=True)
                    res = model.transcribe(wav, fp16=torch.cuda.is_available(), suppress_tokens="",
                                           word_timestamps=True, condition_on_previous_text=False, verbose=None)
                for w in (w for s in res["segments"] for w in s.get("words", [])):
                    s, e = a + w["start"], a + w["end"]
                    who = f" [{voice}]" if voice else ""
                    if matches(w["word"], SLURS):
                        print(f"  ! SLUR heard at {s:.2f}s{who} in '{seg['label']}': {w['word'].strip()} "
                              "-> add it to that segment's \"cuts\"")
                    if matches(w["word"], patterns) and not any(ks - 0.4 < s < ke + 0.4 for ks, ke in known + mine):
                        mine.append((round(s - 0.05, 2), round(max(e, s + 0.4) + 0.05, 2)))
                        new.append(mine[-1] + ((voice,) if voice else ()))
                        print(f"  + bleep {s:8.2f}s{who} {w['word'].strip():<12} ({seg['label']})")
        if new:
            bleeps = sorted([list(x) for x in cfg.get("bleeps", [])] + [list(x) for x in new])
            line = f'  "bleeps": {json.dumps(bleeps)},\n'
            text = re.sub(r'  "bleeps": .*\n', "", text)
            text = text.replace('  "segments": [', line + '  "segments": [', 1)
            json.loads(text)
            open(plan_path, "w", encoding="utf-8").write(text)
        print(f"{plan_path}: {len(new)} new bleeps")


if __name__ == "__main__":
    main()
