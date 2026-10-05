# YouTube updates (ready to apply)

`youtube-updates.json` lists every video to update. For each one:
1. Open `studio_url` (YouTube Studio, logged in as Ballin4Peace).
2. Thumbnail: upload `thumbnail` (1280x720, under 2 MB).
3. Title: replace it with `new_title`.
4. Description: replace it with `new_description`.
5. Tags: Show more -> Tags, clear the old tags and paste `tags` (comma separated).
6. Don't touch visibility, playlists or anything else.
7. Save, reload the page, and confirm thumbnail, title, description and tags stuck. Then the next video.

Paste this into a Claude session running on your computer (Claude Desktop with Claude in Chrome,
logged in to YouTube Studio), after `git pull`:

> Apply podcast-art/publish/youtube-updates.json in YouTube Studio with Claude in Chrome, one video at a
> time, exactly as podcast-art/publish/README.md says. Don't ask me before each one. At the end, list what
> changed and anything that failed.

## Instagram
`instagram/<Show>/<Episode>/` has the 4:5 feed post, the 9:16 Reels/Stories cover and `caption.txt`
(which account to post from, the caption, collaborator invites, the YouTube link).
`Instagram posts - all episodes.zip` is the same thing in one file.
