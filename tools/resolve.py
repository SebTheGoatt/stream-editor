"""Talk to DaVinci Resolve Studio from the command line: no MCP server or copy-pasted scripts needed.

Resolve must be open (Studio only: the free edition can't be scripted from outside the app), with
Preferences > System > General > "External scripting using" set to Local.

  python tools/resolve.py status                      what's open: project, timeline, frame rate, size
  python tools/resolve.py source                      the recording(s) on the current timeline, longest first
  python tools/resolve.py import out/<name>.mp4       re-wrap with PCM audio, import into the "Seb The Goat
                                                      edits" bin, make a timeline, add chapter markers
  python tools/resolve.py chapters out/<name>_chapters.txt     chapter markers on the current timeline
  python tools/resolve.py slurcheck                   Resolve transcribes the current timeline; lists every
                                                      slur and swear it still hears, then hides the subtitles

Every command prints one JSON object, so a script or Claude can read the answer. Exit code 2 means
Resolve isn't reachable; 3 means the slur check found a slur.

Built straight on Blackmagic's own scripting API (the same one pybmd, mhadifilms/dvr and
samuelgursky/davinci-resolve-mcp wrap), so there is nothing extra to install.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BIN = "Seb The Goat edits"
SLURS = ["nigg*", "fag*", "retard*"]
# Where Blackmagic installs the scripting module and library on each system.
DEFAULTS = {
    "win32": (r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
              r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"),
    "darwin": ("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
               "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"),
    "linux": ("/opt/resolve/Developer/Scripting", "/opt/resolve/libs/Fusion/fusionscript.so"),
}


def say(obj, code=0):
    print(json.dumps(obj, indent=2))
    sys.exit(code)


def connect(wait=0):
    """The running Resolve, or exit 2 with what to fix."""
    api, lib = DEFAULTS.get(sys.platform, DEFAULTS["linux"])
    api = os.environ.setdefault("RESOLVE_SCRIPT_API", os.path.expandvars(api))
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", lib)
    sys.path.append(os.path.join(api, "Modules"))
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        say({"ok": False, "error": "Resolve's scripting module wasn't found",
             "fix": f"Install DaVinci Resolve Studio, or set RESOLVE_SCRIPT_API (looked in {api})"}, 2)
    deadline = time.time() + wait
    while True:
        resolve = dvr.scriptapp("Resolve")
        if resolve or time.time() >= deadline:
            break
        time.sleep(2)
    if not resolve:
        say({"ok": False, "error": "Resolve isn't answering",
             "fix": "Open DaVinci Resolve Studio, close any pop-up, and set Preferences > System > General > "
                    "External scripting using: Local"}, 2)
    return resolve


def current(resolve, need_timeline=True):
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        say({"ok": False, "error": "No project is open in Resolve"}, 2)
    timeline = project.GetCurrentTimeline()
    if need_timeline and not timeline:
        say({"ok": False, "error": f"Project '{project.GetName()}' has no timeline open"}, 2)
    return project, timeline


def fps_of(timeline):
    return float(timeline.GetSetting("timelineFrameRate"))


def describe(project, timeline):
    info = {"project": project.GetName()}
    if timeline:
        fps = fps_of(timeline)
        frames = timeline.GetEndFrame() - timeline.GetStartFrame()
        info.update(timeline=timeline.GetName(), fps=fps, frames=frames, seconds=round(frames / fps, 2),
                    width=int(timeline.GetSetting("timelineResolutionWidth")),
                    height=int(timeline.GetSetting("timelineResolutionHeight")),
                    video_tracks=timeline.GetTrackCount("video"), audio_tracks=timeline.GetTrackCount("audio"))
    return info


def cmd_status(args):
    resolve = connect(args.wait)
    project, timeline = current(resolve, need_timeline=False)
    say({"ok": True, "resolve": resolve.GetVersionString(), **describe(project, timeline)})


def cmd_source(args):
    """Which files the current timeline plays, so the editor can work from the raw recording."""
    project, timeline = current(connect(args.wait))
    fps, files = fps_of(timeline), {}
    for track in range(1, timeline.GetTrackCount("video") + 1):
        for item in timeline.GetItemListInTrack("video", track) or []:
            clip = item.GetMediaPoolItem()
            path = clip.GetClipProperty("File Path") if clip else ""
            if not path:
                continue  # titles, generators, compound clips
            f = files.setdefault(path, {"path": path, "exists": os.path.exists(path), "seconds_on_timeline": 0.0,
                                        "resolution": clip.GetClipProperty("Resolution"),
                                        "clip_fps": clip.GetClipProperty("FPS")})
            f["seconds_on_timeline"] = round(f["seconds_on_timeline"] + item.GetDuration() / fps, 2)
    ranked = sorted(files.values(), key=lambda f: -f["seconds_on_timeline"])
    missing = [f["path"] for f in ranked if not f["exists"]]
    say({"ok": bool(ranked), **describe(project, timeline), "recording": ranked[0]["path"] if ranked else None,
         "files": ranked, **({"missing": missing} if missing else {})}, 0 if ranked else 2)


def parse_chapters(path):
    """ "1:12 Football talk" lines (what edit.py writes next to every render) -> [(seconds, name)]."""
    marks = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*((?:\d+:)?\d+:\d\d)\s+(.+)", line)
        if m:
            secs = 0
            for part in m.group(1).split(":"):
                secs = secs * 60 + int(part)
            marks.append((secs, m.group(2).strip()))
    return marks


def add_chapters(timeline, path, color="Blue"):
    fps, added = fps_of(timeline), 0
    last = timeline.GetEndFrame() - timeline.GetStartFrame() - 1
    for secs, name in parse_chapters(path):
        frame = int(round(secs * fps))  # counted from the start of the timeline, not from its timecode
        if frame <= last:
            added += bool(timeline.AddMarker(frame, color, name[:60], "chapter", 1))
    return added


def cmd_chapters(args):
    project, timeline = current(connect(args.wait))
    if args.replace:
        timeline.DeleteMarkersByColor(args.color)
    n = add_chapters(timeline, args.file, args.color)
    say({"ok": n > 0, "timeline": timeline.GetName(), "markers_added": n, "in_file": len(parse_chapters(args.file))})


def pcm_copy(path):
    """Seb's Resolve drops AAC audio partway through playback, so hand it uncompressed audio instead."""
    out = os.path.splitext(path)[0] + ".mov"
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(path):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-map", "0", "-c:v", "copy", "-c:a", "pcm_s24le",
                        out], check=True)
    return out


