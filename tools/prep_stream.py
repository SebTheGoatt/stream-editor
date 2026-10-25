"""Get a new OBS recording ready for planning, in one go.

Usage: python tools/prep_stream.py "C:/Users/Raymu/Videos/<recording>.mp4" --name minecraft-ep2

Writes, under work/ (anything already there is reused):
  <name>_transcript.json   word timings (GPU via .venv-gpu when it exists, else CPU transcribe.py);
                           for an OBS recording with separate tracks (mix, mic, game, Discord), the
                           mic and Discord tracks are transcribed on their own and every word is
                           tagged with whose voice it was
  <name>_transcript.txt    every line, timestamped, for reading the whole stream
  <name>_loud.txt          the 40 loudest moments (screams, laughs, hype)
  <name>_overview.png      one frame every 4 minutes, to see what happened when
and plans/<name>.json: a starter plan with the Seb The Goat header and no segments yet.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from find_moments import loud_spots  # noqa: E402

HEADER = {
    "fps": 60,
    "crf": 10,
    "x264_preset": "fast",
    "facecam": [0.84, 0.83],
    "tighten": {"min_silence": 0.7, "pad": 0.15, "noise_db": -30},
    "palette": {"text": "white", "punch": "#FF2B2B", "danger": "#FF2B2B", "win": "#7CFC00", "box": "#E01B24"},
    "goat_sound": "goat",
    "bleep_sound": "quack",
    "layout": {"game": [1920, 0, 1920, 1080], "cam": [0, 0, 1920, 1080], "cam_size": [568, 320],
               "cam_pos": [1324, 732], "border": 4},
}


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", video],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    s = info["streams"][0]
    n_audio = len(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                  "-of", "csv=p=0", video], capture_output=True, text=True, check=True).stdout.split())
    return s["width"], s["height"], float(info["format"]["duration"]), n_audio


def parse_tracks(spec):
    """"mic=1,game=2,friends=3" -> {"mic": 1, ...}: audio stream numbers, 0 being OBS track 1."""
    return {k: int(v) for k, v in (part.split("=") for part in spec.split(","))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--name", required=True, help="short slug, used for every output file")
    ap.add_argument("--tracks", help='OBS audio tracks, e.g. "mic=1,game=2,friends=3" (stream numbers, '
                                     '0 = track 1 = full mix). Default: that layout when the file has 4+ audio streams')
    args = ap.parse_args()
    work = os.path.join(HERE, "work")
    os.makedirs(work, exist_ok=True)
    base = os.path.join(work, args.name)

    w, h, dur, n_audio = probe(args.video)
    print(f"{args.video}: {w}x{h}, {dur / 3600:.2f} h, {n_audio} audio track(s)")
    if (w, h) != (3840, 1080):
        print("! not the usual 3840x1080 webcam|game recording: check the plan's \"layout\" before rendering")
    tracks = parse_tracks(args.tracks) if args.tracks else (
        {"mic": 1, "game": 2, "friends": 3} if n_audio >= 4 else None)
    if tracks:
        print("separate tracks:", ", ".join(f"{k} = OBS track {v + 1}" for k, v in tracks.items()))

    transcript = base + "_transcript.json"
    if not os.path.exists(transcript):
        gpu = os.path.join(HERE, ".venv-gpu", "Scripts", "python.exe")
        print("transcribing (about 15 min per hour of stream on the GPU)...", flush=True)
        if tracks:
            # Each voice on its own track transcribes cleaner, and the editor can bleep only that voice.
            # GPU (AMD ROCm) when .venv-gpu exists, else the CPU transcriber, which takes the same flags.
            engine = ([gpu, os.path.join(HERE, "transcribe_gpu.py")] if os.path.exists(gpu)
                      else [sys.executable, os.path.join(HERE, "transcribe.py")])
            merged = {"duration": dur, "segments": []}
            for voice in ("mic", "friends"):
                if voice not in tracks:
                    continue
                part = f"{base}_{voice}_transcript.json"
                if not os.path.exists(part):
                    subprocess.run([*engine, args.video, part, "--track", str(tracks[voice]), "--label", voice],
                                   check=True)
                merged["segments"] += [{**s, "track": voice} for s in json.load(open(part))["segments"]]
            merged["segments"].sort(key=lambda s: s["start"])
            with open(transcript, "w") as f:
                json.dump(merged, f)
        else:
            if os.path.exists(gpu):
                cmd = [gpu, os.path.join(HERE, "transcribe_gpu.py"), args.video, transcript]
            else:
                cmd = [sys.executable, os.path.join(HERE, "transcribe.py"), args.video, transcript]
            subprocess.run(cmd, check=True)
    t = json.load(open(transcript))
    with open(base + "_transcript.txt", "w", encoding="utf-8") as f:
        # Who said it, when the voices came from separate tracks: SEB (his mic) or BOYS (Discord).
        who = {"mic": "SEB  ", "friends": "BOYS "}
        f.writelines(f"{s['start']:8.1f}-{s['end']:7.1f}  {who.get(s.get('track'), '')}{s['text']}\n"
                     for s in t["segments"])
    print(f"{len(t['segments'])} lines -> {base}_transcript.txt")

    if not os.path.exists(base + "_loud.txt"):
        with open(base + "_loud.txt", "w") as f:
            f.writelines(f"{when:8.1f}  {lufs:6.1f}\n" for when, lufs in loud_spots(args.video, top=40))

    overview = base + "_overview.png"
    if not os.path.exists(overview):
        # Seek to each frame instead of decoding the whole file: seconds, not minutes.
        times = list(range(30, int(dur), 240)) or [int(dur / 2)]
        frames = []
        for i, sec in enumerate(times):
            frame = f"{base}_ov{i:03d}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(sec), "-i", args.video, "-frames:v", "1",
                            "-vf", "scale=480:-1", frame], check=True)
            frames.append(frame)
        cols = min(6, len(frames))
        rows = (len(frames) + cols - 1) // cols
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{base}_ov%03d.png", "-vf", f"tile={cols}x{rows}",
                        "-frames:v", "1", overview], check=True)
        for frame in frames:
            os.remove(frame)
        print(f"overview: one frame every 4 min, row by row from {times[0]}s -> {overview}")

    plan = os.path.join(HERE, "plans", args.name + ".json")
    if not os.path.exists(plan):
        starter = {"title": args.name, "source": args.video.replace("\\", "/"),
                   "transcript": f"../work/{args.name}_transcript.json", "sfx_dir": "../sfx",
                   "output": f"../out/{args.name}.mp4", **HEADER,
                   **({"audio_tracks": tracks} if tracks else {}), "segments": []}
        with open(plan, "w", encoding="utf-8") as f:
            json.dump(starter, f, indent=2)
        print(f"starter plan -> {plan}")


if __name__ == "__main__":
    main()
