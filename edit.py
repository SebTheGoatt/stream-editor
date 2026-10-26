"""Render a comedic gaming edit from a long stream VOD and a JSON edit plan.

Usage:
    python edit.py plans/crafting.json            # full quality
    python edit.py plans/crafting.json --preview  # fast 540p check

The plan lists segments of the VOD to keep and effects to apply. All times are
seconds in the ORIGINAL VOD, so moments can be copied straight from the
transcript. See plans/crafting.json and README.md for every option.

Per segment the pipeline:
  1. trims long silences (dead air) unless an effect, a laugh or the
     comedic pause before a punchline covers them,
  2. splits into pieces: normal playback, slow-mo, and freeze frames,
  3. renders each piece with zoom punch-ins, color looks, screen shake,
     meme captions, sound effects and bleeped curse words,
then joins everything (with an optional TV-static transition between moments)
and levels the loudness for YouTube.

Caption colors can be palette names ("text", "punch", "win", "danger", "box"),
set per channel with the plan's "palette".
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
# Named caption colors; a plan's "palette" overrides any of them.
PALETTE = {"text": "white", "punch": "#FFD400", "win": "#7CFC00", "danger": "#FF4040", "box": "#E01B24"}


def paint(color, cfg):
    return {**PALETTE, **cfg.get("palette", {})}.get(color, color)


def expand_goat(seg, cfg):
    """A "goat" effect is the channel's signature beat: face punch-in, stamp and goat sound."""
    out = []
    for f in seg.get("fx", []):
        if f["type"] != "goat":
            out.append(f)
            continue
        dur = f.get("dur", 2.6)
        out += [
            {"type": "zoom", "at": f["at"], "dur": dur, "scale": f.get("scale", 2.4), "target": "face",
             "shake": f.get("shake", False)},
            {"type": "text", "at": f["at"], "dur": dur, "text": f.get("text", "GOAT MOMENT"), "pos": "bottom",
             "color": "text", "box": "box"},
            {"type": "sfx", "at": f["at"], "name": cfg.get("goat_sound", "goat"), "vol": f.get("vol", 1.0)},
        ]
    seg["fx"] = out


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(" ".join(cmd) + "\n" + p.stderr[-3000:])
        raise SystemExit(f"ffmpeg failed (exit {p.returncode})")
    return p


# ---------------------------------------------------------------- planning


def silences(src, a, b, noise_db, min_len, cfg=None):
    """Silent stretches inside [a, b] of the source, in source seconds.

    With separate OBS tracks, "silence" means nobody is talking: only the voice tracks (at their
    track_levels) are listened to, so game noise can't hide a pause and quiet talk isn't cut.
    """
    tracks = (cfg or {}).get("audio_tracks") or {}
    voices = [n for n in ("mic", "friends") if n in tracks]
    detect = f"silencedetect=n={noise_db}dB:d={min_len}"
    if voices:
        levels = (cfg or {}).get("track_levels", {})
        parts = ";".join(f"[0:a:{tracks[n]}]volume={levels.get(n, 1.0)}[v{k}]" for k, n in enumerate(voices))
        mixed = "".join(f"[v{k}]" for k in range(len(voices)))
        audio = ["-filter_complex", f"{parts};{mixed}amix=inputs={len(voices)}:normalize=0,{detect}[o]", "-map", "[o]"]
    else:
        audio = ["-vn", "-af", detect]
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", str(a), "-t", str(b - a), "-i", src, *audio, "-f", "null", "-"],
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


# Whisper writes laughter as its own token: (laughs), [LAUGHTER], *Laughing*, Haha!
# Bracketed only, so spoken words like "laugh" or "slaughter" don't count.
LAUGH = re.compile(r"^[\[(*]\s*(laugh|chuckl|giggl)|^(ha){2,}\b", re.I)


def laughs(transcript):
    """Laughs the transcript marked, as (start, end) in source seconds."""
    return [(w["s"], w["e"]) for s in transcript.get("segments", []) for w in s.get("words", [])
            if LAUGH.search(w["w"])]


def without_holes(ranges, holes):
    """ranges minus holes, both lists of (start, end)."""
    for hs, he in holes:
        ranges = [piece for s, e in ranges
                  for piece in ((s, min(e, hs)), (max(s, he), e)) if piece[1] - piece[0] > 0.05]
    return ranges


