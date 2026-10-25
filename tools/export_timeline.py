"""Export an edit plan as an editable timeline for DaVinci Resolve, Premiere or FilmCraft.

Usage:
  python tools/export_timeline.py plans/cod-mw4-jevmerk.json
  python tools/export_timeline.py plans/cod-mw4-jevmerk.json --source work/cod_hd.mp4   # point at the HD original

Builds the timeline with FilmCraft's headless CLI (https://github.com/storytold/filmcraft): the same cuts
`edit.py` renders (dead air trimmed, cut lines removed), with the channel intro/outro, on a 1080p30
sequence. Effects aren't baked in; each one becomes a colored marker instead, so the polish happens
in the editor at full quality:

  Yellow  ZOOM / SHAKE      punch in on the facecam
  Blue    FREEZE            hold the frame, black and white, with the caption
  Green   TEXT / OVERLAY    on-screen text, or a graphic like brand/subscribe.mov
  Purple  SFX / MUSIC       sound effect or music bed to drop in
  Rose    BLEEP             a swear to mute or bleep

Writes out/timelines/<plan>.xml (FCP 7 XML: Resolve File > Import > Timeline), .fcpxml, .otio, .edl
and .fcproj (opens in FilmCraft). Needs filmcraft-cli on PATH, in FILMCRAFT_CLI, or via --filmcraft.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import edit  # noqa: E402

TICKS = 254_016_000_000  # FilmCraft ticks per second
FPS = 30
COLORS = {"zoom": "Yellow", "shake": "Yellow", "freeze": "Blue", "text": "Green", "sfx": "Purple",
          "music": "Purple", "look": "Yellow", "slowmo": "Yellow", "overlay": "Green", "bleep": "Rose"}


def frames(seconds):
    return int(round(seconds * FPS))


def marker_name(f):
    t = f["type"]
    if t == "zoom":
        return f"ZOOM x{f.get('scale', 2.2)} ({f.get('target', 'face')})"
    if t == "freeze":
        return f"FREEZE {f.get('dur', 1.5)}s: {f.get('text', '')}".strip(": ")
    if t == "text":
        return f"TEXT: {f['text']}"
    if t in ("sfx", "music"):
        return f"{t.upper()}: {f.get('name')}"
    if t == "overlay":
        return f"OVERLAY: {os.path.basename(f['file'])}"
    if t == "look":
        return f"LOOK: {f['look']}"
    if t == "slowmo":
        return f"SLOW-MO x{f.get('factor', 0.5)} (skip if the game audio drifts)"
    return t.upper()


def find_cli(arg):
    for c in (arg, os.environ.get("FILMCRAFT_CLI"), shutil.which("filmcraft-cli"), shutil.which("filmcraft-cli.exe")):
        if c and os.path.exists(c):
            return c
    sys.exit("filmcraft-cli not found: install FilmCraft (github.com/storytold/filmcraft/releases) and pass --filmcraft "
             "or set FILMCRAFT_CLI")


def fc_run(cli, lines, *opts):
    script = os.path.join(ROOT, "work", "_filmcraft_run.jsonl")
    os.makedirs(os.path.dirname(script), exist_ok=True)
    with open(script, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(line) + "\n" for line in lines)
    p = subprocess.run([cli, *opts, "--compact", "--keep-going", "run", script], capture_output=True, text=True)
    results = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    bad = [r for r in results if not r.get("ok")]
    for r in bad:
        print(f"  ! FilmCraft line {r.get('line')} {r.get('id')}: {r.get('error', r)}", file=sys.stderr)
    if p.returncode and not results:
        sys.exit(p.stderr[-2000:])
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--source", help="use this recording instead of the plan's (e.g. the HD original)")
    ap.add_argument("--filmcraft", help="path to filmcraft-cli")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "out", "timelines"))
    args = ap.parse_args()

    cli = find_cli(args.filmcraft)
    base = os.path.dirname(os.path.abspath(args.plan))
    cfg = json.load(open(args.plan))

    def rel(p):
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    src = os.path.abspath(args.source) if args.source else rel(cfg["source"])
    transcript = json.load(open(rel(cfg["transcript"]))) if cfg.get("transcript") and os.path.exists(rel(cfg["transcript"])) else {}
    laugh_marks = edit.laughs(transcript)
    patterns = cfg.get("bleep_words", edit.DEFAULT_BLEEP)

    # Media: the recording first, then every inserted clip (intro, outro...), in order.
    media = [src]
    for seg in cfg["segments"]:
        if "clip" in seg and rel(seg["clip"]) not in media:
            media.append(rel(seg["clip"]))
    item_of = {path: i + 1 for i, path in enumerate(media)}  # FilmCraft numbers imports 1..n in a new project

    name = os.path.splitext(os.path.basename(args.plan))[0]
    os.makedirs(args.out_dir, exist_ok=True)
    proj = os.path.join(args.out_dir, f"{name}.fcproj")
    title = cfg.get("title", name)
    first = fc_run(cli, [
        {"id": "file.newProject", "params": {"name": title}},
        {"id": "file.import", "params": {"paths": media}},
        {"id": "file.newSequence", "params": {"name": title, "width": 1920, "height": 1080, "fps": FPS,
                                              "video": 2, "audio": 2}},
    ], "--save-as", proj)
    imported = next((r["result"]["items"] for r in first if r.get("id") == "file.import" and r.get("ok")), [])
    if len(imported) != len(media):
        sys.exit(f"FilmCraft imported {len(imported)} of {len(media)} files: {media}")
    item_of = dict(zip(media, imported))

    lines, t, cuts, n_markers = [], 0, 0, 0

    def mark(at_frame, f_or_name, comment=""):
        nonlocal n_markers
        if isinstance(f_or_name, dict):
            nm, color = marker_name(f_or_name), COLORS.get(f_or_name["type"], "Yellow")
            comment = comment or json.dumps({k: v for k, v in f_or_name.items() if k not in ("type", "at")})
        else:
            nm, color = f_or_name, COLORS["bleep"]
        lines.append({"id": "markers.add", "params": {"target": "program", "time": at_frame * (TICKS // FPS),
                                                      "name": nm[:120], "comment": comment[:500], "color": color}})
        n_markers += 1

    for seg in cfg["segments"]:
        if "clip" in seg:
            dur = frames(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                               "-of", "csv=p=0", rel(seg["clip"])], capture_output=True,
                                              text=True).stdout))
            lines.append({"id": "timeline.place", "params": {"item": item_of[rel(seg["clip"])], "track": "V1",
                                                             "audioTrack": "A1", "time": t * (TICKS // FPS)}})
            for f in seg.get("fx", []):
                mark(t + frames(f["at"]), f)
            t += dur
            cuts += 1
            continue
        edit.expand_goat(seg, cfg)
        fx = seg.get("fx", [])
        for piece in edit.pieces_for(seg, src, cfg, laugh_marks):
            if piece["kind"] == "freeze":
                mark(t, piece["fx"])
                continue
            a, b = piece["a"], piece["b"]
            fa, n = frames(a), frames(b) - frames(a)
            if n <= 0:
                continue
            lines.append({"id": "timeline.place", "params": {
                "item": item_of[src], "track": "V1", "audioTrack": "A1", "time": t * (TICKS // FPS),
                "sourceIn": fa * (TICKS // FPS), "duration": n * (TICKS // FPS)}})
            for f in fx:
                if f["type"] != "freeze" and a <= f["at"] < b:
                    mark(t + frames(f["at"] - a), f)
            for s, e in edit.bleep_words(transcript, a, b, patterns):
                mark(t + frames(s - a), "BLEEP", f"{e - s:.2f}s")
            t += n
            cuts += 1

    stem = os.path.join(args.out_dir, name)
    lines += [
        {"id": "file.exportFcp7Xml", "params": {"path": stem + ".xml"}},
        {"id": "file.exportFcpxml", "params": {"path": stem + ".fcpxml"}},
        {"id": "file.exportOtio", "params": {"path": stem + ".otio"}},
        {"id": "file.exportEdl", "params": {"path": stem + ".edl"}},
    ]
    results = fc_run(cli, lines, "--project", proj, "--save")
    failed = sum(1 for r in results if not r.get("ok"))
    print(f"{name}: {cuts} clips, {n_markers} markers, {t / FPS / 60:.1f} min"
          + (f", {failed} FilmCraft commands failed" if failed else ""))
    for ext in ("xml", "fcpxml", "otio", "edl", "fcproj"):
        print(f"  {stem}.{ext}")


if __name__ == "__main__":
    main()
