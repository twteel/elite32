"""Build podcast-art/publish/: YouTube thumbnails + youtube-updates.json, and the Instagram pack (+ zip).

Usage: python publish_kit.py ep-id ep-id ...   (episodes that have renders in out/)
Keeps current_title / new_title already recorded in publish/youtube-updates.json.
"""
import json, re, shutil, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUB = ROOT / "publish"
E = {e["id"]: e for e in json.load(open(ROOT / "episodes.json"))}
S = json.load(open(ROOT / "shows.json"))
old = {r["episode"]: r for r in json.loads((PUB / "youtube-updates.json").read_text())} if (PUB / "youtube-updates.json").exists() else {}
ids = sys.argv[1:] or list(old)
SHOW_ACCOUNTS = {"@ballin4peace", "@wavyworldpod", "@nycelite32"}

(PUB / "youtube").mkdir(parents=True, exist_ok=True)
ig = PUB / "instagram"
shutil.rmtree(ig, ignore_errors=True)
rows = []
for i in ids:
    e, prev = E[i], old.get(i, {})
    vid = prev.get("video_id") or e["youtube_id"]
    art = (ROOT / "out" / f"{i}_yt.jpg").exists()
    keep = e.get("keep_youtube_thumbnail") or not art  # keep the cover already on YouTube (or none made yet)
    if not keep:
        shutil.copy(ROOT / "out" / f"{i}_yt.jpg", PUB / "youtube" / f"{vid}.jpg")
    yt = e.get("youtube") or {}
    rows.append({"video_id": vid, "show": S[e["show"]]["name"], "episode": i,
                 "studio_url": f"https://studio.youtube.com/video/{vid}/edit",
                 "thumbnail": None if keep else f"podcast-art/publish/youtube/{vid}.jpg",
                 "current_title": prev.get("current_title"), "new_title": yt.get("title"),
                 "why": prev.get("why") or "Title matches the thumbnail hook",
                 "new_description": yt.get("description"), "tags": yt.get("tags", [])})
    g = e.get("guests") or e.get("guest") or ""
    names = "The Pinnocks" if i == "ww-26-pinnock" else (" & ".join(g) if isinstance(g, list) else g)
    name = re.sub(r'[\\/:*?"<>|]', "", f"{names + ' - ' if names else ''}{e['hook'].replace('|', ' ')}").strip()
    d = ig / S[e["show"]]["name"] / name
    d.mkdir(parents=True)
    if art:
        shutil.copy(ROOT / "out" / f"{i}_post.jpg", d / "1 Feed post (4x5).jpg")
        shutil.copy(ROOT / "out" / f"{i}_story.jpg", d / "2 Reels + Stories cover (9x16).jpg")
    c = e.get("instagram") or {}
    account = "@ballin4peace" if e["show"] == "b4p" else "@wavyworldpod"
    collab = [t for t in c.get("tags", []) if t not in SHOW_ACCOUNTS]
    (d / "caption.txt").write_text(f"POST FROM: {account}\n\nCAPTION\n{c.get('caption', '').strip()}\n\n"
                                   f"INVITE AS COLLABORATOR: {' '.join(collab) or '(none on file)'}\n"
                                   f"TAG IN PHOTO: {' '.join(t for t in c.get('tags', []) if t != account)}\n\n"
                                   f"YOUTUBE: https://youtu.be/{vid}\n")
(ig / "HOW TO POST.txt").write_text("Each folder = one episode.\n1 Feed post (4x5).jpg -> Instagram feed post (1080x1350)\n"
                                     "2 Reels + Stories cover (9x16).jpg -> the episode's Reel cover, or a Story (1080x1920)\n"
                                     "caption.txt -> caption, which account to post from, collaborator invites, YouTube link\n")
(PUB / "youtube-updates.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
z = PUB / "Instagram posts - all episodes.zip"
with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
    for f in sorted(ig.rglob("*")):
        if f.is_file():
            zf.write(f, Path("Instagram posts") / f.relative_to(ig))
print(f"{len(rows)} episodes -> {PUB}")
