"""AI-upscale a low-resolution video 4x with Real-ESRGAN's compact models (CPU friendly).

Usage: python upscale.py in.mp4 out.mp4 [--model general|anime] [--start S --end E] [--height 1080]

Only needed when the original file isn't available. Upscaling sharpens edges and
cleans blur, but it can't recover detail that was never recorded, so the
original download from YouTube Studio always looks better.

Models (BSD-3-Clause) from https://github.com/xinntao/Real-ESRGAN:
  general: realesr-general-x4v3   anime: realesr-animevideov3 (good on blocky game art)
"""
import argparse
import os
import subprocess
import sys
import time

import numpy as np
import torch
from torch import nn

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = {"general": ("realesr-general-x4v3.pth", 32), "anime": ("realesr-animevideov3.pth", 16)}


class SRVGGNetCompact(nn.Module):
    """The compact Real-ESRGAN network: plain conv stack + pixel shuffle."""

    def __init__(self, num_conv, num_feat=64, upscale=4):
        super().__init__()
        self.upscale = upscale
        body = [nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        for _ in range(num_conv):
            body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        return out + nn.functional.interpolate(x, scale_factor=self.upscale, mode="nearest")


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip().split(",")
    num, den = out[2].split("/")
    return int(out[0]), int(out[1]), float(num) / float(den)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--model", choices=MODELS, default="anime")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument("--height", type=int, default=1080, help="final height after the 4x pass")
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    torch.set_num_threads(os.cpu_count() or 4)
    name, num_conv = MODELS[args.model]
    net = SRVGGNetCompact(num_conv)
    state = torch.load(os.path.join(HERE, "models", name), map_location="cpu")
    net.load_state_dict(state.get("params", state.get("params_ema", state)))
    net.eval()

    w, h, fps = probe(args.src)
    span = []
    if args.start is not None:
        span += ["-ss", str(args.start)]
    if args.end is not None:
        span += ["-t", str(args.end - (args.start or 0))]
    reader = subprocess.Popen(
        ["ffmpeg", "-v", "error", *span, "-i", args.src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    ow, oh = w * 4, h * 4
    fw = int(round(args.height * ow / oh / 2) * 2)
    writer = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ow}x{oh}", "-r", str(fps),
         "-i", "-", *span, "-i", args.src, "-map", "0:v", "-map", "1:a?",
         "-vf", f"scale={fw}:{args.height}:flags=lanczos", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", args.out],
        stdin=subprocess.PIPE)

    frame_bytes = w * h * 3
    done, t0 = 0, time.time()
    with torch.inference_mode():
        while True:
            frames = []
            for _ in range(args.batch):
                buf = reader.stdout.read(frame_bytes)
                if len(buf) < frame_bytes:
                    break
                frames.append(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
            if not frames:
                break
            x = torch.from_numpy(np.stack(frames)).permute(0, 3, 1, 2).float() / 255.0
            y = net(x).clamp_(0, 1).mul_(255).round_().byte().permute(0, 2, 3, 1).contiguous().numpy()
            writer.stdin.write(y.tobytes())
            done += len(frames)
            if done % (args.batch * 50) == 0:
                print(f"{done} frames, {done / (time.time() - t0):.1f} fps", file=sys.stderr, flush=True)
    writer.stdin.close()
    writer.wait()
    reader.wait()
    print(f"upscaled {done} frames in {time.time() - t0:.0f}s -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
