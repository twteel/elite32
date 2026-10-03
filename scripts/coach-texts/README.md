# Coach texts

Texts Instagram post images to coaches via Twilio MMS. The images are hosted in Google Drive.

1. Share each image in Drive as **Anyone with the link → Viewer**. Twilio has to be able to fetch it.
2. Fill in `coaches.csv` (`team,name,phone,consent`) and `posts.csv` (`team,drive_file_id,caption`).
   The Drive file ID is the part of the share link between `/d/` and `/view`.
3. Dry run (sends nothing):
   `node scripts/coach-texts/send.mjs coaches.csv posts.csv`
4. Send:
   `TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_FROM_NUMBER=+1... node scripts/coach-texts/send.mjs coaches.csv posts.csv --send`

Each post is texted to every coach on the same team (the team names are matched without regard to case).
Coaches without `consent=yes` or without a valid US phone number are skipped.
Before sending, the Twilio number must be registered for US business texting (A2P 10DLC).
Keep real `coaches.csv` files out of git, because they contain phone numbers.
