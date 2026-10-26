# stream-editor: notes for Claude

Seb The Goat's tool for turning gaming streams into CoryxKenshin-style YouTube edits.

- Editing a stream: use the `sebthegoat-edit` skill (the channel's own style, built on `coryxkenshin-edit`'s
  rules). Only use plain `coryxkenshin-edit` when Cory-heavy editing is asked for. New computer or missing
  tools: `stream-editor-setup`.
  Shorts, captions, publishing: `using-vizard-api` (`tools/vizard.py`; key in `VIZARDAI_API_KEY`, never in chat
  or git; publishing needs the owner's explicit yes).
- **Owner's chosen style (Oct 25, 2026): FaZe Jev / M3RKMUS1C.** Long continuous clips, hard cuts, voice up front,
  no captions/meme sounds/music under gameplay, 3-4 face snap-zooms and 1-2 B&W freezes per video, one
  LIKE + SUBSCRIBE card. Make the full plan, then `python tools/jev_merk_plan.py plans/<name>.json` and render
  the `-jevmerk` plan. Not CoryxKenshin-style overkill. The subscribe card is `brand/subscribe.mov` (EffectCraft,
  `intro/subscribe.jsx`), used as an `overlay` effect.
  From the owner's reference videos (Jev "IfwS8Wl3_rI", Merk "ZJ2O5PYuBYw", Oct 2026): open with a ~60-75 s fast
  highlight montage (4-5 s hits, punch zooms, "LEAVE A LIKE FOR MORE <GAME> :)" along the bottom for ~12 s), then
  the TV-static brand intro as the glitch transition, then long commentary clips. `jev_merk_plan.py --montage`
  builds it (default 75 s; plan `"game"` names the game). Lead the montage with the strongest action/punchline,
  not a menu.
- **Polish in Resolve:** `python tools/export_timeline.py plans/<name>.json --source <HD original>` writes an FCP 7 XML
  timeline (File > Import > Timeline in Resolve) plus FCPXML/OTIO/EDL/FilmCraft project, built with FilmCraft's CLI
  (`FILMCRAFT_CLI` or on PATH). Effects and bleeps come in as colored markers.
- **Earlier preference: no over-editing.** Default to a clean edit: facecam + gameplay, the best
  moments with dead air cut, bleeps, intro/outro, and nothing else. Make a full plan, then
  `python tools/clean_plan.py plans/<name>.json` and render the `-clean` plan. Only add captions, zooms,
  freezes, sounds or music when the owner asks for them.
- **Voices over the game (owner, Oct 26 2026):** mic and Discord must sit ~10 dB above the game. Seb's OBS
  tracks record very quiet (mic peaks around -24 dBFS), so for 4-track recordings use
  `"track_levels": {"mic": 7.0, "friends": 5.6, "game": 0.8}` and
  `"track_filters"` with `acompressor=threshold=0.1:ratio=3:attack=5:release=150,alimiter=limit=0.89` on mic and
  friends; measure with ebur128 per track and adjust if a new recording is louder. Silence trimming listens to
  the voice tracks only (`tighten.noise_db` -35).
- **Recordings may play fast or have game audio out of sync.** Don't try to fix it, don't add slow-mo or
  speed changes, and time cuts and anything else to the voice, not to game sounds.
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
