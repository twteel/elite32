"""Apply publish/youtube-updates.json to YouTube through the YouTube Data API (no browser needed).

One-time setup (Google Cloud Console, project of your choice):
  1. APIs & Services -> Library -> enable "YouTube Data API v3".
  2. OAuth consent screen -> External, add your Google account as a test user.
  3. Credentials -> Create credentials -> OAuth client ID -> type "TVs and Limited Input devices".
  4. Put the client ID and secret in the environment as YT_CLIENT_ID and YT_CLIENT_SECRET.

Then:
  python youtube_publish.py login-web  # on your computer: browser sign-in, pick the brand channel (recommended)
  python youtube_publish.py login      # code sign-in at google.com/device (personal channels only)
  python youtube_publish.py plan       # what will change (reads current titles from YouTube)
  python youtube_publish.py apply      # update title, description, tags and thumbnail, then verify

The sign-in is kept in work/.youtube-token.json (git-ignored, this machine only). Quota: about
100 units per video (update + thumbnail) of the 10,000 per day.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
TOKEN = ROOT / "work" / ".youtube-token.json"
UPDATES = ROOT / "publish" / "youtube-updates.json"
SCOPE = "openid email https://www.googleapis.com/auth/youtube"  # email: so we can show WHICH account signed in
API = "https://www.googleapis.com/youtube/v3"


CLIENT_FILE = ROOT / "work" / ".youtube-client.json"


def client():
    cid, sec = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
    if (not cid or not sec) and CLIENT_FILE.exists():  # the client_secret_*.json downloaded from Google Cloud
        c = json.loads(CLIENT_FILE.read_text())
        c = c.get("installed") or c.get("web") or c
        cid, sec = c["client_id"], c["client_secret"]
    if not cid or not sec:
        sys.exit("Set YT_CLIENT_ID and YT_CLIENT_SECRET in the environment first (see the top of this file).")
    return cid, sec


def jwt_email(id_token):
    """Read the signed-in email from Google's id_token (display only)."""
    import base64
    try:
        part = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("email")
    except Exception:
        return None


def whoami():
    """Which Google account and which YouTube channel(s) this sign-in can edit."""
    email = json.loads(TOKEN.read_text()).get("email") if TOKEN.exists() else None
    ch = api("GET", "channels", {"part": "snippet", "mine": "true"})
    chans = [f"{c['snippet']['title']} ({c['id']})" for c in ch.get("items", [])]
    print(f"Google account: {email or '(unknown - sign in again)'}")
    print(f"YouTube channel: {', '.join(chans) or 'NONE - this account has no channel, or the brand channel was not picked'}")
    v = snippet("OWo3uLkOLjQ")
    if v:
        owner = v["snippet"]["channelId"]
        ok = any(owner in c for c in chans)
        print(f"Ballin' 4 Peace channel: {v['snippet']['channelTitle']} ({owner}) -> {'CAN EDIT' if ok else 'cannot edit with this sign-in'}")
    return bool(chans)


def post_form(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def login():
    cid, sec = client()
    d = post_form("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": SCOPE})
    if "device_code" not in d:
        sys.exit(f"Google refused the sign-in request: {d}")
    print(f"On your phone or computer open {d['verification_url']} and enter the code:  {d['user_code']}")
    print("Sign in with the Google account that owns the YouTube channel. Waiting...", flush=True)
    wait = d.get("interval", 5)
    deadline = time.time() + d.get("expires_in", 1800)
    while time.time() < deadline:
        time.sleep(wait)
        t = post_form("https://oauth2.googleapis.com/token", {
            "client_id": cid, "client_secret": sec, "device_code": d["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if "refresh_token" in t:
            TOKEN.parent.mkdir(parents=True, exist_ok=True)
            TOKEN.write_text(json.dumps({"refresh_token": t["refresh_token"], "email": jwt_email(t.get("id_token", ""))}))
            TOKEN.chmod(0o600)
            _access.clear()
            print("Signed in.")
            whoami()
            return
        if t.get("error") == "slow_down":
            wait += 5
        elif t.get("error") not in ("authorization_pending",):
            sys.exit(f"Sign-in failed: {t}")
    sys.exit("The code expired. Run login again.")


def login_web():
    """Browser sign-in on YOUR computer: Google shows 'Choose an account or brand account', so you can
    pick the Ballin' 4 Peace channel. Saves the sign-in to work/.youtube-token.json and prints the
    line to add to the cloud environment (as the YT_REFRESH_TOKEN variable) - never paste it in chat."""
    import http.server
    import webbrowser
    cid, sec = client()
    port = 8765
    redirect = f"http://localhost:{port}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent select_account"})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab and go back to the terminal.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("localhost", port), H)
    print("Opening your browser. Pick the Ballin' 4 Peace channel (brand account) when Google asks.")
    print(f"If it doesn't open, visit:\n{url}")
    webbrowser.open(url)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if "error" in got:
        sys.exit(f"Sign-in cancelled: {got['error']}")
    t = post_form("https://oauth2.googleapis.com/token", {
        "client_id": cid, "client_secret": sec, "code": got["code"], "grant_type": "authorization_code",
        "redirect_uri": redirect})
    if "refresh_token" not in t:
        sys.exit(f"Sign-in failed: {t}")
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps({"refresh_token": t["refresh_token"], "email": jwt_email(t.get("id_token", ""))}))
    TOKEN.chmod(0o600)
    _access.clear()
    print("Signed in.")
    whoami()
    print("To let a cloud Claude session publish, add this environment variable in its settings (not in chat):")
    print(f"YT_REFRESH_TOKEN={t['refresh_token']}")