def keep_ranges(seg, src, cfg, laugh_marks=()):
    """Source ranges of a segment left after cutting dead air and any lines the plan cuts out."""
    holes = [tuple(c) for c in seg.get("cuts", [])]
    return without_holes(tightened(seg, src, cfg, laugh_marks), holes)


def tightened(seg, src, cfg, laugh_marks):
    a, b = seg["start"], seg["end"]
    tighten = seg.get("tighten", cfg.get("tighten", {}).get("enabled", True))
    if not tighten:
        return [(a, b)]
    t = cfg.get("tighten", {})
    pad = t.get("pad", 0.18)
    # Music beds run under the cut, so they don't stop dead air from being trimmed.
    protected = [fx_window(f) for f in seg.get("fx", []) if f["type"] != "music"]
    # Comedic timing is not dead air: the beat before a punchline (zoom/freeze), and a laugh with
    # the pause that sets it up and its tail.
    pause = t.get("comic_pause", 0.8)
    protected += [(f["at"] - pause, f["at"]) for f in seg.get("fx", []) if f["type"] in ("zoom", "freeze")]
    if t.get("keep_laughs", True):
        protected += [(s - pause, e + 0.6) for s, e in laugh_marks if s < b and e > a]
    cuts = []
    for s, e in silences(src, a, b, t.get("noise_db", -34), t.get("min_silence", 0.9), cfg):
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


def pieces_for(seg, src, cfg, laugh_marks=()):
    """Split a segment into normal / slow / freeze pieces."""
    if "clip" in seg:
        return [{"kind": "clip", "a": 0.0, "b": 0.0}]
    slows = sorted((f for f in seg.get("fx", []) if f["type"] == "slowmo"), key=lambda f: f["at"])
    freezes = sorted((f for f in seg.get("fx", []) if f["type"] == "freeze"), key=lambda f: f["at"])
    out = []
    for ra, rb in keep_ranges(seg, src, cfg, laugh_marks):
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
            if y - x < 0.25:  # slivers between cuts are invisible and can stall ffmpeg
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


def layout_filter(cfg):
    """Rebuild the picture from a raw OBS recording, per piece: game full-frame, webcam inset.

    Plan option "layout" (all in source/output pixels), e.g. for a 3840x1080 webcam|game recording:
      {"game": [1920, 0, 1920, 1080], "cam": [0, 0, 1920, 1080],
       "cam_size": [568, 320], "cam_pos": [1324, 732], "border": 4}
    or, for vertical Shorts, regions of the source stacked top to bottom:
      {"stack": [{"crop": [127, 0, 1666, 1080], "size": [1080, 700]},
                 {"crop": [2402, 0, 956, 1080], "size": [1080, 1220]}]}
    Only the kept moments get rebuilt, so there is no full-length intermediate file to make.
    """
    lay = cfg.get("layout")
    if not lay:
        return ""
    if "stack" in lay:
        parts = lay["stack"]
        ins = "".join(f"[ls{i}]" for i in range(len(parts)))
        outs = "".join(f"[lo{i}]" for i in range(len(parts)))
        crops = ";".join(f"[ls{i}]crop={p['crop'][2]}:{p['crop'][3]}:{p['crop'][0]}:{p['crop'][1]},"
                         f"scale={p['size'][0]}:{p['size'][1]}:flags=lanczos,setsar=1[lo{i}]"
                         for i, p in enumerate(parts))
        return f"split={len(parts)}{ins};{crops};{outs}vstack=inputs={len(parts)},"
    gx, gy, gw, gh = lay["game"]
    cx, cy, cw, ch = lay["cam"]
    w, h = lay["cam_size"]
    x, y = lay["cam_pos"]
    b = lay.get("border", 4)
    return (f"split[lg][lc];[lg]crop={gw}:{gh}:{gx}:{gy}[lgame];"
            f"[lc]crop={cw}:{ch}:{cx}:{cy},scale={w}:{h},pad={w + 2 * b}:{h + 2 * b}:{b}:{b}:"
            f"{lay.get('border_color', 'white')}[lcam];[lgame][lcam]overlay={x - b}:{y - b},")


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


