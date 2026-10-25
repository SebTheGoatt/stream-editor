"""Turn a full edit plan into a FaZe Jev / M3RKMUS1C-style plan: let the gameplay and commentary breathe.

Usage: python tools/jev_merk_plan.py plans/cod-mw4.json      # writes plans/cod-mw4-jevmerk.json
       python tools/jev_merk_plan.py plans/cod-mw4.json --pad 10 --zooms 4 --freezes 2

What both creators do (from breakdowns of their Oct 2026 MW4 videos):
- Long continuous clips (15-90 s) with hard cuts; whole thoughts are never chopped mid-sentence.
- Boring stretches are skipped with one hard cut, not trimmed word by word.
- No captions, meme sounds or music under gameplay. Voice up front, game underneath.
- Merk's only accents: 3-4 snap zooms on the facecam for big reactions, 1-2 black-and-white freezes
  on the biggest punchlines, a "LIKE + SUB" card early on, a loud end card.

So this script widens every moment for context, merges moments that are close together, only cuts
long silences (2 s+), keeps a few face zooms (no shake) and freezes (no sound effects), drops
everything else, and adds one subscribe card. No slow-mo or speed changes, which also keeps
recordings whose game audio drifts from looking worse.
"""
import argparse
import json
import os
import subprocess


def media_duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True, check=True).stdout)


def spread(items, n):
    """Pick n items spread evenly through the list (keeps the first and last big moments)."""
    if len(items) <= n:
        return items
    if n <= 0:
        return []
    if n == 1:
        return [items[len(items) // 2]]
    step = (len(items) - 1) / (n - 1)
    return [items[round(i * step)] for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--out")
    ap.add_argument("--pad", type=float, default=8.0, help="seconds of context added before and after each moment")
    ap.add_argument("--merge-gap", type=float, default=12.0, help="join moments closer than this")
    ap.add_argument("--zooms", type=int, default=4, help="face punch-ins to keep")
    ap.add_argument("--freezes", type=int, default=2, help="black-and-white freezes to keep")
    ap.add_argument("--no-cta", action="store_true", help="skip the LIKE + SUBSCRIBE card")
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    base = os.path.dirname(os.path.abspath(args.plan))
    src = plan["source"] if os.path.isabs(plan["source"]) else os.path.join(base, plan["source"])
    end_of_stream = media_duration(src) if os.path.exists(src) else float("inf")

    clips = [s for s in plan["segments"] if "clip" in s]
    moments = [s for s in plan["segments"] if "clip" not in s and not s.get("label", "").lower().startswith("cold open")]
    moments.sort(key=lambda s: s["start"])

    # Widen for context, then merge neighbours into one continuous clip.
    merged = []
    for s in moments:
        a, b = max(0.0, s["start"] - args.pad), min(end_of_stream - 0.3, s["end"] + args.pad)
        if merged and a - merged[-1]["end"] < args.merge_gap:
            m = merged[-1]
            m["end"] = max(m["end"], b)
            m["label"] += " + " + s.get("label", "")
            m["_fx"] += s.get("fx", [])
        else:
            merged.append({"label": s.get("label", ""), "start": a, "end": b, "_fx": list(s.get("fx", []))})

    # Accents: a few face zooms and freezes, spread across the video.
    zooms = spread([(i, f) for i, m in enumerate(merged) for f in m["_fx"]
                    if f["type"] == "zoom" and f.get("target", "face") == "face"], args.zooms)
    freezes = spread([(i, f) for i, m in enumerate(merged) for f in m["_fx"]
                      if f["type"] == "freeze" and f.get("text") and "\n" not in f["text"]], args.freezes)
    for m in merged:
        m["fx"] = []
    for i, f in zooms:
        merged[i]["fx"].append({"type": "zoom", "at": f["at"], "dur": min(f.get("dur", 2.0), 2.0),
                                "scale": 1.6, "target": "face"})
    for i, f in freezes:
        merged[i]["fx"].append({"type": "freeze", "at": f["at"], "dur": 1.4, "text": f["text"],
                                "zoom": 1.5, "target": f.get("target", "face"), "look": "bw"})

    if merged and not args.no_cta:
        first = merged[0]
        at = min(first["start"] + 20, first["end"] - 4)
        card = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brand", "subscribe.mov")
        if os.path.exists(card):
            # The animated EffectCraft pop-up (intro/subscribe.jsx): slides in, gets "clicked", slides out.
            card_rel = os.path.relpath(card, base).replace(os.sep, "/")
            first["fx"].append({"type": "overlay", "at": at, "dur": 3.5, "file": card_rel})
            first["fx"].append({"type": "sfx", "at": at + 0.2, "name": "pop_1", "vol": 0.8})
            first["fx"].append({"type": "sfx", "at": at + 1.6, "name": "mouse_click", "vol": 1.0})
        else:
            first["fx"].append({"type": "text", "at": at, "dur": 3, "text": "LIKE + SUBSCRIBE", "pos": "bottom",
                                "color": "#FFD400", "size": 0.07})
            first["fx"].append({"type": "sfx", "at": at, "name": "pop_1", "vol": 0.8})

    segments = []
    for m in merged:
        m.pop("_fx")
        segments.append(m)
    intro = [c for c in clips if "intro" in c.get("label", "").lower()]
    outro = [c for c in clips if "outro" in c.get("label", "").lower()]
    plan["segments"] = intro + segments + outro
    plan["tighten"] = {"min_silence": 2.0, "pad": 0.35, "noise_db": plan.get("tighten", {}).get("noise_db", -34)}

    root, ext = os.path.splitext(args.plan)
    out = args.out or f"{root}-jevmerk{ext}"
    if plan.get("output"):
        r, e = os.path.splitext(plan["output"])
        plan["output"] = f"{r}-jevmerk{e}"
    if plan.get("title"):
        plan["title"] += " (Jev/Merk style)"
    with open(out, "w") as f:
        json.dump(plan, f, indent=2)
    total = sum(m["end"] - m["start"] for m in segments)
    print(f"{out}: {len(segments)} clips, {total / 60:.1f} min before silence cuts, "
          f"{len(zooms)} zooms, {len(freezes)} freezes")


if __name__ == "__main__":
    main()
