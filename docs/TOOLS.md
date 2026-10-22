# Every tool used, and what it's for

## In the editing pipeline

| Tool | What it does here | Where | License |
|---|---|---|---|
| [FFmpeg](https://ffmpeg.org) | All cutting, zooms, freeze frames, slow-mo, color looks, captions, mixing, bleeps, loudness | `edit.py` | LGPL/GPL |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Word-by-word transcript: finds moments, times captions, finds curse words to bleep | `transcribe.py` | MIT |
| [auto-editor](https://github.com/WyattBlue/auto-editor) | Optional rough cut of silence across a whole VOD (`edit.py` trims dead air itself per segment) | README | Unlicense |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) compact models + [PyTorch](https://pytorch.org) | AI 4x upscaling when only a low-res copy exists | `upscale.py`, `models/` | BSD-3 |
| [EffectCraft](https://github.com/storytold/effectcraft) | Scripted motion graphics; built the alternate animated intro, rendered headless | `intro/intro.jsx` | MIT / Apache-2.0 |
| [Anton](https://github.com/googlefonts/AntonFont) font | Meme captions | `fonts/` | SIL OFL |
| Homemade sound effects | Boom, ding, scratch, fall, thud, bonk, crickets, sting, whoosh, fail, synthesized with FFmpeg | `make_sfx.py`, `sfx/` | original |
| CoryxKenshin 8-BitRyan FX pack | Real meme sounds and music beds (bought by the channel owner) | `pack/` → `tools/import_pack.py` | purchased pack |

## Helpers

| Tool | Use |
|---|---|
| `tools/find_moments.py` | Read/search the transcript, exact word times, loudest moments |
| `tools/contact_sheet.py` | Timestamped frame grid to find deaths/kills and to review a finished edit |
| `tools/import_pack.py` | Convert any sound pack into `sfx/pack/` with even loudness and short names |
| `tools/vizard.py` | Vizard.ai API: long video to ranked vertical Shorts, AI captions/titles, scheduled publishing (needs a paid plan + `VIZARDAI_API_KEY`) |

## Used while building this (outside the repo)

| Tool | Use |
|---|---|
| vidIQ (Claude connector) | Pulled the stream info, a scene-by-scene breakdown to shortlist moments, and short clips. Its downloads were only 144p, which is why originals matter |
| yt-dlp | Tried for HD downloads; YouTube blocks cloud servers, so download originals from YouTube Studio instead |
| gdown | Downloaded the sound pack from Google Drive |
| [FilmCraft](https://github.com/storytold/filmcraft) | Looked at as a free editor; not needed for the automated pipeline |
| DaVinci Resolve Studio | Final polish on the owner's PC (Voice Isolation, color, Super Scale, export) |

## Claude skills in this repo

| Skill | When |
|---|---|
| `.claude/skills/coryxkenshin-edit` | Edit a stream into a CoryxKenshin-style video, start to finish |
| `.claude/skills/stream-editor-setup` | Install everything on a new computer; OBS recording settings |
| `.claude/skills/using-vizard-api` | Shorts, captions and publishing through Vizard.ai |
