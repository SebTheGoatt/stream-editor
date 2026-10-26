"""Cut vertical Shorts (TikTok / Reels / YouTube Shorts) straight from a long-form edit plan.

Usage:
  python tools/make_shorts.py plans/cave-dweller-part1.json                # rank, then render the top 4
  python tools/make_shorts.py plans/cave-dweller-part1.json --top 6 --preview
  python tools/make_shorts.py plans/cave-dweller-part1.json --only "I lied I lied,the timeshare"
  python tools/make_shorts.py plans/cave-dweller-part1.json --plan-only   # just print the ranking

Like Vizard's clip picker, but it reads the edit itself: a moment scores for its GOAT moment,
freeze frames, zooms, counters and transcript laughs, and for landing in the 15-45 s sweet spot.
Each Short is 1080x1920: webcam on top, game below, every word captioned, the moment's best
caption as the hook. Plans go to work/shorts/, videos to out/shorts/, plus a ranking file with
hook lines to start titles from.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from edit import laughs  # noqa: E402

CAM_H, GAME_H, W = 700, 1220, 1080
# The prebuilt 1920x1080 game+cam file (work/stream.mp4) has the webcam inset here.
INSET = [1324, 732, 568, 320]


def centered(region, aspect):
    """The widest crop of region [x, y, w, h] with this width/height aspect, centered, even-sized."""
    x, y, w, h = region
    cw = min(w, int(h * aspect) // 2 * 2)
    return [x + (w - cw) // 2, y, cw, h]


def stack_layout(cfg):
    lay = cfg.get("layout") or {}
    if "cam" in lay:  # raw OBS recording: full 1080p webcam and game halves
        cam, game = lay["cam"], lay["game"]
        game_crop = centered(game, W / GAME_H)
    else:  # prebuilt 1920x1080 file: the small inset is the only webcam there is
        cam = INSET
        # As close to the center as the game goes without catching the inset's edge.
        game_crop = centered([0, 0, 1920, 1080], W / GAME_H)
        game_crop[0] = min(game_crop[0], INSET[0] - 6 - game_crop[2])
    return {"stack": [{"crop": centered(cam, W / CAM_H), "size": [W, CAM_H]},
                      {"crop": game_crop, "size": [W, GAME_H]}]}


def score(seg, laugh_marks):
    fx = seg.get("fx", [])
    n = lambda t: sum(f["type"] == t for f in fx)  # noqa: E731
    dur = seg["end"] - seg["start"]
    pts = 5 * n("goat") + 2 * n("freeze") + n("zoom") + n("counter")
    pts += 2 * sum(seg["start"] <= s <= seg["end"] for s, _ in laugh_marks)
    pts += 2 if 15 <= dur <= 45 else 0
    return pts


def hook(seg):
    """The moment's punchline caption (a highlighted one first), else its label."""
    texts = [f for f in seg.get("fx", []) if f["type"] == "text"]
    texts.sort(key=lambda f: (0 if f.get("color") not in (None, "white", "text") else 1, f["at"]))
    return texts[0]["text"] if texts else seg["label"].upper()


