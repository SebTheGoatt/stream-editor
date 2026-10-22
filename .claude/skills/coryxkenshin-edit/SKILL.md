---
name: coryxkenshin-edit
description: Turn a long gaming stream recording into a fast, funny CoryxKenshin-style YouTube video with this repo's editor (jump cuts, facecam punch-in zooms, freeze frames, deep-voice slow-mo, meme captions, the sound pack, music beds, auto-bleeped swearing, channel intro/outro). Use when asked to edit, cut, make highlights from, or "do the Cory edit" on a stream or VOD.
---

# CoryxKenshin-style stream edit

The editor is `edit.py`, driven by a JSON plan in `plans/`. Your job is mostly picking moments and
writing the plan; the script does the rendering. `plans/crafting.json` (Minecraft) and
`plans/cod-mw4.json` (COD) are complete worked examples: copy their patterns.

## 0. Before anything

- Run the `stream-editor-setup` skill first if `.venv/`, FFmpeg or `sfx/pack/` are missing.
- Get the **original** recording (OBS file, or YouTube Studio → Content → ⋮ → Download). Never work from a
  re-downloaded or low-res copy if the original exists: 144p sources look bad no matter what.
  Only if no original exists, render with `--upscale general` (AI upscaling, slow on CPU).
- Put it in `work/` (git-ignored). Check it: `ffprobe -v error -show_entries stream=width,height -of csv work/<file>`.

## 1. Transcribe (word timings drive bleeps and caption timing)

```bash
python transcribe.py work/stream.mp4 work/stream_transcript.json   # ~0.5x stream length on 4 CPU cores
```

## 2. Find the moments

Aim for **6–10 minutes** of finished video from a 30–60 minute stream; 10–16 segments of 10–50 s each.

```bash
python tools/find_moments.py work/stream_transcript.json                 # read the whole thing
python tools/find_moments.py work/stream_transcript.json --loud work/stream.mp4   # yelling/laughing spikes
python tools/find_moments.py work/stream_transcript.json --words bed died irs     # exact word times
python tools/contact_sheet.py work/stream.mp4 --start 1338 --dur 36 --out work/sheet.png  # see deaths/kills
```

Keep: punchlines, roasts, stories with a payoff, deaths and fails, rage, wholesome dad moments,
friends' bits that escalate (repeated lines are gold: "that's how you sound" x10).
Cut: menus with no talking, settings fiddling, silent walking, queue time.
**Always verify visual beats with a contact sheet.** AI summaries of a video get timestamps wrong;
the transcript and frames are the truth.
**Never keep a slur moment**, even bleeped; skip the whole bit.

## 3. Write the plan

Structure that works:
1. **Cold open**: the best fail/rage moment (10–15 s, `"tighten": false`), ending on a freeze frame
   `"ANYWAY. LET'S BACK UP."` with `flashback`.
2. **Channel intro**: `{"label": "channel intro", "clip": "../brand/intro.mp4", "fx": [music cues]}`
   (the brand intro has almost no audio; put `glitch` + `music_cory_dance_music` under it).
3. Moments in stream order, each with 3–8 effects.
4. **Ending**: the biggest fail, a freeze with a joke subscribe line, then
   `{"label": "outro", "clip": "../brand/outro.mp4", "fx": [{"type": "music", "at": 0, "dur": 6, "name": "music_cory_happy_music", "vol": 0.8}]}`.

Effect timing rules (times are seconds in the ORIGINAL recording):
- Caption `at` = the word's start time from the transcript; `dur` 2–4 s. Quote what people said in
  `"\"QUOTES\""`, add reaction captions in plain caps ("IT IS NOT.", "SIR???", "SKILL ISSUE").
  Keep captions short; use `\n` for a 2–3 line end card. The Anton font has no emoji.
- `zoom` on `"target": "face"` right on the punchline, 2–3 s, scale 1.8–2.4 (1.7 max on low-res sources).
  Add `"shake": true` for rage. Set `"facecam": [x, y]` per stream layout (0–1 from top-left;
  find it on a contact sheet). Minecraft layout was [0.89, 0.54], COD [0.83, 0.78].
- `freeze` = the comedic pause: 1.2–2.2 s, black-and-white by default, with a caption and a sound.
- `slowmo` (factor 0.5, deep voice) into deaths and falls, with `falling`.
- `look`: `red` for taking damage/rage, `deepfry` for chaos, `blue` for sad.
- `music` beds run across cuts and duck under voices: sad violin for sad stories, sneaky snitch for
  dodging questions, curb your enthusiasm on the final fail, run/chase music for panic.

Sound cheat sheet (names in `sfx/pack/`, from `pack/`; homemade fallbacks in `sfx/`):

| Moment | Sound |
|---|---|
| punchline / zoom hit | `boom_meme` |
| caught / busted / "WHO IS IN MY BED" | `mgs_alert` |
| money, flexing, "not sponsored" | `cash_register` |
| awkward silence | `crickets_gaming` |
| bad take, "SIR???" | `bruh`, `what`, `huh_ceeday`, `nope` |
| death (Minecraft / Roblox / COD) | `minecraft_damage`, `roblox_death_sound_oof`, `mission_failed_we_ll_get_em_next_time_call_of_duty` |
| fail | `spongebob_boo_womp`, `fail_1` |
| dramatic reveal | `dun_dun_dun` |
| cops / IRS / FBI joke | `fbi_open_up` |
| hits | `punch_1`, `punch_2`, `bonk`, `hit_marker` |
| level up / win | `anime_shine`, `correct_ding`, `big_bell` (round start) |
| flashback / rewind | `flashback` |
| record scratch | `scratch` (homemade) |

List everything available: `ls sfx/pack sfx`.

## 4. Preview, check, render

```bash
python edit.py plans/<name>.json --preview                 # 540p, about a minute
python tools/contact_sheet.py out/<name>_preview.mp4 --every 3 --out work/check.png
```
Look at the sheet: captions landing on the right lines, zooms on the face, nothing off-screen.
Fix the plan, re-preview just the changed parts with `--only 3,4`, then render:

```bash
python edit.py plans/<name>.json            # full 1080p
```

Then tell the person to **listen once before uploading**: bleeps rely on speech recognition and can
miss a word. Remind them borrowed music can trigger a YouTube copyright claim.

## 5. Shorts (optional)

After the long video is on YouTube, use the `using-vizard-api` skill: `python tools/vizard.py clip <youtube link> --length 1`
turns it into ranked vertical Shorts with captions. Get the owner's OK before publishing anything.

## Gotchas learned the hard way

- `pgrep -f "edit.py plans/x.json"` inside a shell loop matches its own command line; wait on a PID instead.
- A clip with no audio track (like the outro) gets silence of its exact length; don't use `-shortest`.
- Long sounds are trimmed at the end of the piece they start in; use a `music` cue for anything that
  should play across cuts.
- Upscaled segments are cached in `work/upscaled/`, so re-renders after plan edits are fast.
