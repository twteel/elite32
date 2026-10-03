# Elite 32 Live Scores — iPhone app + WordPress backend

Post a score once a day or 80 times a day, from anywhere. Every iPhone running the app sees it within about 15 seconds, and so does the website.

```
 Scorekeeper (iPhone app or wp-admin on any phone)
          │  tap +2
          ▼
 WordPress site (Cloudways) ── plugin "Elite32 Live Scores"
          │  /wp-json/elite32/v1/games
          ├──────────────► Elite 32 iPhone app (fans), refreshes every 15 s
          └──────────────► [elite32_scores] scoreboard on the website
```

You don't need a new server or another monthly bill. Your existing WordPress site stores the scores.

| Folder | What it is |
| --- | --- |
| `wordpress-plugin/elite32-scores/` | WordPress plugin: stores games and serves the API. It adds the scorekeeper screen in wp-admin and the website scoreboard. |
| `elite32-scores-plugin.zip` | The same plugin, zipped and ready to upload. |
| `ios/` | The iPhone app (SwiftUI, iOS 17+). Open `ios/Elite32Scores.xcodeproj` in Xcode. |

---

## 1. Install the plugin (5 minutes)

1. In WordPress, go to **Plugins → Add New → Upload Plugin**, choose `elite32-scores-plugin.zip`, then click **Install** and **Activate**.
2. An **Elite32 Scores** item now appears in the wp-admin menu. This is the scorekeeper screen, and it works well on a phone browser too.
3. To show live scores on the website, add the shortcode `[elite32_scores]` to any page. Options:
   - `[elite32_scores event="Middle School Madness"]` shows one event only.
   - `[elite32_scores status="live"]` shows live games only.

**Caching (important on Cloudways).** The API already sends `no-cache` headers. If scores look stale, exclude `/wp-json/elite32/` from caching:
- Cloudways → Application → **Varnish settings** → add an exclusion URL `/wp-json/elite32/*`.
- If you use **Breeze**: Settings → Advanced → *Never cache URLs* → add `/wp-json/elite32/*`.
- If you use **Cloudflare**: add a Cache Rule that bypasses cache for `/wp-json/elite32/*`.

## 2. Add games

Use any of these:
- **wp-admin → Elite32 Scores → "Paste a whole schedule"** is fastest for a tournament. Put one game per line:
  ```
  2026-04-04 10:00 | Middle School Madness | 8th Grade Boys | Court 1 | Queens Kings | Brooklyn Elite
  2026-04-04 11:15 | Middle School Madness | 7th Grade Girls | Court 2 | Bronx Ballers | LI Lightning
  ```
- **wp-admin → Elite32 Scores → "Add a game"**
- **iPhone app → Scorekeeper tab → +**

Times use the site's time zone (WordPress → Settings → General).

## 3. Update scores

**In the iPhone app:** open **Scorekeeper**, tap a game, and use the big **+1 / +2 / +3** buttons (**−1** fixes mistakes). Set the period (Q1…OT) and mark the game **Final**. The first basket flips a scheduled game to **Live** automatically.

**In a browser:** go to wp-admin → **Elite32 Scores** and use the same buttons.

Several scorekeepers can work at once, even on the same game. Each tap is saved as a single atomic "+2", so taps never overwrite each other. I tested this with 40 simultaneous taps.

### Give someone scorekeeper access
1. Create a WordPress user for them with the **Editor** or **Administrator** role. Both roles get the `manage_e32_scores` permission when the plugin is activated.
2. Logged in as that user, go to **Users → Profile → Application Passwords**, type "iPhone", and click **Add New Application Password**.
3. In the app: **Scorekeeper** tab → WordPress username + that application password. It is stored in the iPhone Keychain.

To cut off access, revoke the application password. Fans never sign in; reading scores is public.

> If sign-in always fails even with the right password, the host is stripping the `Authorization` header. On Apache, add this to `.htaccess` above the WordPress block:
> `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`

## 4. Build the iPhone app

You need a Mac with **Xcode 16 or newer** and an Apple Developer account ($99/yr to publish on the App Store; free to run on your own phone).

1. Open `ios/Elite32Scores.xcodeproj`.
2. If the site moves to its real domain, change `siteURL` in `ios/Elite32Scores/Config.swift`.
3. Select the **Elite32Scores** target → **Signing & Capabilities**. Pick your Team, and change the Bundle Identifier if `com.elite32.scores` is taken.
4. Plug in your iPhone, select it as the run destination, and press **Run**.
5. To publish: **Product → Archive → Distribute App → App Store Connect**. Then use TestFlight for staff or submit for review for the public.

The app icon is a placeholder (`Assets.xcassets/AppIcon.appiconset/AppIcon.png`, 1024×1024, no transparency). Swap in the real logo before publishing.

### What's in the app
- **Scores tab:** Live / Today / Upcoming / Final, grouped by event. It refreshes every 15 s while open, supports pull-to-refresh, and has a game detail screen.
- **Scorekeeper tab:** sign in, add or edit games, keep score with big buttons and haptics, set status and period, and delete games.

---

## API reference

Base: `https://<site>/wp-json/elite32/v1`

| Method | Path | Who | Body / query |
| --- | --- | --- | --- |
| GET | `/games` | public | `?status=live`, `?event=Name`, `?date=2026-04-04`, `?all=1` (default: last 3 days onward + all live) |
| GET | `/games/{id}` | public | |
| POST | `/games` | scorekeeper | `{"home_team","away_team","event_name","division","venue","starts_at"}` |
| PATCH | `/games/{id}` | scorekeeper | any of the fields above + `home_score`, `away_score`, `status`, `period` |
| POST | `/games/{id}/points` | scorekeeper | `{"side":"home","points":2}` (−10…10) |
| DELETE | `/games/{id}` | scorekeeper | |
| GET | `/me` | scorekeeper | checks sign-in |

`status` is one of `scheduled`, `live`, `final`, `postponed`, `canceled`. Times are returned in UTC (ISO 8601). Scorekeeper calls use HTTP Basic auth with a WordPress Application Password.

Example (good for automation such as Zapier, a stats app, or a spreadsheet):
```sh
curl -u 'coach:abcd efgh ijkl mnop qrst uvwx' -X POST \
  https://<site>/wp-json/elite32/v1/games/12/points \
  -H 'Content-Type: application/json' -d '{"side":"home","points":3}'
```

## Ideas for later
- Push notifications for final scores (needs APNs + a small sender; the plugin's `updated_at` and `revision` fields are ready for it).
- Standings and brackets computed from final scores.
- A Home Screen widget / Live Activity for a followed game.