def short_plan(cfg, seg, base_dir, name, max_len):
    a, b = seg["start"], seg["end"]
    if b - a > max_len:  # keep the window around the moment's biggest beat
        beats = [f["at"] for f in seg["fx"] if f["type"] in ("goat", "freeze", "zoom")] or [a]
        a = max(a, min(beats[0] - max_len * 0.6, b - max_len))
        b = a + max_len
    keep = ("zoom", "goat", "freeze", "sfx", "counter", "look", "shake", "slowmo", "music")
    fx = [dict(f) for f in seg["fx"] if f["type"] in keep and a <= f["at"] <= b
          and "CONTINUED" not in f.get("text", "")]
    for f in fx:
        # The webcam already fills the top third, so punch-ins only need to be gentle.
        if f["type"] in ("zoom", "goat"):
            f["scale"] = min(f.get("scale", 2.4), 1.6)
        elif f["type"] == "freeze" and f.get("zoom", 1.8) > 1:
            f["zoom"] = min(f.get("zoom", 1.8), 1.6)
    fx.append({"type": "text", "at": a + 0.05, "dur": 2.6, "text": hook(seg), "pos": "center", "color": "punch"})
    rel = lambda p: os.path.normpath(os.path.join(base_dir, p))  # noqa: E731
    keys = ("palette", "goat_sound", "tighten", "bleep", "bleep_words", "bleeps", "bleep_sound", "bleep_volume",
            "audio_tracks", "track_levels", "track_filters")
    return {"title": hook(seg), "source": rel(cfg["source"]), "transcript": rel(cfg["transcript"]),
            "sfx_dir": rel(cfg.get("sfx_dir", "../sfx")), "output": os.path.join(HERE, "out", "shorts", name + ".mp4"),
            "width": W, "height": CAM_H + GAME_H, "fps": 30, "crf": 18, "x264_preset": "fast",
            "facecam": [0.5, CAM_H / 2 / (CAM_H + GAME_H)], "layout": stack_layout(cfg), "subtitles": True,
            **{k: cfg[k] for k in keys if k in cfg},
            # The long edit's cut lines (slurs, anything pulled) stay cut in the Short.
            "segments": [{"label": seg["label"], "start": round(a, 2), "end": round(b, 2), "fx": fx,
                          "cuts": [c for c in seg.get("cuts", []) if c[1] > a and c[0] < b]}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--top", type=int, default=4)
    ap.add_argument("--only", help="comma-separated segment labels instead of the ranking")
    ap.add_argument("--max", type=float, default=55, help="longest source window per Short, seconds")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()

    base_dir = os.path.dirname(os.path.abspath(args.plan))
    cfg = json.load(open(args.plan, encoding="utf-8"))
    transcript = json.load(open(os.path.join(base_dir, cfg["transcript"]), encoding="utf-8"))
    laugh_marks = laughs(transcript)
    moments = [s for s in cfg["segments"] if "clip" not in s and not s["label"].startswith("cold open")]
    ranked = sorted(moments, key=lambda s: -score(s, laugh_marks))
    if args.only:
        wanted = [x.strip() for x in args.only.split(",")]
        picks = [s for s in moments if s["label"] in wanted]
    else:
        picks = ranked[:args.top]

    stem = os.path.splitext(os.path.basename(args.plan))[0]
    os.makedirs(os.path.join(HERE, "work", "shorts"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "out", "shorts"), exist_ok=True)
    print("rank  score  length  moment")
    for i, s in enumerate(ranked, 1):
        mark = "*" if s in picks else " "
        print(f"{mark}{i:3d}  {score(s, laugh_marks):5d}  {s['end'] - s['start']:5.0f}s  {s['label']}")
    summary = []
    for k, seg in enumerate(picks, 1):
        name = f"{stem}-{k}-" + re.sub(r"[^a-z0-9]+", "-", seg["label"].lower()).strip("-")
        plan = short_plan(cfg, seg, base_dir, name, args.max)
        path = os.path.join(HERE, "work", "shorts", name + ".json")
        json.dump(plan, open(path, "w", encoding="utf-8"), indent=2)
        summary.append({"short": name, "hook": plan["title"], "moment": seg["label"],
                        "video": plan["output"].replace(".mp4", "_preview.mp4") if args.preview else plan["output"]})
        if not args.plan_only:
            cmd = [sys.executable, os.path.join(HERE, "edit.py"), path, "--jobs", "4"] + (["--preview"] if args.preview else [])
            subprocess.run(cmd, check=True)
    out = os.path.join(HERE, "out", "shorts", stem + "-shorts.json")
    json.dump(summary, open(out, "w", encoding="utf-8"), indent=2)
    print(f"{len(summary)} Shorts -> {out}")


if __name__ == "__main__":
    main()