def ff_path(p):
    """A file path that survives FFmpeg filter parsing, including Windows drive letters."""
    return p.replace("\\", "/").replace(":", "\\:")


def drawtext(text, la, lb, pos, W, H, tmp, color="white", size=None, box=None):
    path = tempfile.NamedTemporaryFile("w", suffix=".txt", dir=tmp, delete=False)
    path.write(text)
    path.close()
    size = size or {"center": 0.13, "corner": 0.06, "subs": 0.06}.get(pos, 0.095)
    fs = int(H * size)
    # Shrink long lines so they fit: Anton caps run about 0.5 em wide.
    longest = max((len(line) for line in text.split("\n")), default=1)
    fs = min(fs, int(W * 0.92 / (0.5 * max(1, longest))))
    y = {"top": f"{int(H * 0.05)}", "center": "(h-text_h)/2", "bottom": f"h-text_h-{int(H * 0.08)}",
         "corner": f"{int(H * 0.05)}", "subs": f"{int(H * 0.62)}"}[pos]
    # Counters sit in the top-left corner; everything else is centered.
    x = f"{int(W * 0.03)}" if pos == "corner" else "(w-text_w)/2"
    boxed = f"box=1:boxcolor={box}@0.9:boxborderw={max(6, fs // 4)}:" if box else ""
    # Pop in: text starts 30% bigger and settles over 0.12 s.
    return (
        f"drawtext=fontfile='{ff_path(FONT)}':textfile='{ff_path(path.name)}':fontcolor={color}:"
        f"fontsize='{fs}*(1+0.3*max(0,1-(t-{la:.3f})/0.12))':{boxed}"
        f"borderw={max(3, fs // 12)}:bordercolor=black:shadowx=4:shadowy=4:shadowcolor=black@0.6:"
        f"line_spacing={fs // 8}:text_align=C:x={x}:y={y}:enable='between(t,{la:.3f},{lb:.3f})'"
    )


def bleep_words(transcript, a, b, patterns, track=None):
    """Swear spans in [a, b]. With track, only words from that voice (or untagged words) count."""
    hits = []
    for seg in transcript.get("segments", []):
        if seg["end"] < a or seg["start"] > b:
            continue
        for w in seg.get("words", []):
            if track and w.get("track", seg.get("track")) not in (None, track):
                continue
            word = re.sub(r"[^a-z]", "", w["w"].lower())
            # Whisper sometimes stamps a word with zero length; still bleep a whole word's worth.
            ws, we = w["s"], max(w["e"], w["s"] + 0.4)
            if word and any(fnmatch.fnmatch(word, p) for p in patterns) and we > a and ws < b:
                hits.append((max(a, ws - 0.08), min(b, we + 0.05)))
    return hits


def caption_chunks(transcript, a, b, patterns, max_words=3):
    """Word-by-word captions for Shorts: (TEXT, start, end) chunks of up to max_words in [a, b].

    A chunk breaks early on a pause or at the end of a sentence. Bleeped words are starred out.
    """
    # In time order: with separate voice tracks, two people's words interleave.
    words = sorted((w for seg in transcript.get("segments", []) for w in seg.get("words", [])
                    if a <= w["s"] < b and not LAUGH.search(w["w"]) and not w["w"].startswith(("[", "(", "*", "♪"))),
                   key=lambda w: w["s"])
    chunks, cur = [], []
    for i, w in enumerate(words):
        bare = re.sub(r"[^a-z]", "", w["w"].lower())
        text = w["w"].upper()
        if bare and any(fnmatch.fnmatch(bare, p) for p in patterns):
            text = text[0] + "*" * (len(text) - 1)
        cur.append((text, w["s"], w["e"]))
        nxt = words[i + 1] if i + 1 < len(words) else None
        if len(cur) == max_words or not nxt or nxt["s"] - w["e"] > 0.4 or w["w"][-1:] in ".?!":
            chunks.append(cur)
            cur = []
    out = []
    for i, c in enumerate(chunks):
        # Hold each chunk until the next one starts (or a beat after its last word), never past b.
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else c[-1][2] + 0.25
        out.append((" ".join(t for t, _, _ in c), c[0][1], min(b, max(end, c[-1][2]))))
    return out


