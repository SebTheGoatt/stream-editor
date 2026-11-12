---
name: sebthegoat-edit
description: Edit a stream or "edit my timeline" into a Seb The Goat video, start to finish, with the DaVinci Resolve steps (find the recording, import the result, slur check). Default style is FaZe Jev / M3RKMUS1C (highlight montage, long clips, voices over the game); the fuller "dad gamer chaos" treatment (counters, GOAT MOMENT, two parts) is on request. Use by default for any request to edit, cut or make videos from Seb's streams or DaVinci timeline; use coryxkenshin-edit only when Cory-heavy editing is asked for.
---

# "Edit my timeline": the run, start to finish

**Default style (owner, Oct 25 2026): FaZe Jev / M3RKMUS1C.** A 60-75 s highlight montage, the TV-static
intro, then long commentary clips with hard cuts, 3-4 face zooms, 1-2 B&W freezes and one subscribe card.
No captions, meme sounds or music under gameplay. Voices sit ~10 dB over the game. The "Seb The Goat
feel" further down (counters, GOAT MOMENT, two parts) is only for when Seb asks for the full treatment;
`tools/clean_plan.py` gives a bare cut.

Run these in order without stopping to ask. Stop only for: a missing recording, a slur the check
finds, or Seb's notes on the preview. Give Seb one short progress line per step. `PY` is
`.venv/Scripts/python.exe` on his PC (`python` elsewhere). Every `resolve.py` call prints JSON.

| # | Step | Command | Time |
|---|---|---|---|
| 1 | Find the recording on his Resolve timeline | `PY tools/resolve.py --wait 60 source` → `"recording"` | seconds |
| 2 | Transcript, loud moments, overview, starter plan | `PY tools/prep_stream.py "<recording>" --name <slug>` | ~15 min per stream hour |
| 3 | Pick 10-14 moments into `plans/<slug>.json` | read `work/<slug>_transcript.txt` whole, then `_loud.txt`, the overview | you |
| 4 | Second bleep pass | `.venv-gpu/Scripts/python.exe tools/bleep_pass.py plans/<slug>.json` | ~2 min |
| 5 | Jev/Merk plan | `PY tools/jev_merk_plan.py plans/<slug>.json` (plan `"game"` names the game) | seconds |
| 6 | Render | `PY edit.py plans/<slug>-jevmerk.json --jobs 5` (add `--preview` first only if Seb wants to see a draft) | ~2 s per output second |
| 7 | Into Resolve, with chapter markers | `PY tools/resolve.py import out/<slug>-jevmerk.mp4` | ~1 min |
| 8 | Slur check by Resolve's own ears | `PY tools/resolve.py slurcheck` (exit 3 = slur found) | ~2 min |

Rules that save a re-render:

- **Step 1:** if `resolve.py` exits 2, read its `"fix"` line to Seb and stop. If the recording is in
  `"missing"`, ask where the file went. If Resolve MCP tools are connected, they work too, but
  `resolve.py` needs nothing but Resolve Studio being open. Not on Seb's PC (a cloud session)? There is
  no Resolve to reach: ask for a Google Drive link to the recording and start at step 2.
- **Step 2:** OBS records 3840x1080 (webcam left, game right) with 4 audio tracks; the starter plan
  already carries the layout, the track numbers and the louder-voices settings. Everything in `work/`
  is reused, so a re-run is free.
- **Step 3:** each moment needs `label`, `chapter` (viewer-facing), `start`, `end`, and its best beats as
  `fx` (`zoom` on the face at the reaction, `freeze` with a short caption on the punchline): the
  montage and the kept accents are built from those beats. Lead with action or a punchline, never a
  menu. Put `{"label": "intro", "clip": "../brand/intro.mp4"}` first and
  `{"label": "outro", "clip": "../brand/outro.mp4"}` last. **Never keep a slur moment**, even bleeped; cut the line with `"cuts": [[start, end]]` or drop
  the moment. Also skip sexual talk, jokes about hurting women and personal relationship stories.
  Time everything to the voice: recordings can play fast or have game audio out of sync, so no
  slow-mo or speed changes. Seb's son is his "co-host" in chapters and hooks.