_access = {}


def access_token():
    if _access.get("exp", 0) > time.time() + 60:
        return _access["tok"]
    refresh = os.environ.get("YT_REFRESH_TOKEN") or (json.loads(TOKEN.read_text())["refresh_token"] if TOKEN.exists() else None)
    if not refresh:
        sys.exit("Not signed in. Run: python youtube_publish.py login-web (on your computer) or login")
    cid, sec = client()
    t = post_form("https://oauth2.googleapis.com/token", {
        "client_id": cid, "client_secret": sec, "grant_type": "refresh_token", "refresh_token": refresh})
    if "access_token" not in t:
        sys.exit(f"Could not refresh the sign-in ({t.get('error')}). Run login again.")
    _access.update(tok=t["access_token"], exp=time.time() + t.get("expires_in", 3600))
    return _access["tok"]


def api(method, path, params=None, body=None, upload=None, ctype=None):
    base = "https://www.googleapis.com/upload/youtube/v3" if upload else API
    url = f"{base}/{path}?{urllib.parse.urlencode(params or {})}"
    data = upload if upload is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {access_token()}")
    if data is not None:
        req.add_header("Content-Type", ctype or "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b"{}").get("error", {})
        return {"_error": f"{e.code} {err.get('message', '')}".strip()}


def snippet(video_id):
    r = api("GET", "videos", {"part": "snippet,status", "id": video_id})
    items = r.get("items") or []
    return items[0] if items else None


def plan():
    whoami()
    print()
    rows = json.loads(UPDATES.read_text())
    for r in rows:
        v = snippet(r["video_id"])
        cur = v["snippet"]["title"] if v else "(not found on this channel)"
        vis = v["status"]["privacyStatus"] if v else "-"
        print(f"{r['video_id']} [{vis}]\n  now: {cur}\n  new: {r['new_title']}")
    print(f"\n{len(rows)} videos. Run 'apply' to update title, description, tags and thumbnail.")


def apply(only=None):
    if not whoami():
        sys.exit("Stopping: this sign-in can't edit any channel. Sign in again as the channel owner.")
    rows = json.loads(UPDATES.read_text())
    if only:
        rows = [r for r in rows if r["video_id"] in only or r["episode"] in only]
    done, failed = [], []
    for r in rows:
        vid = r["video_id"]
        v = snippet(vid)
        if not v:
            failed.append((vid, "video not found on this channel (wrong account, or deleted)"))
            continue
        sn = v["snippet"]
        body = {"id": vid, "snippet": {
            "title": r["new_title"] or sn["title"],
            "description": r["new_description"] or sn.get("description", ""),
            "tags": r["tags"] or sn.get("tags", []),
            "categoryId": sn["categoryId"],
            **({"defaultLanguage": sn["defaultLanguage"]} if sn.get("defaultLanguage") else {})}}
        u = api("PUT", "videos", {"part": "snippet"}, body)
        if "_error" in u:
            failed.append((vid, f"text: {u['_error']}"))
            continue
        thumb = REPO / r["thumbnail"]
        t = api("POST", "thumbnails/set", {"videoId": vid}, upload=thumb.read_bytes(), ctype="image/jpeg")
        check = snippet(vid)["snippet"]
        problems = []
        if check["title"] != body["snippet"]["title"] or sorted(t.lower() for t in check.get("tags", [])) != sorted(t.lower() for t in body["snippet"]["tags"]):
            problems.append("title/tags did not stick")
        if "_error" in t:
            problems.append(f"thumbnail: {t['_error']}")
        (failed if problems else done).append((vid, "; ".join(problems) or check["title"]))
        print(("FAIL " if problems else "OK   ") + f"{vid}  {check['title']}" + (f"  ({'; '.join(problems)})" if problems else ""), flush=True)
    print(f"\nUpdated {len(done)} of {len(rows)}.")
    for vid, why in failed:
        print(f"  FAILED {vid}: {why}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "login":
        login()
    elif cmd == "login-web":
        login_web()
    elif cmd == "whoami":
        whoami()
    elif cmd == "plan":
        plan()
    elif cmd == "apply":
        apply(sys.argv[2:])  # optional: video ids or episode ids to do just those
    else:
        sys.exit(__doc__)