def media_info(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    s = info["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den), float(info["format"]["duration"])


def cmd_import(args):
    """Each finished video becomes its own timeline next to Seb's original, which is never touched."""
    resolve = connect(args.wait)
    project, _ = current(resolve, need_timeline=False)
    pool = project.GetMediaPool()
    root = pool.GetRootFolder()
    folder = next((f for f in root.GetSubFolderList() or [] if f.GetName() == BIN), None) or pool.AddSubFolder(root, BIN)
    pool.SetCurrentFolder(folder)
    results, ok = [], True
    for path in args.files:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            results.append({"file": path, "ok": False, "error": "file not found"})
            ok = False
            continue
        media = path if path.lower().endswith(".mov") or args.keep_audio else pcm_copy(path)
        w, h, fps, dur = media_info(media)
        name = args.name if args.name and len(args.files) == 1 else os.path.splitext(os.path.basename(path))[0]
        name += " - Seb The Goat edit"
        items = pool.ImportMedia([media])
        timeline = pool.CreateTimelineFromClips(name, items) if items else None
        if not timeline:
            results.append({"file": media, "ok": False,
                            "error": "Resolve refused the import (a timeline with this name may already exist, "
                                     "or a pop-up is open)"})
            ok = False
            continue
        project.SetCurrentTimeline(timeline)
        for track in range(1, timeline.GetTrackCount("audio") + 1):
            if not timeline.GetIsTrackEnabled("audio", track):
                timeline.SetTrackEnable("audio", track, True)  # one came in switched off
        got = describe(project, timeline)
        problems = []
        if abs(got["fps"] - fps) > 0.01:
            problems.append(f"timeline is {got['fps']} fps, the video is {fps:.2f}")
        if (got["width"], got["height"]) != (w, h):
            problems.append(f"timeline is {got['width']}x{got['height']}, the video is {w}x{h}")
        if abs(got["seconds"] - dur) > 1:
            problems.append(f"timeline runs {got['seconds']} s, the video {dur:.1f} s")
        chapters = args.chapters or re.sub(r"(-master)?\.\w+$", "", path) + "_chapters.txt"
        markers = add_chapters(timeline, chapters) if os.path.exists(chapters) else 0
        results.append({"file": media, "ok": True, **got, "chapter_markers": markers,
                        **({"check": problems} if problems else {})})
    say({"ok": ok, "bin": BIN, "imported": results}, 0 if ok else 1)


def matches(word, patterns):
    w = re.sub(r"[^a-z']", "", word.lower())
    return any(fnmatch.fnmatch(w, p) for p in patterns)


def cmd_slurcheck(args):
    """A second pair of ears: Resolve's own transcription has caught slurs Whisper heard as "this thing"."""
    from edit import DEFAULT_BLEEP
    resolve = connect(args.wait)
    project, timeline = current(resolve)
    before = timeline.GetTrackCount("subtitle")
    if not args.reuse or not before:
        settings = {resolve.AUTO_CAPTION_LANGUAGE: resolve.AUTO_CAPTION_ENGLISH}
        if not timeline.CreateSubtitlesFromAudio(settings):
            say({"ok": False, "error": "Resolve couldn't transcribe the timeline",
                 "fix": "Close any pop-up in Resolve (a missing Extra blocks it at 'Initializing') and try again"}, 1)
    fps, start, slurs, swears, lines = fps_of(timeline), timeline.GetStartFrame(), [], [], 0
    for track in range(1, timeline.GetTrackCount("subtitle") + 1):
        for item in timeline.GetItemListInTrack("subtitle", track) or []:
            lines += 1
            text, at = item.GetName(), round((item.GetStart() - start) / fps, 2)
            for word in text.split():
                if matches(word, SLURS):
                    slurs.append({"at": at, "text": text})
                elif matches(word, DEFAULT_BLEEP):
                    swears.append({"at": at, "text": text})
        # The video already has its captions burned in; a visible track would double them in renders.
        timeline.SetTrackEnable("subtitle", track, False)
    say({"ok": not slurs, "timeline": timeline.GetName(), "lines_heard": lines, "slurs": slurs, "swears": swears,
         "next": ("Cut each slur with the segment's \"cuts\", re-render and re-import" if slurs else
                  "Listen at each swear: if it is audible, add a \"bleeps\" entry and re-render" if swears else
                  "Clean")}, 3 if slurs else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wait", type=float, default=0, help="seconds to keep trying while Resolve starts up")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(run=cmd_status)
    sub.add_parser("source").set_defaults(run=cmd_source)
    p = sub.add_parser("import")
    p.add_argument("files", nargs="+")
    p.add_argument("--name", help="timeline name (one file only; default: the file's name)")
    p.add_argument("--chapters", help="chapters file (default: the one edit.py wrote next to the render)")
    p.add_argument("--keep-audio", action="store_true", help="import as is, without the PCM re-wrap")
    p.set_defaults(run=cmd_import)
    p = sub.add_parser("chapters")
    p.add_argument("file")
    p.add_argument("--color", default="Blue")
    p.add_argument("--replace", action="store_true", help="remove this color's markers first")
    p.set_defaults(run=cmd_chapters)
    p = sub.add_parser("slurcheck")
    p.add_argument("--reuse", action="store_true", help="read the subtitles already on the timeline")
    p.set_defaults(run=cmd_slurcheck)
    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
