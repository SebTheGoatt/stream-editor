"""Vizard.ai from the command line: Shorts from a long video, captions, publishing.

The API key is read from the VIZARDAI_API_KEY environment variable, or from a git-ignored `.env`
file in the repo root containing `VIZARDAI_API_KEY=...`. Never commit the key or paste it in chat.

Usage:
  python tools/vizard.py clip https://www.youtube.com/watch?v=XXXX --length 1 --name "COD shorts"
      Long video -> vertical clips with captions, ranked by viral score. Waits, then downloads every
      clip to out/shorts/<projectId>/ with clips.json (titles, scores, transcripts, editor links).
  python tools/vizard.py edit https://example.com/short.mp4 --ratio 1
      A video of 3 minutes or less -> one enhanced video (subtitles, hook headline, optional B-roll).
  python tools/vizard.py query <projectId>             re-check a project / refresh 7-day download links
  python tools/vizard.py caption <videoId> --platform youtube --tone catchy
  python tools/vizard.py accounts                      social accounts connected in Vizard
  python tools/vizard.py publish <videoId> --account <id> [--at 2026-10-25T18:00] [--title "..."] --yes

Sources: YouTube, Google Drive, Vimeo, Twitch, TikTok... links work directly. A local file needs a
public direct link first (videoType 1, pass --ext mp4).
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODES = {1000: "still processing", 4001: "invalid API key", 4002: "clipping failed", 4003: "rate limit exceeded",
         4004: "unsupported format / plan upgrade needed", 4005: "invalid URL or video too long for edit mode",
         4006: "illegal parameter", 4007: "not enough Vizard credits", 4008: "Vizard could not download the video",
         4011: "invalid social account ID"}
PLATFORMS = {"general": 1, "tiktok": 2, "instagram": 3, "youtube": 4, "facebook": 5, "linkedin": 6, "twitter": 7}
TONES = {"neutral": 0, "interesting": 1, "catchy": 2, "serious": 3, "question": 4}


def api_key():
    key = os.environ.get("VIZARDAI_API_KEY")
    env = os.path.join(ROOT, ".env")
    if not key and os.path.exists(env):
        for line in open(env):
            if line.strip().startswith("VIZARDAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    if not key:
        sys.exit("No Vizard API key: set VIZARDAI_API_KEY or put VIZARDAI_API_KEY=... in .env (git-ignored).")
    return key


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 headers={"VIZARDAI_API_KEY": api_key(), "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Vizard HTTP {e.code}: {e.read()[:300]!r}")


def check(resp):
    code = resp.get("code")
    if code not in (2000, 1000):
        sys.exit(f"Vizard error {code}: {CODES.get(code, resp)}")
    return resp


def video_type(url, ext):
    u = url.lower()
    for needle, t in (("youtube.com", 2), ("youtu.be", 2), ("drive.google", 3), ("vimeo.com", 4),
                      ("streamyard", 5), ("tiktok.com", 6), ("twitter.com", 7), ("x.com", 7), ("twitch.tv", 9),
                      ("loom.com", 10), ("facebook.com", 11), ("linkedin.com", 12)):
        if needle in u:
            return t, None
    return 1, ext or u.rsplit(".", 1)[-1].split("?")[0]


def wait(project_id, max_minutes=45):
    print(f"project {project_id}: processing (long or 4K videos can take 10-30 min)...", flush=True)
    for _ in range(max_minutes * 2):
        time.sleep(30)
        r = check(call("GET", f"/project/query/{project_id}"))
        if r["code"] == 2000 and r.get("videos"):
            return r
    sys.exit(f"timed out; check later with: python tools/vizard.py query {project_id}")


def save(result):
    folder = os.path.join(ROOT, "out", "shorts", str(result["projectId"]))
    os.makedirs(folder, exist_ok=True)
    for i, v in enumerate(result["videos"], 1):
        name = f"{i:02d}_{''.join(c if c.isalnum() else '_' for c in v.get('title', 'clip'))[:50]}.mp4"
        urllib.request.urlretrieve(v["videoUrl"], os.path.join(folder, name))
        print(f"{i:2d}. score {v.get('viralScore', '-'):>4}  {v['videoMsDuration'] / 1000:5.1f}s  "
              f"id {v['videoId']}  {v.get('title', '')}")
    with open(os.path.join(folder, "clips.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(f"saved {len(result['videos'])} clips -> {folder}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clip")
    c.add_argument("url")
    c.add_argument("--length", type=int, nargs="+", default=[0], help="0 auto, 1 <30s, 2 30-60s, 3 60-90s, 4 >90s")
    c.add_argument("--lang", default="en")
    c.add_argument("--name")
    c.add_argument("--ext")
    e = sub.add_parser("edit")
    e.add_argument("url")
    e.add_argument("--ratio", type=int, default=1, help="1 9:16, 2 1:1, 3 4:5, 4 16:9")
    e.add_argument("--lang", default="en")
    e.add_argument("--ext")
    e.add_argument("--broll", action="store_true")
    e.add_argument("--no-subtitles", action="store_true")
    e.add_argument("--no-headline", action="store_true")
    e.add_argument("--remove-silence", action="store_true")
    e.add_argument("--template", type=int)
    q = sub.add_parser("query")
    q.add_argument("project_id")
    cap = sub.add_parser("caption")
    cap.add_argument("video_id", type=int)
    cap.add_argument("--platform", choices=PLATFORMS, default="youtube")
    cap.add_argument("--tone", choices=TONES, default="catchy")
    sub.add_parser("accounts")
    p = sub.add_parser("publish")
    p.add_argument("video_id", type=int)
    p.add_argument("--account", required=True)
    p.add_argument("--post", default="", help="caption; empty lets Vizard write one")
    p.add_argument("--title", help="YouTube only")
    p.add_argument("--at", help="schedule, local time like 2026-10-25T18:00")
    p.add_argument("--yes", action="store_true", help="required: publishing posts publicly")
    args = ap.parse_args()

    if args.cmd in ("clip", "edit"):
        vtype, ext = video_type(args.url, args.ext)
        body = {"videoUrl": args.url, "videoType": vtype, "lang": args.lang}
        if ext:
            body["ext"] = ext
        if args.cmd == "clip":
            body.update(preferLength=args.length, getClips=1)
            if args.name:
                body["projectName"] = args.name
        else:
            body.update(getClips=0, ratioOfClip=args.ratio, subtitleSwitch=0 if args.no_subtitles else 1,
                        headlineSwitch=0 if args.no_headline else 1, autoBrollSwitch=int(args.broll),
                        removeSilenceSwitch=int(args.remove_silence))
            if args.template:
                body["templateId"] = args.template
        r = check(call("POST", "/project/create", body))
        save(wait(r["projectId"]))
    elif args.cmd == "query":
        r = check(call("GET", f"/project/query/{args.project_id}"))
        if r["code"] == 1000 or not r.get("videos"):
            print("still processing")
        else:
            save(r)
    elif args.cmd == "caption":
        r = check(call("POST", "/project/ai-social", {"finalVideoId": args.video_id,
                                                       "aiSocialPlatform": PLATFORMS[args.platform],
                                                       "tone": TONES[args.tone], "voice": 0}))
        if r.get("aiSocialTitle"):
            print("TITLE:", r["aiSocialTitle"])
        print(r.get("aiSocialContent", ""))
    elif args.cmd == "accounts":
        r = check(call("GET", "/project/social-accounts"))
        for a in r.get("accounts", []):
            print(f"{a['id']}  {a['platform']:<10} {a.get('username', ''):<24} {a.get('status', '')}")
    elif args.cmd == "publish":
        if not args.yes:
            sys.exit("Publishing posts the clip publicly. Re-run with --yes once the owner has approved it.")
        body = {"finalVideoId": args.video_id, "socialAccountId": args.account, "post": args.post}
        if args.title:
            body["title"] = args.title
        if args.at:
            body["publishTime"] = int(datetime.datetime.fromisoformat(args.at).timestamp() * 1000)
        check(call("POST", "/project/publish-video", body))
        print("scheduled" if args.at else "published")


if __name__ == "__main__":
    main()