- **Step 6:** `crf` 10 masters are for Seb's own export from Resolve's Deliver page. Before rendering,
  check every `fx` sits inside its segment.
- **Step 7:** the importer re-wraps to PCM audio (his Resolve drops AAC partway through), files the
  video under the "Seb The Goat edits" bin, makes a new timeline, switches the audio track on, and
  reports any frame rate, size or length mismatch under `"check"`. His original timeline is untouched.
- **Step 8:** a slur means: add a `"cuts"` entry, re-render, re-import. A swear listed there usually
  means a badly timed bleep: listen, add a `"bleeps"` entry if it is audible. The check leaves the
  subtitle track switched off. A Resolve pop-up blocks it at "Initializing" until Seb closes it.
- **Finish:** tell Seb the timeline name and length, paste `out/<slug>-jevmerk_chapters.txt`, and
  remind him to listen once before uploading (bleeps can miss) and that borrowed music can get
  claimed. Offer Shorts (`tools/make_shorts.py plans/<slug>.json --top 4`) and the packaging below.
  Every publish needs his explicit yes.

# THE SEB THE GOAT FEEL

Seb games with the kids around and the boys on voice. The channel's edge is **dad gamer chaos**:
dad duty crashing the game, roasting the boys, and acting tough about caves and then panicking.
The style borrows from five creators, each for the kind of moment it handles best, with Seb's own
signatures on top. The workflow and effect timing rules are the same as `coryxkenshin-edit`;
this skill changes **what** goes on each moment and **how much**.

## Treatment by moment type

