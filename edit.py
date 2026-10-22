"""Render a comedic gaming edit from a long stream VOD and a JSON edit plan.

Usage:
    python edit.py plans/crafting.json            # full quality
    python edit.py plans/crafting.json --preview  # fast 540p check

The plan lists segments of the VOD to keep and effects to apply. All times are
seconds in the ORIGINAL VOD, so moments can be copied straight from the
transcript. See plans/crafting.json and README.md for every option.

Per segment the pipeline:
  1. trims long silences (dead air) unless an effect covers them,
  2. splits into pieces: normal playback, slow-mo, and freeze frames,
  3. renders each piece with zoom punch-ins, color looks, screen shake,
     meme captions, sound effects and bleeped curse words,
then joins everything and levels the loudness for YouTube.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "Anton-Regular.ttf")

DEFAULT_BLEEP = [
    "fuck*", "motherf*", "shit*", "bullshit*", "bitch*", "dick", "dicks", "pussy*",
    "nigg*", "cunt*", "fag*", "retard*", "whore*", "slut*", "cock*",
]
LOOKS = {
    "bw": "hue=s=0:enable='{e}'",
    "deepfry": "eq=saturation=3:contrast=1.6:brightness=0.04:enable='{e}',"
               "unsharp=7:7:2.5:enable='{e}',noise=alls=22:allf=t:enable='{e}'",
    "red": "colorchannelmixer=rr=1.2:gg=0.45:bb=0.45:enable='{e}'",
    "blue": "colorchannelmixer=rr=0.6:gg=0.75:bb=1.25:enable='{e}'",
}


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(" ".join(cmd) + "\n" + p.stderr[-3000:])
        raise SystemExit(f"ffmpeg failed (exit {p.returncode})")
    return p


# ---------------------------------------------------------------- planning


def silences(src, a, b, noise_db, min_len):
    """Silent stretches inside [a, b] of the source, in source seconds."""
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", str(a), "-t", str(b - a), "-i", src, "-vn",
         "-af", f"silencedetect=n={noise_db}dB:d={min_len}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    out, start = [], None
    for line in p.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            out.append((a + start, a + float(m.group(1))))
            start = None
    if start is not None:
        out.append((a + start, b))
    return out


def fx_window(fx):
    if fx["type"] == "freeze":
        return fx["at"], fx["at"]
    if fx["type"] == "sfx":
        return fx["at"], fx["at"] + fx.get("dur", 1.0)
    return fx["at"], fx["at"] + fx.get("dur", 1.0)


def keep_ranges(seg, src, cfg):
    """Source ranges of a segment left after cutting dead air."""
    a, b = seg["start"], seg["end"]
    tighten = seg.get("tighten", cfg.get("tighten", {}).get("enabled", True))
    if not tighten:
        return [(a, b)]
    t = cfg.get("tighten", {})
    pad = t.get("pad", 0.18)
    protected = [fx_window(f) for f in seg.get("fx", [])]
    cuts = []
    for s, e in silences(src, a, b, t.get("noise_db", -34), t.get("min_silence", 0.9)):
        s, e = s + pad, e - pad
        if e - s < 0.3:
            continue
        # Never cut through an effect window: shorten the cut around it instead.
        for ps, pe in protected:
            if ps < e and pe > s:
                if ps - s >= e - pe:
                    e = min(e, ps)
                else:
                    s = max(s, pe)
        if e - s >= 0.3:
            cuts.append((s, e))
    ranges, cur = [], a
    for s, e in cuts:
        if s > cur:
            ranges.append((cur, s))
        cur = max(cur, e)
    if cur < b:
        ranges.append((cur, b))
    return [r for r in ranges if r[1] - r[0] > 0.05]


def pieces_for(seg, src, cfg):
    """Split a segment into normal / slow / freeze pieces."""
    slows = sorted((f for f in seg.get("fx", []) if f["type"] == "slowmo"), key=lambda f: f["at"])
    freezes = sorted((f for f in seg.get("fx", []) if f["type"] == "freeze"), key=lambda f: f["at"])
    out = []
    for ra, rb in keep_ranges(seg, src, cfg):
        cuts = [ra]
        for f in slows:
            for x in (f["at"], f["at"] + f["dur"]):
                if ra < x < rb:
                    cuts.append(x)
        for f in freezes:
            if ra < f["at"] < rb:
                cuts.append(f["at"])
        cuts = sorted(set(cuts)) + [rb]
        for x, y in zip(cuts, cuts[1:]):
            if y - x < 0.04:
                continue
            slow = next((f for f in slows if f["at"] <= x + 1e-6 and y <= f["at"] + f["dur"] + 1e-6), None)
            for f in freezes:
                if abs(f["at"] - x) < 1e-6:
                    out.append({"kind": "freeze", "a": x, "fx": f})
            out.append({"kind": "slow" if slow else "normal", "a": x, "b": y, "slow": slow})
        for f in freezes:
            if abs(f["at"] - rb) < 1e-6:
                out.append({"kind": "freeze", "a": rb, "fx": f})
    return out


# ---------------------------------------------------------------- rendering


def target_xy(fx, cfg):
    t = fx.get("target", "face")
    if t == "face":
        return cfg.get("facecam", [0.5, 0.5])
    if t == "center":
        return [0.5, 0.5]
    return t


def zoom_exprs(zooms, W, H):
    """Per-frame zoom factor and crop x/y expressions for scale+crop."""
    if not zooms:
        return None
    z, cx, cy, sh = "1", "0.5", "0.5", "0"
    for la, lb, scale, (tx, ty), shake in reversed(zooms):
        ramp_in = f"min(1,(t-{la:.3f})/0.10)"
        ramp_out = f"min(1,({lb:.3f}-t)/0.08)"
        zf = f"(1+{scale - 1:.3f}*min({ramp_in},{ramp_out}))"
        cond = f"between(t,{la:.3f},{lb:.3f})"
        z = f"if({cond},{zf},{z})"
        cx = f"if({cond},{tx},{cx})"
        cy = f"if({cond},{ty},{cy})"
        if shake:
            sh = f"if({cond},1,{sh})"
    zw = f"(trunc({W}*{z}/2)*2)"
    zh = f"(trunc({H}*{z}/2)*2)"
    amp = round(W * 0.012)
    x = f"min(max({cx}*{zw}-{W / 2}+{amp}*{sh}*sin(t*71),0),{zw}-{W})"
    y = f"min(max({cy}*{zh}-{H / 2}+{amp}*{sh}*cos(t*53),0),{zh}-{H})"
    return zw, zh, x, y


def drawtext(text, la, lb, pos, W, H, tmp, color="white", size=None):
    path = tempfile.NamedTemporaryFile("w", suffix=".txt", dir=tmp, delete=False)
    path.write(text)
    path.close()
    size = size or (0.13 if pos == "center" else 0.095)
    fs = int(H * size)
    # Shrink long lines so they fit: Anton caps run about 0.5 em wide.
    longest = max((len(line) for line in text.split("\n")), default=1)
    fs = min(fs, int(W * 0.92 / (0.5 * max(1, longest))))
    y = {"top": f"{int(H * 0.05)}", "center": "(h-text_h)/2", "bottom": f"h-text_h-{int(H * 0.08)}"}[pos]
    # Pop in: text starts 30% bigger and settles over 0.12 s.
    return (
        f"drawtext=fontfile='{FONT}':textfile='{path.name}':fontcolor={color}:"
        f"fontsize='{fs}*(1+0.3*max(0,1-(t-{la:.3f})/0.12))':"
        f"borderw={max(3, fs // 12)}:bordercolor=black:shadowx=4:shadowy=4:shadowcolor=black@0.6:"
        f"line_spacing={fs // 8}:text_align=C:x=(w-text_w)/2:y={y}:enable='between(t,{la:.3f},{lb:.3f})'"
    )


def bleep_words(transcript, a, b, patterns):
    hits = []
    for seg in transcript.get("segments", []):
        if seg["end"] < a or seg["start"] > b:
            continue
        for w in seg.get("words", []):
            word = re.sub(r"[^a-z]", "", w["w"].lower())
            if word and any(fnmatch.fnmatch(word, p) for p in patterns) and w["e"] > a and w["s"] < b:
                hits.append((max(a, w["s"] - 0.03), min(b, w["e"] + 0.03)))
    return hits


def upscaled_source(seg, ctx):
    """AI-upscale just this segment once (cached) and return (file, offset)."""
    a = max(0.0, seg["start"] - 1.0)
    b = seg["end"] + 1.0
    cache = os.path.join(ctx["cache_dir"], f"{os.path.basename(ctx['src'])}_{a:.2f}_{b:.2f}_{ctx['upscale']}.mp4")
    if not os.path.exists(cache):
        os.makedirs(ctx["cache_dir"], exist_ok=True)
        print(f"  upscaling {a:.1f}-{b:.1f}s with the {ctx['upscale']} model...", flush=True)
        subprocess.run([sys.executable, os.path.join(HERE, "upscale.py"), ctx["src"], cache + ".part.mp4",
                        "--model", ctx["upscale"], "--start", f"{a:.3f}", "--end", f"{b:.3f}"], check=True)
        os.replace(cache + ".part.mp4", cache)
    return cache, a


def render_piece(i, piece, seg, ctx):
    cfg, W, H, fps, tmp = ctx["cfg"], ctx["W"], ctx["H"], ctx["fps"], ctx["tmp"]
    src, sfx_dir = ctx["src"], ctx["sfx_dir"]
    # Seek offset: source time t lives at (t - shift) in the file being read.
    shift = 0.0
    if seg.get("_upscaled"):
        src, shift = seg["_upscaled"]
    out = os.path.join(tmp, f"p{i:04d}.mp4")
    fxs = seg.get("fx", [])
    inputs, vf, af_extra, sfx_list = [], [], [], []

    base_v = f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"

    if piece["kind"] == "freeze":
        f = piece["fx"]
        dur = f.get("dur", 1.5)
        inputs = ["-ss", f"{piece['a'] - shift:.3f}", "-i", src]
        v = f"[0:v]trim=end_frame=1,{base_v},loop=loop=-1:size=1:start=0,trim=duration={dur:.3f},setpts=N/{fps}/TB"
        zooms = [(0.0, dur + 1, f.get("zoom", 1.8), target_xy(f, cfg), f.get("shake", False))] if f.get("zoom", 1.8) > 1 else []
        looks = [(f.get("look", "bw"), 0.0, dur + 1)] if f.get("look", "bw") else []
        texts = [(f["text"], 0.0, dur + 1, f.get("pos", "center"), f.get("color", "white"), f.get("size"))] if f.get("text") else []
        sfx_list = [(f["sfx"], 0.0, f.get("vol", 1.0))] if f.get("sfx") else []
        length = dur
        audio = f"anullsrc=r=48000:cl=stereo,atrim=duration={dur:.3f}"
        speed = None
        a0 = b0 = piece["a"]
    else:
        a0, b0 = piece["a"], piece["b"]
        slow = piece.get("slow")
        speed = slow.get("factor", 0.5) if slow else 1.0
        length = (b0 - a0) / speed
        inputs = ["-ss", f"{a0 - shift:.3f}", "-t", f"{b0 - a0:.3f}", "-i", src]
        v = f"[0:v]setpts=(PTS-STARTPTS)/{speed},{base_v}"

        def loc(t):
            return (t - a0) / speed

        zooms, looks, texts = [], [], []
        for f in fxs:
            fa, fb = fx_window(f)
            if f["type"] == "freeze" or fb <= a0 or fa >= b0:
                continue
            la, lb = max(0.0, loc(fa)), min(length, loc(fb))
            if f["type"] == "zoom":
                zooms.append((la, lb, f.get("scale", 2.2), target_xy(f, cfg), f.get("shake", False)))
            elif f["type"] == "shake":
                zooms.append((la, lb, f.get("scale", 1.12), target_xy({"target": f.get("target", "center")}, cfg), True))
            elif f["type"] == "look":
                looks.append((f["look"], la, lb))
            elif f["type"] == "text":
                texts.append((f["text"], la, lb, f.get("pos", "top"), f.get("color", "white"), f.get("size")))
            elif f["type"] == "slowmo" and f.get("text"):
                texts.append((f["text"], la, lb, f.get("pos", "bottom"), f.get("color", "white"), f.get("size")))
            if f["type"] in ("sfx", "slowmo") and f.get("sfx" if f["type"] == "slowmo" else "name"):
                # A sound fires once, in the piece that contains its start time.
                if a0 <= fa < b0:
                    sfx_list.append((f.get("name") or f.get("sfx"), loc(fa), f.get("vol", 1.0)))
        if slow and slow.get("deep", True):
            audio = f"[0:a]asetpts=PTS-STARTPTS,asetrate=48000*{speed},aresample=48000"
        elif speed != 1.0:
            tempo, chain = speed, []
            while tempo < 0.5:
                chain.append("atempo=0.5")
                tempo /= 0.5
            chain.append(f"atempo={tempo:.4f}")
            audio = "[0:a]asetpts=PTS-STARTPTS,aresample=48000," + ",".join(chain)
        else:
            audio = "[0:a]asetpts=PTS-STARTPTS,aresample=48000"
        audio += ",aformat=sample_rates=48000:channel_layouts=stereo"
        if cfg.get("bleep", True) and ctx["transcript"]:
            hits = [((s - a0) / speed, (e - a0) / speed)
                    for s, e in bleep_words(ctx["transcript"], a0, b0, cfg.get("bleep_words", DEFAULT_BLEEP))]
            if hits:
                gate = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in hits)
                audio += f",volume=0:enable='{gate}'"
                af_extra.append(f"aevalsrc='0.25*sin(2*PI*1000*t)*gt({gate},0)':s=48000:d={length:.3f},aformat=channel_layouts=stereo")

    # Video chain: looks, then camera (zoom/shake), then captions.
    for look, la, lb in looks:
        vf.append(LOOKS[look].format(e=f"between(t,{la:.3f},{lb:.3f})"))
    ze = zoom_exprs(zooms, W, H)
    if ze:
        zw, zh, x, y = ze
        vf.append(f"scale=w='{zw}':h='{zh}':eval=frame:flags=bicubic,crop={W}:{H}:x='{x}':y='{y}'")
    for text, la, lb, pos, color, size in texts:
        vf.append(drawtext(text, la, lb, pos, W, H, tmp, color, size))
    vchain = v + ("," + ",".join(vf) if vf else "") + f",trim=duration={length:.3f},format=yuv420p[v]"

    graph = [vchain]
    if piece["kind"] == "freeze":
        graph.append(f"{audio}[a0]")
    else:
        graph.append(f"{audio},apad,atrim=duration={length:.3f}[a0]")
    mix = ["[a0]"]
    n_in = 1
    for k, chain in enumerate(af_extra):
        graph.append(f"{chain}[x{k}]")
        mix.append(f"[x{k}]")
    for name, at, vol in sfx_list:
        path = os.path.join(sfx_dir, f"{name}.wav")
        if not os.path.exists(path):
            print(f"  ! missing sound effect {name}.wav, skipped", file=sys.stderr)
            continue
        inputs += ["-i", path]
        ms = int(max(0, at) * 1000)
        graph.append(f"[{n_in}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[s{n_in}]")
        mix.append(f"[s{n_in}]")
        n_in += 1
    if len(mix) > 1:
        graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.95,atrim=duration={length:.3f}[a]")
    else:
        graph.append("[a0]anull[a]")

    enc = ctx["enc"]
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph),
         "-map", "[v]", "-map", "[a]", *enc, "-t", f"{length:.3f}", out])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--preview", action="store_true", help="fast 960x540 render for checking timing")
    ap.add_argument("--source", help="override the plan's source video (e.g. the HD download)")
    ap.add_argument("--out", help="override the output path")
    ap.add_argument("--only", help="render only these segment numbers, e.g. 1,4")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--upscale", choices=["general", "anime"],
                    help="AI-upscale each kept segment first (for low-res sources; slow on CPU)")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(args.plan))
    with open(args.plan) as f:
        cfg = json.load(f)

    def rel(p):
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    src = rel(args.source or cfg["source"])
    transcript = {}
    if cfg.get("transcript") and os.path.exists(rel(cfg["transcript"])):
        with open(rel(cfg["transcript"])) as f:
            transcript = json.load(f)
    elif cfg.get("bleep", True):
        print("! no transcript found: curse words will NOT be bleeped (run transcribe.py)", file=sys.stderr)

    W, H = (960, 540) if args.preview else (cfg.get("width", 1920), cfg.get("height", 1080))
    fps = cfg.get("fps", 30)
    enc = (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"] if args.preview
           else ["-c:v", "libx264", "-preset", cfg.get("x264_preset", "medium"), "-crf", str(cfg.get("crf", 18))])
    enc += ["-pix_fmt", "yuv420p", "-r", str(fps), "-video_track_timescale", "90000",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-threads", "2"]

    out = rel(args.out or cfg.get("output", "out/edit.mp4"))
    if args.preview:
        out = re.sub(r"\.mp4$", "", out) + "_preview.mp4"
    os.makedirs(os.path.dirname(out), exist_ok=True)

    segs = cfg["segments"]
    if args.only:
        keep = {int(x) for x in args.only.split(",")}
        segs = [s for n, s in enumerate(segs, 1) if n in keep]

    tmp = tempfile.mkdtemp(prefix="edit_", dir=os.path.dirname(out))
    ctx = {"cfg": cfg, "W": W, "H": H, "fps": fps, "tmp": tmp, "src": src,
           "sfx_dir": rel(cfg.get("sfx_dir", "../sfx")), "transcript": transcript, "enc": enc,
           "upscale": args.upscale, "cache_dir": os.path.join(os.path.dirname(src), "upscaled")}
    jobs = []
    for n, seg in enumerate(segs, 1):
        if args.upscale:
            seg["_upscaled"] = upscaled_source(seg, ctx)
        ps = pieces_for(seg, src, cfg)
        kept = sum((p["b"] - p["a"]) for p in ps if p["kind"] != "freeze")
        print(f"segment {n}: {seg.get('label', '')!s:28} {seg['end'] - seg['start']:5.1f}s -> {kept:5.1f}s kept, {len(ps)} pieces")
        for p in ps:
            jobs.append((len(jobs), p, seg))
    try:
        with ThreadPoolExecutor(args.jobs) as pool:
            files = list(pool.map(lambda j: render_piece(*j, ctx), jobs))
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w") as f:
            f.writelines(f"file '{p}'\n" for p in files)
        joined = os.path.join(tmp, "joined.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", joined])
        # YouTube plays back at about -14 LUFS; level the whole edit to that.
        run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-c:v", "copy",
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-movflags", "+faststart", out])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).stdout)
    print(f"wrote {out} ({dur / 60:.1f} min)")


if __name__ == "__main__":
    main()
