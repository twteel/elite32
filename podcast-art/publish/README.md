# YouTube updates (ready to apply)

`youtube-updates.json` lists every video to update. For each one:
1. Open `studio_url` (YouTube Studio, logged in as Ballin4Peace).
2. Thumbnail: upload `thumbnail` (1280x720, under 2 MB).
3. Title: if `new_title` is set, replace the title with it. If it's null, leave the title alone.
4. Don't touch descriptions, tags, visibility or playlists.
5. Save, reload the page, and confirm the thumbnail and title stuck. Then the next video.

Paste this into a Claude session running on your computer (Claude Desktop with Claude in Chrome,
logged in to YouTube Studio), after `git pull`:

> Apply podcast-art/publish/youtube-updates.json in YouTube Studio with Claude in Chrome, one video at a
> time, exactly as podcast-art/publish/README.md says. Don't ask me before each one. At the end, list what
> changed and anything that failed.