def find_sound(sfx_dir, name):
    """sfx/<name>.wav, falling back to a dropped-in pack in sfx/pack/."""
    for path in (os.path.join(sfx_dir, f"{name}.wav"), os.path.join(sfx_dir, "pack", f"{name}.wav")):
        if os.path.exists(path):
            return path
    return None


def piece_length(piece, seg):
    if piece["kind"] == "clip":
        return seg["_clip_dur"]
    if piece["kind"] == "static":
        return seg["_dur"]
    if piece["kind"] == "freeze":
        return piece["fx"].get("dur", 1.5)
    speed = piece["slow"].get("factor", 0.5) if piece.get("slow") else 1.0
    return (piece["b"] - piece["a"]) / speed


def music_cues(jobs):
    """Place each music bed on the finished timeline: (name, start, dur, vol)."""
    cues, t = [], 0.0
    for _, piece, seg in jobs:
        for f in seg.get("fx", []):
            if f["type"] != "music":
                continue
            if piece["kind"] == "clip":
                local = f["at"]
            elif piece["kind"] != "freeze" and piece["a"] <= f["at"] < piece["b"]:
                speed = piece["slow"].get("factor", 0.5) if piece.get("slow") else 1.0
                local = (f["at"] - piece["a"]) / speed
            else:
                continue
            cues.append((f["name"], t + local, f.get("dur", 8.0), f.get("vol", 0.5)))
        t += piece_length(piece, seg)
    return cues


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
    inputs, vf, af_extra, sfx_list, overlays = [], [], [], [], []

    base_v = f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"

    if piece["kind"] == "clip":
        # A finished clip (e.g. the EffectCraft intro): just match the edit's format.
        run(["ffmpeg", "-v", "error", "-y", "-i", seg["_clip_path"], "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-filter_complex", f"[0:v]{base_v},format=yuv420p[v];[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a]"
             if seg.get("_clip_has_audio") else
             f"[0:v]{base_v},format=yuv420p[v];[1:a]atrim=duration={seg['_clip_dur']:.3f}[a]",
             "-map", "[v]", "-map", "[a]", *ctx["enc"], "-t", f"{seg['_clip_dur']:.3f}", out])
        return out

    if piece["kind"] == "static":
        # TV-static transition between moments, tinted to match the channel intro.
        dur = seg["_dur"]
        run(["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i", f"color=c=0x707070:s={W}x{H}:r={fps}:d={dur:.3f}",
             "-f", "lavfi", "-i", f"anoisesrc=d={dur:.3f}:c=pink:a=0.3",
             "-filter_complex",
             "[0:v]noise=alls=100:allf=t+u,hue=s=0,colorchannelmixer=rr=1.15:gg=0.22:bb=0.22,format=yuv420p[v];"
             f"[1:a]highpass=f=300,afade=t=in:d=0.03,afade=t=out:st={max(0, dur - 0.08):.3f}:d=0.08,"
             "aformat=sample_rates=48000:channel_layouts=stereo[a]",
             "-map", "[v]", "-map", "[a]", *ctx["enc"], "-t", f"{dur:.3f}", out])
        return out

    if piece["kind"] == "freeze":
        f = piece["fx"]
        dur = f.get("dur", 1.5)
        # A freeze at the very end of the recording would seek past the last frame.
        at = min(piece["a"], ctx["src_dur"] - 0.2)
        inputs = ["-ss", f"{at - shift:.3f}", "-i", src]
        v = (f"[0:v]{layout_filter(cfg)}trim=end_frame=1,{base_v},loop=loop=-1:size=1:start=0,"
             f"trim=duration={dur:.3f},setpts=N/{fps}/TB")
        zooms = [(0.0, dur + 1, f.get("zoom", 1.8), target_xy(f, cfg), f.get("shake", False))] if f.get("zoom", 1.8) > 1 else []
        looks = [(f.get("look", "bw"), 0.0, dur + 1)] if f.get("look", "bw") else []
        texts = [(f["text"], 0.0, dur + 1, f.get("pos", "center"), paint(f.get("color", "white"), cfg), f.get("size"),
                  paint(f["box"], cfg) if f.get("box") else None)] if f.get("text") else []
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
        v = f"[0:v]{layout_filter(cfg)}setpts=(PTS-STARTPTS)/{speed},{base_v}"

        def loc(t):
            return (t - a0) / speed

        zooms, looks, texts = [], [], []
        for f in fxs:
            fa, fb = fx_window(f)
            if f["type"] == "freeze" or fb <= a0 or fa >= b0:
                continue
            la, lb = max(0.0, loc(fa)), min(length, loc(fb))
            if f["type"] == "overlay":
                # A transparent clip (e.g. the EffectCraft subscribe pop-up), picked up where this piece starts.
                inputs += ["-ss", f"{max(0.0, a0 - fa):.3f}", "-i", f["_path"]]
                overlays.append((len(overlays) + 1, la, lb, f))
                continue
            if f["type"] == "zoom":
                zooms.append((la, lb, f.get("scale", 2.2), target_xy(f, cfg), f.get("shake", False)))
            elif f["type"] == "shake":
                zooms.append((la, lb, f.get("scale", 1.12), target_xy({"target": f.get("target", "center")}, cfg), True))
            elif f["type"] == "look":
                looks.append((f["look"], la, lb))
            elif f["type"] == "text":
                texts.append((f["text"], la, lb, f.get("pos", "top"), paint(f.get("color", "white"), cfg), f.get("size"),
                              paint(f["box"], cfg) if f.get("box") else None))
            elif f["type"] == "slowmo" and f.get("text"):
                texts.append((f["text"], la, lb, f.get("pos", "bottom"), paint(f.get("color", "white"), cfg),
                              f.get("size"), None))
            elif f["type"] == "counter":
                # Running tally (DEATHS: 3) that pops up in the corner whenever it changes.
                texts.append((f["text"], la, lb, "corner", paint(f.get("color", "text"), cfg), f.get("size"),
                              paint(f.get("box", "box"), cfg)))
            sound = f.get("name") if f["type"] == "sfx" else f.get("sfx") if f["type"] in ("slowmo", "counter") else None
            if sound and a0 <= fa < b0:
                # A sound fires once, in the piece that contains its start time.
                sfx_list.append((sound, loc(fa), f.get("vol", 1.0)))
        if cfg.get("subtitles") and ctx["transcript"]:
            # Shorts-style captions: every word on screen, a few at a time.
            for text, s, e in caption_chunks(ctx["transcript"], a0, b0, cfg.get("bleep_words", DEFAULT_BLEEP)):
                texts.append((text, loc(s), min(length, loc(e)), "subs", paint("text", cfg), None, None))
        if slow and slow.get("deep", True):
            retime = f"asetpts=PTS-STARTPTS,asetrate=48000*{speed},aresample=48000"
        elif speed != 1.0:
            tempo, chain = speed, []
            while tempo < 0.5:
                chain.append("atempo=0.5")
                tempo /= 0.5
            chain.append(f"atempo={tempo:.4f}")
            retime = "asetpts=PTS-STARTPTS,aresample=48000," + ",".join(chain)
        else:
            retime = "asetpts=PTS-STARTPTS,aresample=48000"
        # A recording with separate OBS tracks ("audio_tracks": {"mic": 1, "game": 2, "friends": 3})
        # is mixed here, so a bleep mutes only the voice that swore and the game keeps playing.
        tracks = cfg.get("audio_tracks")
        voices = [n for n in ("mic", "friends", "game") if n in tracks] if tracks else [None]
        chains, all_hits = [], []
        for n in voices:
            chain = f"[0:a:{tracks[n]}]" if n else "[0:a]"
            chain += retime + ",aformat=sample_rates=48000:channel_layouts=stereo"
            if cfg.get("bleep", True) and ctx["transcript"] and n != "game":
                # Plus any extra bleeps the plan lists: swears a second transcription pass caught.
                spans = bleep_words(ctx["transcript"], a0, b0, cfg.get("bleep_words", DEFAULT_BLEEP), n)
                spans += [(max(a0, x[0]), min(b0, x[1])) for x in cfg.get("bleeps", [])
                          if x[1] > a0 and x[0] < b0 and (len(x) < 3 or x[2] == n)]
                hits = [((s - a0) / speed, (e - a0) / speed) for s, e in spans]
                if hits:
                    chain += ",volume=0:enable='" + "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in hits) + "'"
                    all_hits += hits
            if n:
                chain += f",volume={cfg.get('track_levels', {}).get(n, 1.0)}"
                # Optional per-voice processing, e.g. compress and limit a quiet mic after boosting it.
                if cfg.get("track_filters", {}).get(n):
                    chain += "," + cfg["track_filters"][n]
            chains.append(chain)
        if len(chains) == 1:
            audio = chains[0]
        else:
            audio = (";".join(f"{c}[v{k}]" for k, c in enumerate(chains)) + ";"
                     + "".join(f"[v{k}]" for k in range(len(chains))) + f"amix=inputs={len(chains)}:normalize=0")
        if all_hits and cfg.get("bleep_sound"):
            # A sound effect over each muted swear instead of the beep (Seb's: a duck quack).
            sfx_list += [(cfg["bleep_sound"], s, cfg.get("bleep_volume", 1.0)) for s, _ in all_hits]
        elif all_hits:
            gate = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in all_hits)
            af_extra.append(f"aevalsrc='0.25*sin(2*PI*1000*t)*gt({gate},0)':s=48000:d={length:.3f},aformat=channel_layouts=stereo")

    # Video chain: looks, then camera (zoom/shake), then captions.
    for look, la, lb in looks:
        vf.append(LOOKS[look].format(e=f"between(t,{la:.3f},{lb:.3f})"))
    ze = zoom_exprs(zooms, W, H)
    if ze:
        zw, zh, x, y = ze
        vf.append(f"scale=w='{zw}':h='{zh}':eval=frame:flags=bicubic,crop={W}:{H}:x='{x}':y='{y}'")
    for text, la, lb, pos, color, size, box in texts:
        vf.append(drawtext(text, la, lb, pos, W, H, tmp, color, size, box))
    vchain = v + ("," + ",".join(vf) if vf else "") + f",trim=duration={length:.3f}"

    if not overlays:
        graph = [vchain + ",format=yuv420p[v]"]
    else:
        graph = [vchain + "[vb0]"]
        for j, (idx, la, lb, f) in enumerate(overlays):
            w = int(W * f.get("width", 1.0)) // 2 * 2
            x, y = f.get("x", 0.5), f.get("y", 0.5)
            graph.append(f"[{idx}:v]format=rgba,scale={w}:-2,setpts=PTS-STARTPTS+{la:.3f}/TB[ov{j}]")
            graph.append(f"[vb{j}][ov{j}]overlay=x='{x}*W-w/2':y='{y}*H-h/2':eof_action=pass:"
                         f"enable='between(t,{la:.3f},{lb:.3f})'[vb{j + 1}]")
        graph.append(f"[vb{len(overlays)}]format=yuv420p[v]")
    if piece["kind"] == "freeze":
        graph.append(f"{audio}[a0]")
    else:
        graph.append(f"{audio},apad,atrim=duration={length:.3f}[a0]")
    mix = ["[a0]"]
    n_in = 1 + len(overlays)
    for k, chain in enumerate(af_extra):
        graph.append(f"{chain}[x{k}]")
        mix.append(f"[x{k}]")
    for name, at, vol in sfx_list:
        path = find_sound(sfx_dir, name)
        if not path:
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
    # The graph goes in a file: word-by-word captions can outgrow Windows' 32K command-line limit.
    script = os.path.join(tmp, f"p{i:04d}_graph.txt")
    with open(script, "w", encoding="utf-8") as f:
        f.write(";".join(graph))
    run(["ffmpeg", "-v", "error", "-y", *inputs, graph_file_option(), script,
         "-map", "[v]", "-map", "[a]", *enc, "-t", f"{length:.3f}", out])
    return out


