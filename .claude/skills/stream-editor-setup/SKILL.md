---
name: stream-editor-setup
description: Install and check everything this repo needs (Python venv, FFmpeg, faster-whisper, the sound pack import, optional AI upscaling and EffectCraft), and give OBS recording settings that make editing easier. Use on a new computer, when a tool is missing, or when asked how to record streams for editing.
---

# Set up stream-editor

## Windows (the main editing PC)

From the repo folder in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

It installs Python 3.12 and FFmpeg with winget if missing, creates `.venv`, installs
`requirements.txt`, builds the homemade sounds (`make_sfx.py`) and imports `pack/` into `sfx/pack/`.
After it, close and reopen the terminal so FFmpeg is on PATH, then check:

```powershell
ffmpeg -version
.venv\Scripts\python edit.py plans\test.json --preview
```

## macOS / Linux

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # torch is only for --upscale; skip it if the originals are HD
python make_sfx.py sfx
python tools/import_pack.py pack
```
FFmpeg: `brew install ffmpeg` / `sudo apt install ffmpeg`.

## Optional

- **AI upscaling** (`upscale.py`, only for low-res sources): models are in `models/`. With an NVIDIA GPU,
  install the CUDA build of torch from pytorch.org for a big speed-up. DaVinci Resolve Studio's
  Super Scale is an alternative if Resolve is installed.
- **EffectCraft** (animated titles/intros, `intro/intro.jsx`): download from
  https://github.com/storytold/effectcraft/releases and run `effectcraft-cli` from its `bin/`.
- **Speech-to-text speed**: `transcribe.py --model base.en` is ~3x faster than `small.en` but less accurate on slang.

## OBS settings for streams you plan to edit

- **Record locally** while streaming (Settings → Output → Recording): 1080p or 1440p, 60 fps, MKV with
  "Automatically remux to MP4", NVENC (NVIDIA) or x264 at a high quality setting.
- **Separate audio tracks** (Recording → Audio Track 1–3): 1 = mic, 2 = game, 3 = Discord/voice chat.
  Bleeps can then mute only the speaker's voice and music ducks properly.
- **Keep the facecam in the same corner** every stream so `"facecam"` in plans stays the same.
  For crisp face zooms, the free "Source Record" OBS plugin saves the camera as its own file.
