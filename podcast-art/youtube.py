"""Read the channel's playlists and videos (title, description, date, order) so the covers agent
gets guest names and episode numbers from the source instead of asking.

Two ways in, tried in order:
  1. YouTube Data API v3 - needs YOUTUBE_API_KEY (read-only key from console.cloud.google.com)
  2. A real browser (Playwright/Chromium) on youtube.com - needs www.youtube.com allowed
     in the environment's network settings

Usage:
  python youtube.py playlists                         # list the channel's playlists
  python youtube.py playlist "Ballin' 4 Peace Podcast" # every video in it -> work/youtube/<playlist>.json
  python youtube.py video yIi-6sVwO3k                  # one video's title + description
"""
import glob
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "work" / "youtube"
CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", "UCZMq-aiXcITjbxxqrjYz8Dg")  # Ballin' 4 Peace
KEY = os.environ.get("YOUTUBE_API_KEY")


# ------------------------------------------------------------------ Data API
def api(path, **params):
    params["key"] = KEY
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def api_pages(path, **params):
    while True:
        data = api(path, maxResults=50, **params)
        yield from data.get("items", [])
        if not data.get("nextPageToken"):
            return
        params["pageToken"] = data["nextPageToken"]


def api_playlists():
    return [{"id": p["id"], "title": p["snippet"]["title"], "count": p["contentDetails"]["itemCount"]}
            for p in api_pages("playlists", part="snippet,contentDetails", channelId=CHANNEL_ID)]


def api_playlist(pid):
    items = list(api_pages("playlistItems", part="snippet,contentDetails", playlistId=pid))
    ids = [i["contentDetails"]["videoId"] for i in items]
    full = {}
    for k in range(0, len(ids), 50):  # playlistItems truncates nothing, but videos gives publish date + full text
        for v in api("videos", part="snippet", id=",".join(ids[k:k + 50]), maxResults=50).get("items", []):
            full[v["id"]] = v["snippet"]
    return [{"position": i["snippet"]["position"], "video_id": vid,
             "title": full.get(vid, i["snippet"])["title"],
             "description": full.get(vid, i["snippet"]).get("description", ""),
             "published": full.get(vid, {}).get("publishedAt")} for i, vid in zip(items, ids)]


# ------------------------------------------------------------------ browser fallback
def browser():
    from playwright.sync_api import sync_playwright
    exe = os.environ.get("CHROMIUM_PATH") or next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")), None)
    pw = sync_playwright().start()
    b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
    return pw, b


def initial_data(page, url, var="ytInitialData"):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function(f"!!window.{var}", timeout=30000)
    return page.evaluate(f"window.{var}")


def walk(node, key):
    if isinstance(node, dict):
        if key in node:
            yield node[key]
        for v in node.values():
            yield from walk(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v, key)


def text(t):
    return "".join(r.get("text", "") for r in t.get("runs", [])) if "runs" in t else t.get("simpleText", "")


def web_playlists():
    pw, b = browser()
    page = b.new_page()
    data = initial_data(page, f"https://www.youtube.com/channel/{CHANNEL_ID}/playlists")
    out = []
    for vm in walk(data, "lockupViewModel"):
        pid = vm.get("contentId")
        title = (((vm.get("metadata") or {}).get("lockupMetadataViewModel") or {}).get("title") or {}).get("content")
        if pid and title:
            out.append({"id": pid, "title": title})
    for r in walk(data, "gridPlaylistRenderer"):
        out.append({"id": r["playlistId"], "title": text(r["title"])})
    b.close(); pw.stop()
    return out


def web_video(page, vid):
    pr = initial_data(page, f"https://www.youtube.com/watch?v={vid}", "ytInitialPlayerResponse")
    d = pr.get("videoDetails", {})
    return {"title": d.get("title"), "description": d.get("shortDescription", ""),
            "published": pr.get("microformat", {}).get("playerMicroformatRenderer", {}).get("publishDate")}


def web_playlist(pid):
    pw, b = browser()
    page = b.new_page()
    data = initial_data(page, f"https://www.youtube.com/playlist?list={pid}")
    vids = [(int(text(r.get("index", {})) or 0), r["videoId"]) for r in walk(data, "playlistVideoRenderer")]
    out = []
    for pos, vid in vids:
        out.append({"position": pos, "video_id": vid, **web_video(page, vid)})
    b.close(); pw.stop()
    return out


# ------------------------------------------------------------------ cli
def playlists():
    return api_playlists() if KEY else web_playlists()


def find_playlist(name_or_id):
    if re.fullmatch(r"PL[\w-]{10,}", name_or_id):
        return name_or_id, name_or_id
    want = re.sub(r"[^a-z0-9]", "", name_or_id.lower())
    for p in playlists():
        if want in re.sub(r"[^a-z0-9]", "", p["title"].lower()):
            return p["id"], p["title"]
    sys.exit(f"no playlist matching {name_or_id!r}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "playlists":
        for p in playlists():
            print(f"{p['id']}  {p['title']}  {p.get('count', '')}")
    elif cmd == "playlist":
        pid, title = find_playlist(args[0])
        items = api_playlist(pid) if KEY else web_playlist(pid)
        OUT.mkdir(parents=True, exist_ok=True)
        dest = OUT / (re.sub(r"[^\w]+", "-", title).strip("-").lower() + ".json")
        dest.write_text(json.dumps({"playlist_id": pid, "title": title, "items": items}, indent=1))
        for it in items:
            print(f"{it['position']:>3}  {it['video_id']}  {it.get('published') or '':<20}  {it['title']}")
        print(f"saved {dest}")
    elif cmd == "video":
        if KEY:
            s = api("videos", part="snippet", id=args[0])["items"][0]["snippet"]
            print(json.dumps({"title": s["title"], "description": s["description"], "published": s["publishedAt"]}, indent=1))
        else:
            pw, b = browser()
            print(json.dumps(web_video(b.new_page(), args[0]), indent=1))
            b.close(); pw.stop()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
