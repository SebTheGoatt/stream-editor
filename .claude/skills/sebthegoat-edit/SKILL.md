---
name: sebthegoat-edit
description: Edit a stream into a Seb The Goat video, the channel's own style ("dad gamer chaos", medium-density edits, running counters, GOAT MOMENT, two ~10 min parts). Use by default for any request to edit, cut or make videos from Seb's streams or DaVinci timeline; use coryxkenshin-edit only when Cory-heavy editing is asked for.
---

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

## Pipeline on Seb's PC

When Seb says "edit my timeline", run this in order. Every step was dry-run end to end on
2026-10-22 (raw recording → prep → master → Resolve import into a throwaway project).

1. **Find the recording**: launch Resolve if needed (`launch_resolve`), then read the current
   timeline with Resolve MCP `run_script`: each video item's `GetMediaPoolItem().GetClipProperty("File Path")`.
   OBS records 3840x1080: webcam on the left, game on the right. Check the file exists before going on;
   old recordings get moved or deleted.
2. **Prep in one command** (transcript on the GPU, readable transcript, loudest moments, overview
   grid, starter plan with the full header including `"layout"`):
   `.venv/Scripts/python.exe tools/prep_stream.py "<recording>" --name <slug>`
   About 15 min per hour of stream. `.venv-gpu` holds AMD's ROCm PyTorch build plus openai-whisper
   (faster-whisper is NVIDIA-only). The plan points straight at the raw recording: edit.py rebuilds
   game full-frame + cam bottom-right with a white border for only the kept moments. Tell Seb the
   progress while it runs.
3. Read `work/<slug>_transcript.txt` start to finish, `work/<slug>_loud.txt` and the overview.
   For contact sheets of the raw recording, the cam is the left half and the game the right.
4. **Pick moments** by reading the whole transcript (`tools/find_moments.py`) and checking deaths and
   kid moments on contact sheets: Seb is sometimes away from the camera while his character dies.
   **Never keep a slur moment**, even bleeped; also skip sexual talk and jokes about hurting women.
   Split the moments into `plans/<slug>-part1.json`, `-part2.json` (copy the starter's header).
   Check every effect sits inside its segment and that no kept range contains a slur before rendering.
   Then run the second bleep pass, which re-transcribes each kept moment on its own and adds missed
   swears to the plan's `"bleeps"`: `.venv-gpu/Scripts/python.exe tools/bleep_pass.py plans/<slug>-part1.json plans/<slug>-part2.json`.
   It reports slurs; cut that line with the segment's `"cuts": [[start, end]]` (source seconds).
   Skip personal relationship stories (Seb had the "girl's guy best friend" story pulled).
5. **Preview both parts** (`edit.py <plan> --preview --jobs 5`, ~6 min a part), open them for Seb
   (`Start-Process <file>`), apply his notes, then render the masters (`crf` 10: near-lossless,
   because Seb exports from DaVinci's Deliver page with his own settings). A master takes about
   2 s per second of output.
6. **Import into Resolve** next to his original, which stays untouched. In his current project:
   ```python
   mp = project.GetMediaPool()
   folder = mp.AddSubFolder(mp.GetRootFolder(), "Seb The Goat edits")
   mp.SetCurrentFolder(folder)
   items = mp.ImportMedia([r"<full path to out/<slug>-part1.mp4>"])
   mp.CreateTimelineFromClips("<slug> part 1 - Seb The Goat edit", items)
   ```
   Then confirm the timeline's frame rate, resolution and duration match the master.
   **Slur check with Resolve (required):** run `timeline.CreateSubtitlesFromAudio({...English...})`
   on each new timeline and search the subtitle items for slurs and swears. A swear that still shows
   up usually means a badly timed bleep (Whisper sometimes stamps a word with zero length; edit.py now
   bleeps at least 0.4 s per word), so check the audio there and add a `"bleeps"` entry if needed. Whisper has twice heard
   a slur as "this thing"; Resolve's transcription caught both. Any slur means: add a `"cuts"` entry,
   re-render, re-import. Then turn the subtitle track off (`timeline.SetTrackEnable("subtitle", 1, False)`):
   the video already has burned-in meme captions, and a visible track doubles them in the viewer and
   in renders. Seb exports it only as a separate captions file for YouTube. A Resolve pop-up (e.g.
   about a missing Extra) blocks these jobs at "Initializing" until Seb closes it.
7. Remind him to listen once for missed bleeps and that music beds can get claimed.
8. After upload: vidIQ for titles, thumbnails and chapters, then Vizard (`using-vizard-api`)
   for Shorts to YouTube, TikTok and Instagram. Every publish needs Seb's explicit yes.