| Moment | Treatment | Borrowed from |
|---|---|---|
| Banter, roasts, stories (Wendy's debate, hairline, the timeshare) | Let it breathe. Clean cuts, ONE caption on the best line, one meme sound at most | Vanoss, Berleezy |
| Panic, mobs, jumpscares ("I lied I lied", baby zombies) | Fast jump cuts (`tighten`), face zoom with `shake`, a hit sound, `look: red` | Dashie, Merk |
| Big fails and punchlines (deaths, "it did not work") | `freeze` with a short caption, face punch-in, `slowmo` with deep voice into a death | Cory |
| Dad moments (kids, "get down", "player 2") | Caption the line, then bump the `KIDS vs DAD` counter | Seb |
| The single best moment of the video | `goat` effect (GOAT MOMENT stamp + Seb's own "baa") | Seb |

**Timing survives the jump cuts.** Dead-air trimming never cuts a laugh the transcript marked
(`(laughs)`, `[LAUGHTER]`, `Haha!`), the 0.8 s pause that sets it up, or the beat right before a
zoom or freeze (`tighten.comic_pause`, `tighten.keep_laughs`). Whisper misses a lot of background
laughter from the boys, so when a joke lands on a laugh the transcript didn't catch, put a zoom or
freeze on the punchline and the pause before it is kept too.

**Density: medium.** Per moment: at most 2 captions, 1 zoom, 1 sound effect, plus its freeze if it
has a real punchline. Most moments get NO freeze. When in doubt, cut an effect: the first
Cory-heavy cut of the cave-dweller stream felt overdone to Seb.

## Signatures (every video)

1. **Cold open** on the best chaos of that part (10-15 s, `"tighten": false`), freeze
   `"ANYWAY. LET'S BACK UP."` with `flashback`, then `brand/intro.mp4`.
2. **Running counters** that carry through the part and continue into the next one:
   `DEATHS: n` (every death), `DAD: n  KIDS: n` (every dad-duty moment; the kids usually win),
   plus any stream-specific running joke (`ZEUS: n`). Pop the counter the moment it changes:
   `{"type": "counter", "at": 564.6, "dur": 2.5, "text": "DEATHS: 1", "sfx": "minecraft_pop"}`.
3. **GOAT MOMENT** on exactly one moment per part: `{"type": "goat", "at": 713.6}`. It adds the face
   punch-in, the stamp and `sfx/goat.wav` (Seb's own "Baa" from the 2026-09-27 stream). Keep other
   bottom captions off that moment, and drop any other zoom or hit sound at the same time.
4. **Straight cuts between moments.** Seb tried red TV-static transitions and cut them, so don't add
   `"transition"` to his plans (edit.py still supports it).
5. **Cliffhanger**: Part 1 ends on a freeze `"TO BE CONTINUED...\nPART 2: <TITLE>"`; the last
   part ends on a subscribe joke from that stream, then `brand/outro.mp4`.

## Look

Captions use the channel palette: white text with a heavy black outline, brand red for
punchlines and danger, green only for wins. Counters and the GOAT stamp sit on a red box.
Use the palette names (`"text"`, `"punch"`, `"danger"`, `"win"`, `"box"`) in plans, never hex,
so the whole channel can be recolored in one place. These are the intro's colors; swap them for
the profile-picture colorway when Seb confirms it.

Paste this into the top of every Seb plan:

```json
"fps": 60,
"crf": 10,
"x264_preset": "fast",
"facecam": [0.84, 0.83],
"tighten": {"min_silence": 0.7, "pad": 0.15, "noise_db": -30},
"palette": {"text": "white", "punch": "#FF2B2B", "danger": "#FF2B2B", "win": "#7CFC00", "box": "#E01B24"},
"goat_sound": "goat",
"bleep_sound": "quack",
"layout": {"game": [1920, 0, 1920, 1080], "cam": [0, 0, 1920, 1080], "cam_size": [568, 320], "cam_pos": [1324, 732], "border": 4},
```

## Length and parts

A 2-hour stream gives about 18-20 minutes of keepers. Split it into **two parts of 9-10 minutes**
in stream order (Vanoss-length); a 5-hour stream becomes 2-3 parts. Each part has its own cold
open, counters, GOAT MOMENT and title. `plans/cave-dweller-part1.json` and `-part2.json` are the
worked example.

## Packaging for views (do this for every part)

- **Research first (vidIQ, ~5 credits a call):** `vidiq_keyword_research` on the game or mod and
  `vidiq_outliers` for breakout videos from small channels in the same niche. Use the keyword with
  rising search and low competition in the title. For the cave-dweller stream that was
  "cave dweller minecraft" (38.6K/mo, +39%, competition 38).
- **Titles:** `vidiq_generate_titles` with an `analysisSummary` of the part and the breakout titles
  as `competitorTitles`. Favor "Minecraft, but ...", "I ... (I lied)" and anything with the
  dad/kids angle. A dad-vs-scary-mod video went 479x on an 8K channel.
- **Title + 3 thumbnail bets:** run the `youtube-packaging` skill (workspace level) through
  Stage 4: one locked title, three distinct thumbnail concepts for YouTube's Test & Compare, and a
  description. Seb has ~1,000 videos, so pull his CTR history with vidIQ and do its
  `channel-calibration.md` instead of the cold-start defaults. Skip its Stage 5 (Nano Banana
  renders): render all three bets with the method below.
- **Thumbnails:** build them from the real 1080p webcam half of the OBS recording (the left
  1920x1080), never an AI face. Layout: dark, tinted game frame behind (crop out the hotbar), Seb's
  reaction on the right with a white edge, 2-3 huge Anton words on the left, one red keyword box.
  Make the words a running bit from the video: `I LIED`, `KIDS 4 / DAD 2`. Get Seb's OK before
  putting his kids' faces on one. Score with `vidiq_score_thumbnail` once the video is up
  (unlisted works), and A/B test with YouTube's Test & Compare.
- **Descriptions, Shorts captions and community posts:** write them in Seb's voice, then run the
  `humanizer` skill (installed at the workspace level) so they don't read as AI-written. Leave
  titles alone: meme caps and "..." are on purpose.
- **Tags (vidIQ `vidiq_keyword_research`, `matching_terms` mode, 5 credits a call):** run it on
  the game/mod keyword and on "funny minecraft". Take 10-15 tags under 500 characters: the
  primary keyword and 3-5 long-tail variants (prefer rising ones with competition under 45), the
  niche ("minecraft horror funny" grew 240% in Oct 2026), the game, then the brand: "seb the
  goat", "sebthegoatt". Put the primary keyword in the first 40 characters of the title and the
  first line of the description.
- **Pick the title** with `vidiq_score_title` and `channelId` UCkpGHy1AY-4Y3HbYHA0IX0Q (scores
  against Seb's own audience). The title and thumbnail should add to each other, not repeat.
- **Chapters:** every render writes `out/<name>_chapters.txt` from the plan. Give each segment a
  viewer-facing `"chapter"` name; the cold open's is "Intro".
- **Description:** hook line with the keyword, two or three lines in Seb's voice, the chapters, then
  socials. Run it through `humanizer`.
- **ArtCraft** (installed desktop app, Nano Banana image edit, Seb's credits) pushes the frame-built
  thumbnails further: write `out/artcraft/PROMPTS.md` with an edit prompt per thumbnail that keeps
  his real face, text and box and only swaps the background for things that are in the video. Seb
  drives the app; it isn't scriptable.
- **Shorts:** `python tools/make_shorts.py plans/<part>.json --top 4` ranks every moment (GOAT moment,
  freezes, zooms, counters, transcript laughs, 15-45 s length) and renders the winners at 1080x1920:
  webcam on top, game below, every word captioned (swears starred), the moment's punchline as the
  hook. Titles from `vidiq_generate_titles` with `type: "short"` and 2-3 hashtags.
- **Publishing:** Seb uploads the long videos and Shorts to YouTube himself. After that, with his
  yes for the exact values: `vidiq_update_video` sets title, description and tags, and
  `vidiq_instagram_publish_reel` reposts a Short to Instagram from its YouTube link. TikTok is a
  manual upload. Vizard (`using-vizard-api`) remains the backup for clipping from a YouTube link.
- **Not REA:** reverse-engineering Vizard or vidIQ breaks their terms and wouldn't work anyway
  (their models and data are server-side). The Shorts maker and the vidIQ calls above replace that.

## Recording setup (OBS 32, Seb's profile)

Advanced output, Recording format Hybrid MP4 (or MKV), Audio Tracks 1-4 ticked. In Edit →
Advanced Audio Properties:

| Source | Track 1 (mix) | 2 (mic) | 3 (game) | 4 (Discord) |
|---|---|---|---|---|
| MIC Audio | yes | yes | | |
| Game Audio (application capture of Minecraft) | yes | | yes | |
| Discord Audio (application capture of Discord) | yes | | | yes |
| Audio Output Capture / Desktop Audio | no tracks (or muted): it would double the game and Discord |

`tools/prep_stream.py` sees 4+ audio streams and assumes exactly this layout: it transcribes the mic
and Discord tracks on their own (cleaner words, each tagged SEB or BOYS in the readable transcript)
and writes `"audio_tracks": {"mic": 1, "game": 2, "friends": 3}` (stream numbers; 0 is the mix) into
the starter plan. Pass `--tracks` if the routing differs. With `audio_tracks`, edit.py mixes the
tracks itself: a bleep mutes only the voice that swore while the game keeps playing, and
`"track_levels": {"friends": 0.8}` sets a voice's level. Plan bleeps can name a voice:
`[start, end, "friends"]`. Recordings with one audio track work exactly as before.

## If `resolve.py` can't be used

The same steps by hand through Resolve MCP `run_script`: read each video item's
`GetMediaPoolItem().GetClipProperty("File Path")`; re-wrap with
`ffmpeg -i out/<slug>.mp4 -map 0 -c:v copy -c:a pcm_s24le out/<slug>.mov`; `ImportMedia` into a
"Seb The Goat edits" bin and `CreateTimelineFromClips`; check `GetIsTrackEnabled("audio", 1)`;
`timeline.CreateSubtitlesFromAudio({...English...})`, search the subtitle items, then
`timeline.SetTrackEnable("subtitle", 1, False)`.
