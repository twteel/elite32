"""List channel uploads that look like podcast episodes and haven't been through the publish kit yet.

  python new_uploads.py            # long uploads (5+ min, not #shorts) missing from publish/youtube-updates.json
  python new_uploads.py --since 2026-10-01

Episodes still processing on YouTube are listed too (their stills may not exist yet).
"""
import json
import re
import sys
from pathlib import Path

import youtube_publish as y

ROOT = Path(__file__).resolve().parent
done = {r["video_id"] for r in json.loads((ROOT / "publish" / "youtube-updates.json").read_text())}
since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else "2000"


def seconds(d):
    m = re.match(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    h, mi, s = [int(x or 0) for x in m.groups()]
    return h * 3600 + mi * 60 + s


uploads = y.api("GET", "channels", {"part": "contentDetails", "mine": "true"})["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
ids = [i["snippet"]["resourceId"]["videoId"] for i in y.api("GET", "playlistItems", {"part": "snippet", "playlistId": uploads, "maxResults": 50})["items"]]
found = 0
for v in y.api("GET", "videos", {"part": "snippet,status,contentDetails", "id": ",".join(ids)})["items"]:
    s = v["snippet"]
    if v["id"] in done or s["publishedAt"] < since or "#shorts" in s["title"].lower() or seconds(v["contentDetails"]["duration"]) < 300:
        continue
    found += 1
    print(f"{s['publishedAt'][:16]}  {v['id']}  {v['status']['privacyStatus']:8}  {v['contentDetails']['duration']:10}  {s['title']}")
print(f"{found} new episode upload(s)")
