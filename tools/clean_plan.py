"""Make a "clean" version of an edit plan: just the facecam and gameplay.

Usage: python tools/clean_plan.py plans/cod-mw4.json            # writes plans/cod-mw4-clean.json
       python tools/clean_plan.py plans/cod-mw4.json --no-intro --keep-cold-open

Keeps the same moments in stream order with dead air trimmed, the swear bleeps and the channel
intro/outro. Drops captions, zooms, shake, freeze frames, slow-mo, color looks, sound effects and
music beds (except the music under the intro/outro clips, which have no sound of their own).

Use it when the owner wants a light edit, and for recordings where the game audio drifts out of
sync or the game footage plays fast: speed effects and sounds timed to game events make that worse,
while plain cuts timed to the voice don't.
"""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--out")
    ap.add_argument("--keep-cold-open", action="store_true", help="keep the teaser segment at the start")
    ap.add_argument("--no-intro", action="store_true")
    ap.add_argument("--no-outro", action="store_true")
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    segs = []
    for seg in plan["segments"]:
        label = seg.get("label", "").lower()
        if "clip" in seg:
            if (args.no_intro and "intro" in label) or (args.no_outro and "outro" in label):
                continue
            segs.append(seg)  # intro/outro keep their music: the clips are silent otherwise
            continue
        if label.startswith("cold open") and not args.keep_cold_open:
            continue
        clean = {k: v for k, v in seg.items() if k != "fx"}
        clean["fx"] = []
        segs.append(clean)

    # Plain cuts back to back: start on the intro if there is one.
    intro = [s for s in segs if "clip" in s and "intro" in s.get("label", "").lower()]
    rest = [s for s in segs if s not in intro]
    plan["segments"] = intro + rest

    base, ext = os.path.splitext(args.plan)
    out = args.out or f"{base}-clean{ext}"
    if plan.get("output"):
        root, oext = os.path.splitext(plan["output"])
        plan["output"] = f"{root}-clean{oext}"
    if plan.get("title"):
        plan["title"] += " (clean)"
    with open(out, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"{out}: {len(plan['segments'])} segments, captions/effects removed")


if __name__ == "__main__":
    main()
