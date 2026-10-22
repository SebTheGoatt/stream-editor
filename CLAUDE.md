# stream-editor: notes for Claude

Seb The Goat's tool for turning gaming streams into CoryxKenshin-style YouTube edits.

- Editing a stream: use the `coryxkenshin-edit` skill. New computer or missing tools: `stream-editor-setup`.
- Pipeline: `transcribe.py` (word timings) → plan in `plans/*.json` → `edit.py` (render) → listen-through.
- Helpers: `tools/find_moments.py`, `tools/contact_sheet.py`, `tools/import_pack.py`. Every tool used and
  why is in `docs/TOOLS.md`.
- Sounds: `sfx/*.wav` are homemade; `sfx/pack/` is generated from `pack/` by `tools/import_pack.py`
  (git-ignored because it is ~1.2 GB of WAV).
- Branding: `brand/intro.mp4` (TV static "SEB THE GOAT", nearly silent: add music under it) and
  `brand/outro.mp4` (end screen, no audio). `intro/` holds an alternate EffectCraft intro.
- `work/` and `out/` are git-ignored: recordings, transcripts and renders never get committed.
- Style: promote the funny moments, keep captions short, never keep a slur moment, always remind the
  owner to listen once before uploading (bleeps can miss) and that borrowed music can get claimed.
- The owner records in OBS on Windows and has DaVinci Resolve Studio; final polish can happen there.
