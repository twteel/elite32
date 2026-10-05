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

4. **Default: YouTube's free stills (user's choice, no OpusClip credits).** With only a
   `youtube_id`, the frames step grabs the full video where YouTube allows it and otherwise
   YouTube's 4 free 1280x720 stills (thumbnail + frames at 25/50/75%). Don't submit new
   OpusClip projects for footage unless the user asks: each one costs at least 10 credits.
   Use OpusClip footage only when a project already exists (Premiere export, below).
   If the stills don't show the guest, pin the best still with `guest_frames` and say so.
   Get frames from the YouTube video, never from OpusClip clips. OpusClip reframes its
   clips to vertical 9:16, which crops people's arms and shoulders off; the cutouts come out
   chopped. The `frames` step reads each episode's `youtube_id` and pulls a still every 10s
   from the full-width episode (up to 1080p). Nothing to do here beyond making sure
   `youtube_id` is right. To use a local file instead, set `frame_sources` (video files or
   stills). `sources` is only for research links.
   **In a cloud session YouTube blocks video downloads** ("Sign in to confirm you're not a
   bot"). Use OpusClip's Premiere export instead: it carries the ORIGINAL 1920x1080 footage,
   uncropped. For 3+ top clips per episode (pick clips where the guest talks; check the
   `thumbnail_url`s if a guest is barely in them): `opusclip_export_clip` with
   `target: "xml"`, poll until `ready`, `curl` the `export_url` zip to
   `work/premiere/<id>/<clip_id>.zip`, then
   `python pipeline.py import-premiere <id> work/premiere/<id>/*.zip`. The frames step uses
   those videos automatically. Some shows have only one wide camera on the guest; if the
   guest's face is under ~120px tall, pin their sharpest frontal frame with `guest_frames`
   and tell the user the cut-out will be softer.

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

## SEO rules (consistency + visibility) - apply to every episode

- **Title:** `Guest: Hook | Search phrase | Show Podcast` (under 100 characters; the hook from the
  artwork comes first after the guest, then what people actually search: a place, program, school,
  team or topic - "The Voice of Rucker Park", "LES Express", "Nazareth Point Guard"). Show suffix is
  always "Ballin' 4 Peace Podcast" or "Wavy World Podcast". No episode numbers.
- **Description:** line 1 = the hook + who the guest is and why they matter (names, schools,
  programs). Then guests with handles, hosts, follow line, and the same 3 show hashtags first
  (#Ballin4Peace #Basketball #NYCHoops / #WavyWorld #StrongIsland #LongIsland) - YouTube shows the
  first three above the title. Add chapters when a transcript is available: a block right after
  line 1, starting `0:00 Intro`, at least 3 entries, each 10s+ apart, labelled by topic. The
  OpusClip transcript (opusclip_get_transcript, read-only) works if the project's length matches the
  live video; YouTube captions can't be read with this sign-in.
- **Links block** (just above the hashtags): "Watch every <Show> episode: <playlist URL>",
  "Subscribe: https://www.youtube.com/@ballin4peacetv?sub_confirmation=1",
  "Ballin' 4 Peace: https://ballin4peace.org".
- **Tags:** guest names, programs/schools, topics, then the show's standard tags.
- **Playlist:** every public episode in "Ballin' 4 Peace Podcast" or "Wavy World", once, newest first.
- Thumbnail, title, description and Instagram caption always carry the same hook.

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

## Publish to YouTube (from a cloud session, no browser)

`podcast-art/youtube_publish.py` applies `publish/youtube-updates.json` through the YouTube Data API.
Client file: `podcast-art/work/.youtube-client.json` (git-ignored; the user's Google Cloud OAuth
client, project roster-setup-477501). Sign-in: `python youtube_publish.py login` gives a code for
google.com/device. Tell the user to open it in a PRIVATE/INCOGNITO window, sign in as
info@ballin4peace.org and pick the Ballin' 4 Peace channel; otherwise Google silently uses their
personal Gmail (no channel -> 403). `whoami` must say `-> CAN EDIT` (the brand account shows up as
ballin4peace-…@pages.plusgoogle.com; that's correct). Then `plan`, test one video with
`apply <video_id>`, then `apply`. YouTube re-orders tags alphabetically; a read right after a write
can lag, so re-check before calling something failed.

## Save it for the user

Folders are grouped by show (`Ballin 4 Peace Covers/<Show>/<episode>/`), and every export
also writes one zip of everything next to it (`... - all covers <date>.zip`) for the team's
Google Drive. `python pipeline.py archive` rebuilds just the zip. Send the zip to the user.

`python pipeline.py export` makes one ready-to-post folder per episode:
`<date> <Guest> - <Hook>/` with `YouTube thumbnail.jpg`, `Instagram post.jpg`,
`Instagram Reels + Stories cover.jpg`, `Podcast cover (Spotify, Apple).jpg` and
`captions.txt` (YouTube title + description, Instagram caption, tags, link).
- Run from the user's own computer (Claude desktop app), it saves to
  `~/Desktop/Ballin 4 Peace Covers/` automatically. Tell them the path.
- In a cloud session it saves to `podcast-art/export/` (not committed): send the folder's
  files to the user (SendUserFile) or upload them where they ask (Google Drive / Netlify).
- `--to <folder>` saves anywhere else.

## Shows

- **Ballin' 4 Peace** (`b4p`): hosts Slim the Announcer & H20. Dark "Court Light" room.
- **Wavy World** (`wavy`): host Wavy Walker, "the voice of Strong Island", powered by NYC
  Elite 32 x Ballin' 4 Peace. OpusClip projects titled "WW-..." or whose intro says
  "Wavy World" / "One Take Cult". Its covers use the user's purple wave background in full
  colour (`"room": "raw"` in shows.json, `brand/wavy/`), the same B&W cut-outs and hook
  blocks, and the Wavy World lockup. Episode ids start with `ww-`. Instagram: @wavyworldpod.
  Many guests are high school players: never tag a minor's personal handle unless the user
  gives it; tag the show accounts.
- Hosts are detected per show, so a guest on one show (Wavy on Ballin' 4 Peace) can be the
  host of another.
- **Show art** (the podcast's own cover, not an episode): an entry with `"kind": "show"`,
  `"formats": ["square", "cover3000"]`, `"no_lockup": true`, a `label`, and a hook with a
  hand-set line break (`"Ballin'|4 Peace"`). Hosts come from `brand/<show>/hosts/*.png`.
  `cover3000` is the square layout at 3000x3000 for Apple Podcasts / Spotify.
- **No episode numbers** anywhere in our creative (covers, captions, descriptions): the user's
  numbering has gaps, so `episode_numbers_on_covers` is false for both shows. Leave the
  user's own YouTube titles as they are.
- After a batch, run `python publish_kit.py <ids>` to refresh `publish/` (YouTube thumbnails +
  youtube-updates.json for a local Claude-in-Chrome session, and the Instagram pack + zip).
- Names on covers follow the user's spelling over anything found online (e.g. "Unsung Yutes").
- Background a guest is touching (e.g. a couch) can be erased: add `"erase": [[[x, y], ...]]` to
  that `guest_frames` entry (polygons as 0-1 fractions of the cut-out) and rerun `cutout` + `render`.
- `publish_kit.py <ids>` rewrites youtube-updates.json with only those ids: pass every episode,
  or merge the new row into the committed file.
- Studio sign letters stuck to a guest's hair are erased automatically
  (`drop_backdrop_signage`); if a chunk of backdrop still shows, pin another frame.

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
- **Hosts behind a guest** are deliberately dim, slightly soft and fade out from the chest
  down (user feedback: bright hosts competed with the guest). Don't brighten them.
- **YouTube thumbnail**: guests only. At 1280x720 there's no room for a back row, so hosts
  are left off (they stay on the Instagram and podcast covers). Hosts-only episodes still
  show the hosts.
- A host only appears on the episodes they're actually in (seen in 5+ frames).

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