_GRAPH_OPT = None


def graph_file_option():
    """FFmpeg 7+ reads a filter graph from a file with -/filter_complex; FFmpeg 6 uses -filter_complex_script."""
    global _GRAPH_OPT
    if _GRAPH_OPT is None:
        first = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split("\n", 1)[0]
        m = re.search(r"version n?(\d+)\.", first)
        _GRAPH_OPT = "-filter_complex_script" if m and int(m.group(1)) < 7 else "-/filter_complex"
    return _GRAPH_OPT


def main():
    # Progress lines reach a log file as they happen, so a render can be tracked live.
    sys.stdout.reconfigure(line_buffering=True)
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

    W, H = cfg.get("width", 1920), cfg.get("height", 1080)
    if args.preview:
        W, H = W // 2, H // 2
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
           "upscale": args.upscale, "cache_dir": os.path.join(os.path.dirname(src), "upscaled"),
           "src_dur": float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", src]).stdout)}
    jobs = []
    laugh_marks = laughs(transcript)
    transition = cfg.get("transition")
    after_moment = False
    for n, seg in enumerate(segs, 1):
        if "clip" in seg:
            seg["_clip_path"] = rel(seg["clip"])
            seg["_clip_has_audio"] = bool(run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                               "stream=index", "-of", "csv=p=0", seg["_clip_path"]]).stdout.strip())
            seg["_clip_dur"] = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", seg["_clip_path"]]).stdout)
            print(f"segment {n}: {seg.get('label', 'clip')!s:28} inserted clip {seg['clip']}")
            jobs.append((len(jobs), pieces_for(seg, src, cfg)[0], seg))
            after_moment = False
            continue
        expand_goat(seg, cfg)
        for f in seg.get("fx", []):
            if f["type"] == "overlay":
                f["_path"] = rel(f["file"])
        # Static only goes between two moments: never next to the intro or outro clips.
        if transition and after_moment and seg.get("transition", True):
            jobs.append((len(jobs), {"kind": "static", "a": 0.0, "b": 0.0},
                         {"label": "transition", "fx": [], "_dur": transition.get("dur", 0.35)}))
        after_moment = True
        if args.upscale:
            seg["_upscaled"] = upscaled_source(seg, ctx)
        ps = pieces_for(seg, src, cfg, laugh_marks)
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
        # Music beds: mixed over the finished cut and ducked under voices.
        inputs, graph, mix = ["-i", joined], [], []
        for k, (name, start, dur, vol) in enumerate(music_cues(jobs), 1):
            path = find_sound(ctx["sfx_dir"], name)
            if not path:
                print(f"  ! missing music {name}.wav, skipped", file=sys.stderr)
                continue
            inputs += ["-i", path]
            ms = int(start * 1000)
            graph.append(f"[{k}:a]atrim=duration={dur:.3f},afade=t=in:d=0.3,afade=t=out:st={max(0, dur - 0.8):.3f}:d=0.8,"
                         f"volume={vol},adelay={ms}|{ms}[m{k}]")
            mix.append(f"[m{k}]")
        # YouTube plays back at about -14 LUFS; level the whole edit to that.
        level = "loudnorm=I=-14:TP=-1.5:LRA=11"
        if mix:
            graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0[mus]")
            graph.append("[0:a]asplit=2[main][key]")
            graph.append("[mus][key]sidechaincompress=threshold=0.04:ratio=5:attack=20:release=350[duck]")
            graph.append(f"[main][duck]amix=inputs=2:normalize=0:duration=first,{level}[a]")
            amap = ["-filter_complex", ";".join(graph), "-map", "0:v", "-map", "[a]"]
        else:
            amap = ["-af", level]
        run(["ffmpeg", "-v", "error", "-y", *inputs, *amap, "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).stdout)
    print(f"wrote {out} ({dur / 60:.1f} min)")
    write_chapters(jobs, out, dur)


def write_chapters(jobs, out, dur):
    """YouTube chapters for the description: where each moment starts in the finished video.

    A segment's "chapter" names it (default: its label). YouTube needs the first at 0:00, at least
    three, and each 10 s or longer, so moments that start within 10 s of the last one are folded in.
    """
    marks, t, last = [], 0.0, None
    for _, piece, seg in jobs:
        if seg is not last and "clip" not in seg and seg.get("label") != "transition":
            name = seg.get("chapter", seg.get("label", ""))
            if not marks or (t - marks[-1][0] >= 10 and dur - t >= 10):
                marks.append((t, name[:1].upper() + name[1:]))
        last = seg
        t += piece_length(piece, seg)
    if len(marks) < 3:
        return
    marks[0] = (0.0, marks[0][1])
    stamp = lambda s: (f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}" if dur >= 3600  # noqa: E731
                       else f"{int(s // 60)}:{int(s % 60):02d}")
    path = re.sub(r"\.mp4$", "", out) + "_chapters.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(f"{stamp(s)} {name}\n" for s, name in marks)
    print(f"chapters -> {path}")


if __name__ == "__main__":
    main()
