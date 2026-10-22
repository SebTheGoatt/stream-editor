# stream-editor

Turns a long gaming stream into a fast, funny YouTube edit: dead air cut out, punch-in zooms on the facecam,
freeze frames, slow-mo, meme captions, sound effects, and curse words bleeped automatically.

Built on open-source tools:
- [FFmpeg](https://github.com/FFmpeg/FFmpeg): all cutting, effects and mixing
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): word-by-word transcript (finds moments, drives the bleeps)
- [auto-editor](https://github.com/WyattBlue/auto-editor): optional rough pass that cuts silence from a whole VOD
- [Anton](https://github.com/googlefonts/AntonFont) font (SIL Open Font License) for captions

## Setup (once)

Needs Python 3.10+ and FFmpeg on your PATH (Windows: `winget install ffmpeg`; Mac: `brew install ffmpeg`).

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python make_sfx.py sfx          # builds the original sound-effect pack
```

## Edit a stream

1. **Get the full-quality file.** YouTube Studio → Content → ⋮ next to the stream → Download. Put it in `work/`.
2. **Transcribe it** (about half the stream's length on a 4-core CPU; much faster with an NVIDIA GPU):
   `python transcribe.py work/stream.mp4 work/transcript.json`
3. **Write or tweak a plan** in `plans/` (see `plans/crafting.json`). Times are seconds in the original stream.
4. **Preview** fast at 540p, then render full quality:
   ```bash
   python edit.py plans/crafting.json --preview
   python edit.py plans/crafting.json --source work/stream.mp4
   ```
   `--only 3,4` renders just those segments while you fine-tune.

## Plan format

```json
{
  "source": "../work/stream.mp4",
  "transcript": "../work/transcript.json",
  "output": "../out/my-video.mp4",
  "facecam": [0.89, 0.54],
  "bleep": true,
  "tighten": {"min_silence": 0.9, "pad": 0.18, "noise_db": -34},
  "segments": [
    {"label": "villager in bed", "start": 1396, "end": 1412, "fx": [ ... ]}
  ]
}
```

`facecam` is where your face sits on screen (0–1 from the left, 0–1 from the top). Each segment's dead air
is trimmed unless you set `"tighten": false`; effect moments are never cut.

| Effect | Fields | What it does |
|---|---|---|
| `text` | `at`, `dur`, `text`, `pos` (top/center/bottom), `color`, `size` | Meme caption that pops in |
| `zoom` | `at`, `dur`, `scale`, `target` (face/center/[x,y]), `shake` | Snap punch-in, then snap back |
| `sfx` | `at`, `name`, `vol` | Plays `sfx/<name>.wav` |
| `freeze` | `at`, `dur`, `text`, `sfx`, `zoom`, `look`, `target` | Freeze frame (black-and-white by default), game audio stops |
| `slowmo` | `at`, `dur`, `factor`, `deep`, `sfx`, `text` | Slow motion; `deep: true` drops the voice pitch too |
| `look` | `at`, `dur`, `look` (bw/deepfry/red/blue) | Color effect |
| `shake` | `at`, `dur`, `scale` | Camera shake |

Sound effects in `sfx/`: boom, ding, scratch, fall, thud, bonk, crickets, sting, whoosh, fail. They're synthesized,
so there is nothing to license. To use your own, drop a `.wav` with the same name (or a new name) in `sfx/`.
Only use sounds you have the rights to; copyrighted meme audio can get a video claimed.

Bleeping uses the word list in `edit.py` (`DEFAULT_BLEEP`); set `"bleep_words": [...]` in a plan to change it.
Speech recognition can miss a word, so listen through before uploading.

## Optional: rough-cut a whole stream

```bash
auto-editor work/stream.mp4 --margin 0.3s -o work/stream_tight.mp4
```

## Channel intro (EffectCraft)

`intro/intro.jsx` builds the animated "SEB THE GOAT" intro with [EffectCraft](https://github.com/storytold/effectcraft)
(free, open source, After Effects-style scripting). Edit the text or colors in the script, then:

```bash
effectcraft-cli script intro/intro.jsx --empty --save-as intro/intro.ecproj
effectcraft-cli render --project intro/intro.ecproj --comp Intro --out intro/intro_raw.mp4 --format h264 --audio off
```

Any finished clip can go in a plan as its own segment: `{"label": "channel intro", "clip": "../intro/intro.mp4"}`.
You can also open `intro.ecproj` in the EffectCraft app to tweak it by hand.
