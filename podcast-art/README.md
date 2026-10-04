# Podcast cover art

Automatic cover art for Ballin' 4 Peace (and any other show added to `shows.json`).
For every episode it finds the guest's face in the episode video, cuts them out,
gives the photo a halftone print treatment and renders three sizes:
YouTube 1280x720, square 1080x1080 and vertical 1080x1920.

## How it finds the guest
Faces are pulled from every episode and grouped by person. Faces that show up in
lots of episodes are the hosts; the most-seen face that isn't a host is the guest.
Nobody has to tag anything. If an episode has no guest, it gets a type-only layout.
To force a frame, set `guest_frame` (and optionally `guest_box`) on the episode.

## Run
    pip install -r requirements.txt
    python pipeline.py import-opus clips/*.json   # OpusClip list_clips dumps -> frame sources
    python pipeline.py all                        # every episode -> out/
    python pipeline.py all b4p-14                 # one episode
    python pipeline.py render                     # re-render after editing hooks/names

An episode can also list its own `sources` (local video files, URLs or stills).

## Files
- `episodes.json` - one row per episode: number, guest name, hook (2-5 words), YouTube id.
  `confirm` notes what still needs checking.
- `shows.json` - show name, colours, logo.
- `template/cover.html` - the layout for all three sizes. Edit it to change the look.
