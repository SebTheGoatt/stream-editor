"""Import a sound-effect / music pack into sfx/pack/ with even loudness and short names.

Usage: python tools/import_pack.py "C:/Users/you/Desktop/CoryxKenshin 8-BitRyan FX" [--out sfx/pack]

Every .mp3/.wav/.mp4 found is converted to 48 kHz stereo WAV. Files in a folder named
MUSIC become music_<name>.wav at -24 LUFS (to sit under voices); everything else is a
sound effect at -16 LUFS. Names are simplified: "BOOM meme sound FX.mp3" -> boom_meme.wav.
Plans refer to these names, e.g. {"type": "sfx", "name": "boom_meme"}.

sfx/pack/ is git-ignored on purpose: packs like this are other creators' audio.
"""
import argparse
import os
import re
import subprocess

AUDIO = (".mp3", ".wav", ".m4a", ".ogg", ".mp4")


def slug(filename, music):
    name = filename.rsplit(".", 1)[0]
    name = re.sub(r"\(.*?\)|\[.*?\]|sound ?effects?|sound ?fx|\bfx\b|\bhd\b|192 ?kbps|online video cutter com",
                  "", name, flags=re.I)
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return ("music_" + s) if music else s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sfx", "pack"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    count = 0
    for root, _, files in os.walk(args.pack):
        music = "music" in root.lower().replace("\\", "/").split("/")[-1]
        for f in sorted(files):
            if not f.lower().endswith(AUDIO) or "intro" == f.lower()[:5] or "outro" == f.lower()[:5]:
                continue
            dst = os.path.join(args.out, slug(f, music) + ".wav")
            target = -24 if music else -16
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(root, f), "-vn",
                            "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", dst], check=True)
            print(os.path.basename(dst))
            count += 1
    print(f"{count} sounds -> {args.out}")


if __name__ == "__main__":
    main()
