"""Synthesize an original, royalty-free sound-effect pack with ffmpeg.

Usage: python make_sfx.py [sfx_dir]

Every sound is generated from math, so there is nothing to license. To use a
real sound instead, drop a file with the same name (e.g. sfx/boom.wav) in the
folder; existing files are never overwritten.
"""
import os
import subprocess
import sys

# name: (seconds, aevalsrc expression)
SOUNDS = {
    # Deep "vine boom" style hit: pitch glides down with a long tail.
    "boom": (1.6, "0.95*sin(2*PI*(50*t+90*(1-exp(-t*10))/10))*exp(-t*2.6)"),
    # Bright notification ding with a couple of overtones.
    "ding": (1.4, "0.5*(sin(2*PI*1568*t)+0.5*sin(2*PI*3136*t)+0.25*sin(2*PI*4704*t))*exp(-t*4)"),
    # Record scratch: wobbling pitch plus grit.
    "scratch": (0.55, "0.6*sin(2*PI*(500*t+70*sin(2*PI*11*t)))*exp(-t*3)+0.25*(random(0)*2-1)*exp(-t*6)"),
    # Cartoon falling whistle, 1800 Hz down to 300 Hz.
    "fall": (1.3, "0.45*sin(2*PI*(1800*t-625*t*t))*(1-exp(-t*30))"),
    # Landing thud.
    "thud": (0.5, "0.95*sin(2*PI*58*t)*exp(-t*12)+0.4*(random(0)*2-1)*exp(-t*45)"),
    # Quick bonk for hits and punches.
    "bonk": (0.3, "0.8*sin(2*PI*(700*t-900*t*t))*exp(-t*14)"),
    # Awkward-silence crickets.
    "crickets": (2.6, "0.22*sin(2*PI*4600*t)*gt(sin(2*PI*28*t),0)*lt(mod(t,0.85),0.22)"),
    # Dramatic "dun dun dunnn" sting.
    "sting": (2.4, "0.35*(sin(2*PI*f*t)+0.5*sin(4*PI*f*t)+0.3*sin(6*PI*f*t))*exp(-max(0,t-1.0)*1.6)"
                   "|f=if(lt(t,0.35),146.8,if(lt(t,0.75),138.6,130.8))"),
    # Airy whoosh for transitions.
    "whoosh": (0.6, "0.5*(random(0)*2-1)*pow(sin(PI*t/0.6),2)"),
    # Fail horn: two sad descending notes.
    "fail": (1.6, "0.35*(sin(2*PI*f*t)+0.6*sin(4*PI*f*t)+0.4*sin(6*PI*f*t))*(1-exp(-t*20))*exp(-max(0,t-0.9)*3)"
                  "|f=if(lt(t,0.45),233,196)"),
}


def build(name, seconds, expr, folder):
    path = os.path.join(folder, f"{name}.wav")
    if os.path.exists(path):
        return path
    # "expr|f=..." lets a sound define a helper variable by substitution.
    if "|f=" in expr:
        body, fdef = expr.split("|f=")
        expr = body.replace("f*", f"({fdef})*")
    af = "aformat=channel_layouts=stereo"
    if name == "whoosh":
        af = "highpass=f=500,lowpass=f=5000," + af
    if name in ("boom", "thud"):
        af = "asoftclip=type=tanh," + af
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         f"aevalsrc='{expr}':s=48000:d={seconds}", "-af", af, path],
        check=True,
    )
    return path


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "sfx"
    os.makedirs(folder, exist_ok=True)
    for name, (seconds, expr) in SOUNDS.items():
        print(build(name, seconds, expr, folder))


if __name__ == "__main__":
    main()
