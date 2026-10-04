---
name: podcast-covers
description: The Ballin' 4 Peace podcast agent. Optimizes each episode's YouTube title + description and Instagram caption in the user's house style, makes cover art, and saves ready-to-post folders for Ballin' 4 Peace podcast episodes (and any other show in podcast-art/shows.json). Pulls stills from each episode's full YouTube video, finds the hosts and the guest, cuts them out, and renders the approved "Court Light" design as a YouTube thumbnail, Instagram post, Instagram Reels/Stories cover and square podcast cover. Use when the user says "make covers", "new episode", "do the art for ep X", "redo the thumbnails", or "/podcast-covers".
---

# Podcast covers agent

Everything lives in `podcast-art/`. The look is locked; **do not restyle it** unless the user
asks. `podcast-art/DESIGN.md` is the brief and `podcast-art/template/cover.html` is the design.

## What you produce, per episode

| file | size | where it goes |
|---|---|---|
| `out/<id>_yt.jpg` | 1280x720 | YouTube thumbnail |
| `out/<id>_post.jpg` | 1080x1350 | Instagram feed post (4:5) |
| `out/<id>_story.jpg` | 1080x1920 | Instagram Reels cover + Stories (key content kept inside IG's safe zone) |
| `out/<id>_square.jpg` | 1080x1080 | Spotify / Apple Podcasts |

Plus `out/review-sheet.jpg`: every episode in every format, for the user to approve.

## Steps

1. **Setup** (once per session):
   `cd podcast-art && pip install -r requirements.txt`
   On the user's Mac also make sure of: `ffmpeg` (`brew install ffmpeg` if missing) and a
   browser for rendering (`python -m playwright install chromium`, once). For YouTube, use
   Claude in Chrome if it's available. Frames come from the YouTube video itself (yt-dlp), so
   the network must allow `www.youtube.com` and `*.googlevideo.com`. If frames fail to
   download, tell the user to add them under the environment's Network access → Allowed
   domains (or run the agent on their Mac), and stop. The OpusClip connector is optional:
   only for clip titles and transcripts.

2. **Start from YouTube - it is the source of truth.** The user keeps titles, descriptions and the
   "Ballin' 4 Peace Podcast" playlist up to date there: episode order/numbers, guest real names
   (often only in the description), and links. Read it before anything else, in this order:
   - **Browser first** (best): if this session has a browser tool (Claude in Chrome, computer
     use, or the Claude desktop app on the user's machine), open
     https://www.youtube.com/@ballin4peacetv/playlists, open the Ballin' 4 Peace Podcast
     playlist, and read every video's title + full description ("...more").
   - **Script**: `python youtube.py playlist "Ballin' 4 Peace Podcast"` saves
     `work/youtube/<playlist>.json` (title, description, date, position per video). It uses
     `YOUTUBE_API_KEY` if set, otherwise drives Chromium on youtube.com.
   - In a cloud session youtube.com is blocked unless the environment allows
     `www.youtube.com` (Network access → Allowed domains). If neither works, say so and ask the
     user to run the agent in the Claude desktop app or paste the descriptions - don't guess.
   Match each YouTube video to its OpusClip project by `source_video_id` == YouTube video id.

   **Find the episodes in OpusClip.** Call the OpusClip MCP tool `opusclip_list_projects`. Ballin' 4 Peace
   episodes are the projects titled "B4P Ep. N - Guest" or "Untitled NN". Skip "WW-..."
   (that is Wavy's World, a different show).

3. **Update `podcast-art/episodes.json`.** One row per episode: `id` (`b4p-NN`), `show`,
   `ep`, `guest` (name, or null if it's just the hosts), `hook`, `youtube_id`
   (= the project's `source_video_id`), `opus_project`.
   - **Hook**: 2-5 words, the most clickable idea in the episode. Get it from the
     top-scoring clip titles (`opusclip_list_clips`). Never a full sentence.
   - **Guest name**: from clip titles/descriptions or the transcript (`opusclip_get_transcript`).
     If unsure, put your best guess and a note in `confirm`, and ask the user.
   - Hosts are **Slim the Announcer** and **H20** - never list them as the guest.
   - More than one guest: use `guests` (a list, most important first). See "Who is on the cover".

3b. **Research every guest before anything renders. Names on a cover must be exactly right.**
   Transcripts mishear names (an earlier run heard "Mike Lowrey" for **Mic Larry**, "Combo On 2"
   for **Combo**, @OneTwoCombo). For each guest:
   - Take the name from the intro in the transcript ("we got ___ in the building"), then
     WebSearch it with context from the episode (their tournament, league, show, film, school).
   - Use the spelling the person uses themselves: their own site, podcast page, IG handle,
     press about them, or ballin4peace.org. Keep their styling (e.g. "PoLo Jose").
   - Record what makes them relevant in `about` (1 line) and the links in `sources`.
     Use that to sharpen the hook (e.g. PoLo Jose -> his Tubi film "Dissection of the Dollar").
   - If you can't verify a name, write `NOT VERIFIED` in `confirm`, keep your best guess,
     and ask the user before publishing that episode. Never invent a full name.
   - Also confirm the episode is actually Ballin' 4 Peace: the intro says "Ballin' 4 Peace
     Podcast" with Slim. Wavy World episodes ("Wavy World", "One Take Cult", host Wavey
     Walker) belong to a different show; don't mix them in.

4. **Get frames from the YouTube video, never from OpusClip clips.** OpusClip reframes its
   clips to vertical 9:16, which crops people's arms and shoulders off; the cutouts come out
   chopped. The `frames` step reads each episode's `youtube_id` and pulls a still every 10s
   from the full-width episode (up to 1080p). Nothing to do here beyond making sure
   `youtube_id` is right. To use a local file instead, set `frame_sources` (video files or
   stills). `sources` is only for research links.

5. **Run it:** `python pipeline.py all` (or `python pipeline.py all b4p-17` for one episode).
   This grabs frames, finds every face, works out who the hosts are (faces seen across many
   episodes) and who the guest is (the most-seen face that isn't a host), cuts them out in
   black and white and renders all four formats plus the review sheet.

6. **Check the review sheet yourself before showing it.** Look at
   `out/review-sheet.jpg`. Things to catch:
   - wrong person as guest (a host, or a crowd face) → set `guest_frame` (path to a frame in
     `work/<id>/frames/`) and optionally `guest_box` [x, y, w, h] on that episode and rerun
     `python pipeline.py pick <id>` then `cutout` and `render`
   - a cut-out with missing hair/shoulders/arms or a leftover background chunk → pick another
     frame (one where the person isn't touching the edge of the shot)
   - title text that reads awkwardly → shorten the hook
   If there are fewer than 3 episodes processed, host detection can't work; put host
   cut-outs (transparent PNGs) in `brand/b4p/hosts/` instead.

7. **Deliver.** Run `python pipeline.py export` (see "Save it for the user"). Send the review sheet to the user. Only after they approve: publish/upload
   wherever they ask (Netlify, Google Drive, YouTube). Never overwrite live YouTube
   thumbnails without an explicit yes.

## YouTube titles + descriptions (same run, if needed)

The user has hand-optimized some videos on YouTube. That is the house style - copy it, don't
invent one.

1. **Learn the style** from the videos the user already fixed (read them in step 2; they are
   the ones with a consistent, polished title and a full description). Write down the pattern
   in `podcast-art/youtube-style.md` the first time (title formula, length, caps, how guests
   are named, description sections, links, hashtags, timestamps, sign-off) and reuse it after.
   If that file exists, follow it.
2. **Check every episode in the playlist** against it. Only touch the ones that don't match.
   Use the verified guest names from step 3b and the hook from the cover, so the title,
   thumbnail and description all say the same thing. Timestamps come from the OpusClip
   transcript (`opusclip_get_transcript`, paragraph `start_ms`).
3. **Show the user a before/after table** (title + first 2 lines of description per video)
   together with the cover review sheet. Nothing on YouTube changes before they say yes.
4. **Apply** in YouTube Studio with the browser (Details → Title, Description, Thumbnail →
   upload `out/<id>_yt.jpg`, Save), one video at a time, re-reading the page after saving to
   confirm it stuck. The YouTube Data API key is read-only; writing needs the logged-in
   browser (or OAuth, if set up).

## Instagram (same run)

Every episode also gets Instagram: the covers are already made (`post` = feed 4:5, `story` =
Reels cover + Stories 9:16). Write the caption too:

- Put it in `episodes.json` as `"instagram": {"caption": "...", "tags": ["@handle", ...]}`
  (and the final YouTube text as `"youtube": {"title": "...", "description": "..."}`).
- Caption: same hook and voice as the YouTube title, 2-4 short lines, the guest's real
  @handle (find it in step 3b, e.g. Combo = @onetwocombo), where to watch (link in bio /
  YouTube), and the same hashtags the user's YouTube style uses. Brand accounts:
  @ballin4peace (Ballin' 4 Peace) - check the account list with OpusClip
  `opusclip_list_social_accounts`.
- Suggest a collab tag with the guest so it lands on their profile too.
- Posting happens only after the user approves, and only if they ask: from the browser
  (instagram.com / Meta Business Suite) or by scheduling clips through OpusClip
  (`opusclip_schedule_publish`). Default is to hand them the files.

## Save it for the user

`python pipeline.py export` makes one ready-to-post folder per episode:
`<date> <Guest> - <Hook>/` with `YouTube thumbnail.jpg`, `Instagram post.jpg`,
`Instagram Reels + Stories cover.jpg`, `Podcast cover (Spotify, Apple).jpg` and
`captions.txt` (YouTube title + description, Instagram caption, tags, link).
- Run from the user's own computer (Claude desktop app), it saves to
  `~/Desktop/Ballin 4 Peace Covers/` automatically. Tell them the path.
- In a cloud session it saves to `podcast-art/export/` (not committed): send the folder's
  files to the user (SendUserFile) or upload them where they ask (Google Drive / Netlify).
- `--to <folder>` saves anywhere else.

## Who is on the cover

Every cover shows **everyone on the episode**: the guest(s) in the front row, the two hosts
(Slim the Announcer, H20) behind them on the outer edges, a step smaller and darker.

- **One guest**: set `"guest": "Name"`.
- **Several guests** (e.g. a father and son): set `"guests": ["Son Name", "Father Name"]`.
  The order is the importance order: the first name goes nearest the centre. The pipeline
  finds that many non-host faces and ranks them by screen time, so for anything sensitive pin
  the frames yourself with `"guest_frames": [{"frame": "work/<id>/frames/....jpg"}, ...]` in
  the same order (the face is found automatically; add `"box": [x, y, w, h]` only if the
  frame has several people).
- **Size**: people standing next to each other are equals, so the front row is the same size
  by default. `"cast_style": "ranked"` makes each next guest a step smaller.
- **Moving people by hand**: `"cast_layout": {"all": [{"x": 40, "h": 100, "z": 3}, ...]}`
  overrides position (x = centre, % of the photo area), height (% of the photo area) and
  stacking (z) per person, in the order guests (by rank) then hosts. Use a format key
  (`"yt"`, `"post"`, `"story"`, `"square"`) instead of `"all"` to change one format only.
  Leave an entry `null` to keep that person's automatic spot.
- **No guest**: the hosts take the front row. No people at all: a type-only layout.

## Changing things

- Edit names/hooks → `episodes.json`, then `python pipeline.py render` (no re-cut needed).
- Brand colours, logo, background, lockup → `shows.json` and `brand/b4p/`.
- Font: the design font is Druk Wide Bold. If `template/fonts/DrukWide-Bold.woff2` (or `.otf`)
  exists it is used; otherwise Archivo Expanded Black stands in.
- A new show: add it to `shows.json` with its own colours/assets and give its episodes
  that `show` key.

## Rules

- Commit `episodes.json` and any brand/template changes; `work/` and `out/` are not committed.
- Don't put the user's email or any credentials in files.
- Report honestly: which episodes rendered, which need a human check, and why.
