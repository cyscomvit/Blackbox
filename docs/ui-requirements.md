# Local UI verification

The visual updates preserve the admin panel as the place to manage the site-wide theme. The existing background CSS, Preview and Save controls remain in that panel. Participants have no theme selector or UI requirements page.

The leaderboard requires a signed-in account. The existing admin visibility switch controls participant access; admins can continue inspecting hidden standings. Both HTTP and live updates honour that setting. An already-open participant leaderboard closes when an admin disables it.

The home page has no challenge-category list or personal GitHub footer link. Layout changes use grid/flex, 8px spacing and 4px corners. The background is an unobscured local image at `static/images/background.png` that remains visible across palette changes, with opacity confined to content panels; no gradients, neon, decorative shadows or hover movement are used.

## Python dependencies

`requirements.txt` contains runtime dependencies. Gunicorn is limited to non-Windows installations. `requirements-win.txt` includes the shared runtime manifest so the two do not drift. Optional test dependencies are in `requirements-dev.txt`. Static images and browser libraries need no additional Python packages.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ui -v
.\.venv\Scripts\python.exe scripts\preview_ui.py
# In another terminal, with the preview running and Edge installed:
.\.venv\Scripts\python.exe tests\browser_ui.py
```

Open http://127.0.0.1:5050. Accounts: `preview-admin` and `preview-player`, password `PreviewOnly123!`. Data is disposable and is reset by restarting the preview. It does not connect to the configured production database. Docker, SMTP and backup execution require their configured services.

Background image selected by the user: https://miro.medium.com/v2/resize:fit:4800/format:webp/1*-oNPWS2F4TMge19BuO8bPg.png


Leaderboard performance: uncached standings use bulk scalar solve reads and one dynamic value calculation per challenge, instead of per-entrant/per-solve database queries. Existing score rules, hint deductions, adjustments and timestamps are preserved. The client shares the notification socket and consumes solve broadcasts without requesting another full board after every solve. REST remains the initial load and 30-second recovery path. Protocol payload logging is enabled only in Flask debug mode.

Run `.venv\Scripts\python.exe -m unittest tests.test_scoreboard_performance` to check parity and query bounds. Local SQLite benchmark with 250 active teams: previous team score calculation 1,249 SQL queries / 553 ms; bulk calculation 6 queries / 16 ms. These are local measurements, not production latency guarantees. Production database/network/Redis timings have not been measured. The existing 100-entry display limit remains in place.


## Competition workspace

Challenge cards share category, difficulty, points, solves and explicit solved/locked states. Category and unsolved filters work within the active ACT. Hidden challenges remain undisclosed until unlocked; visible locked cards do not grant access to challenge details.

Announcements remain in the original navbar menu. The competition-status strip and scoreboard summary tiles are removed. The scoreboard uses an opaque themed base with only the CYSCOM logo watermark, and the same logo appears as the favicon. Instance expiry remains beside its existing controls.

The leaderboard supports top 100 and nearby ranks (including ranks outside the top 100), highlights the current entrant, and counts first bloods. Admin Settings ? Event Configuration ? Freeze public scoreboard captures durable team and individual snapshots. Unchecking and saving releases the freeze. Admins see live standings; participant HTTP and socket responses use the snapshot. The visibility switch still takes precedence. This freezes standings only, not challenge values, profiles or submissions.

Run `python -m unittest tests.test_competition_workspace.CompetitionWorkspace` for freeze/access/nearby checks. Run `tests/browser_competition.py` after `tests/browser_ui.py` on a fresh preview. Set `UI_BASE_URL` to use a different preview port; `scripts/preview_ui.py --port 5052` runs one on port 5052.

The Default palette uses navy (#0B1220), slate panels (#151F2E), soft white (#E6EDF5), and CYSCOM blue (#4DA3FF). Shared buttons, quieter borders, compact challenge cards, and the unified navbar apply across all five admin-selectable palettes. The page photo remains unobscured between panels; standings retain their opaque base and CYSCOM watermark.

Graphite is a separate near-black palette with blue accents; Default preserves the original navy palette. Tick icons and avatar placeholders are removed. Checkbox selection uses a filled square, login/register share typography, and challenge metadata uses an aligned 8px gap.
