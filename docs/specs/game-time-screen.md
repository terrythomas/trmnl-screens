# Spec: Game Time screen (v1)

Status: design settled, ready for issues
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

Knowing that a followed team plays today is easy; knowing what to turn on to watch it is not. Local channels, national networks, streaming exclusives and out-of-market packages change from game to game, and the free schedule sources disagree or leave the team's own local channel out. The household wants an ambient answer on the TRMNL display: who is playing today and tomorrow, when, and on which channel, and the screen should stay out of the playlist when there is nothing to show.

## Solution

A new **Screen**, **Game Time**, in `screens/game-time/`, fed by a **Collector** like the Media screen ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). The collector reads free public sources only, no keys or accounts:

- **ESPN's site API** for every league's schedule, status, scores, team logos and channels.
- **nba.com team schedule pages** for NBA local channels, which ESPN leaves out ([ADR-0008](../adr/0008-local-channels-from-league-sources.md)).
- **The MLB Stats API** for MLB local channels, which ESPN labels with the wrong side.

v1 covers the NBA, NFL, MLB, NHL and MLS. The template groups games into a Today and a Tomorrow section against the render time, so the screen appears, updates its sections and leaves the playlist on the clock, without a fetch.

The primary **Device** is the TRMNL X; the OG renders the same template ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)).

## Behaviour

### Followed teams
- `GAME_TIME_TEAMS` lists **followed teams** as `league:ESPN team abbreviation`, comma-separated, case-insensitive, e.g. `nba:bos, nfl:chi, mlb:sea, nhl:col, mls:atl`. Leagues: `nba`, `nfl`, `mlb`, `nhl`, `mls`.
- An entry that matches no team in ESPN's team list for that league is reported in the **error banner** ("Unknown team: nhl:xyz"); the other teams keep working.

### Games
- Source: ESPN `GET site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates=YYYYMMDD` for yesterday, today and tomorrow (local dates, `TZ`), for each league with a followed team. Yesterday is only read for games still **live** across midnight.
- Keep events where either competitor is a followed team. A game between two followed teams is one game.
- Game fields: league, start time (absolute), the local date it starts on, state (`scheduled`, `live`, `final`, `postponed`), status text for live games (ESPN's short detail, e.g. "Q3 5:12", "Bot 7th", "OT"), and both teams with abbreviation, short name, logo, score (live and final only) and home or away.
- ESPN's `STATUS_POSTPONED`, `STATUS_CANCELED` and `STATUS_SUSPENDED` all map to `postponed`.

### Channels
- Each broadcast is classified as one of:
  - **local channel** of a followed team: TV on that team's side of the game;
  - opponent's local channel: TV on the other side;
  - national TV;
  - streaming;
  - **out-of-market package**: ESPN type "Subscription Package", plus a fixed list of package names ESPN labels as streaming (MLB.TV, NHL Center Ice, ESPN+ for the NHL, NFL Sunday Ticket, NBA League Pass);
  - radio, which is dropped.
- The shown list, in order: local channels, or national TV when there are no local channels; then streaming. Only when that list is empty: the opponent's local channels and out-of-market packages.
- NBA TV channels come from the followed team's nba.com schedule page (`nationalBroadcasters`, `homeTvBroadcasters`, `awayTvBroadcasters`), read once a day and cached in the state directory, since the page carries the whole season. MLB TV channels come from `statsapi.mlb.com/api/v1/schedule?teamId=…&hydrate=broadcasts(all)`, using `homeAway` and `isNational`. Games are matched to ESPN events by start date and the two teams.
- When the NBA or MLB source fails or has no match for a game, that game falls back to ESPN's channels, is marked `channels_incomplete`, and the failure is logged. It does not raise the error banner.
- Channel names are normalised (several source spellings map to one channel) and looked up in the committed **channel map**, which gives each channel's icon source, or marks it deliberately text-only (e.g. Peacock). A channel missing from the map is shown by name and recorded as an **unknown channel**.

### Unknown channels
- `STATE_DIR/game-time/unknown-channels.json` holds one entry per unknown channel: name, league, first seen, last seen and times seen. Seeing it again updates the entry; nothing is appended. Adding the channel to the map removes the entry on the next run.

### Logos and channel icons
No logo or icon artwork is committed to the repository, including tests and fixtures ([ADR-0009](../adr/0009-logos-fetched-at-runtime.md)). The collector fetches the artwork at runtime, converts it, and caches the converted images in `STATE_DIR/game-time/logos/`, refreshing them weekly.
- **Team logos** come from ESPN's logo URL for the team. They are trimmed to their bounding box, fitted in 200 × 200 px, flattened on white and reduced to 8 grays.
- **Channel icons** come from the source the channel map names:
  - Simple Icons (a pinned version on jsdelivr) for the marks it has: FOX, NBC, CBS, Prime Video, Apple TV and a few more. The marks are CC0, but the trademarks still apply.
  - Otherwise the tv-logo/tv-logos collection on GitHub.

  X icons are fitted in 240 × 96 px and reduced to 8 grays. White artwork made for dark backgrounds is drawn as a black silhouette.
- **OG images are made as true 1-bit images** at their exact device pixel size, so the device has no gray to dither. Each image is autocontrasted, scaled to 4× and then box-filtered down, and thresholded.
  - Channel icons: 20 px tall in rows and 30 px in the big view. Simple Icons are used where they exist, because they stay cleanest at 1-bit.
  - Team logos: 32 px in rows and 64 px in the big view. The threshold is chosen per logo. A logo whose 1-bit version comes out mostly solid black, or that is built from mid-tones, gets no 1-bit version, and the device dithers the gray logo instead.
  - A small committed override list, keyed by team or channel, fixes the threshold of a logo or icon that still looks wrong, or forces it to fall back.
- Every image is embedded as a `data:` URI ([ADR-0002](../adr/0002-posters-inlined-as-data-uris.md)), in shared tables keyed by team or channel and not repeated per game (see the payload contract).
- A logo or icon that can't be fetched or converted falls back to the team's abbreviation or the channel's name, and the failure is logged. It never marks the screen stale and is not recorded as an unknown channel.

### Sections and visibility (template)
- Today: games starting on the render's local date, plus any game still live that started the day before. Tomorrow: games starting on the next local date.
- **Final** games stay in Today with their score until midnight. Postponed games stay in their section marked postponed, with no channels.
- Rows are sorted by start time. An empty section is hidden.
- The screen sets `TRMNL_SKIP_DISPLAY` when both sections are empty, unless the error banner has been up for 24 hours or more, so a broken collector is never mistaken for a day without games. The `half_vertical` layout (later) must not set it, as on the Calendar screen.
- A live game's status text is only shown while `updated_at` is under 20 minutes old; after that the row shows plain "Live".

### Featured games (collector)
The collector sets `featured` on the games that the Spotlight layout shows in the big view:
- Only when there are 4 or fewer games in total; with 5 or more, nothing is featured.
- With 1–2 games today, every game today is featured.
- With 3–4 games today, the live games are featured. If none are live, every scheduled game sharing the next start time is featured.
- At most two games are featured.
- Tomorrow's games are never featured, even when they are the only games.

The flag is set at push time, but the sections are grouped at render time, so the flag can be up to one collector interval out of date around midnight. That's acceptable, because the template still lays out every game; a game just shows as a row instead of big until the next push.

### Failure behaviour
- An ESPN failure for a league reuses that league's last good games, marks them **stale**, and adds an error banner entry `{source, since}`, as on the Media screen.
- The payload always includes `updated_at`.

### Schedule
- The collector runs every 60 minutes, and every 5 minutes while any followed game is live or starts within the next 5 minutes. This needs a runner change: a screen can ask for its next run sooner than its interval.
- Display time per screen comes from the LaraPaper playlist's refresh time, which is configured in LaraPaper and out of scope. A 5-minute playlist refresh with three screens brings Game Time back every 15 minutes; the device button forces a refresh.

## Payload contract (Game Time screen)

`fixtures/sample.json` must match it.

```json
{
  "updated_at": "2026-10-23T20:05:00-04:00",
  "games": [
    {
      "league": "nba",
      "start": "2026-10-23T19:00:00-04:00",
      "local_date": "2026-10-23",
      "state": "live",
      "status": "Q3 5:12",
      "followed": { "abbr": "BOS", "name": "Celtics", "logo": "nba-bos", "score": 71, "home": true },
      "opponent": { "abbr": "CHI", "name": "Bulls", "logo": "nba-chi", "score": 66, "home": false },
      "both_followed": false,
      "channels": [
        { "name": "Regional Network", "icon": true },
        { "name": "Streaming Service", "icon": false }
      ],
      "channels_incomplete": false,
      "stale": false,
      "featured": true
    }
  ],
  "logos":   { "nba-bos": "data:image/png;base64,…", "nba-chi": "data:image/png;base64,…" },
  "logos1":  { "nba-bos": "data:image/png;base64,…" },
  "logos1h": { "nba-bos": "data:image/png;base64,…" },
  "icons":   { "Regional Network": "data:image/png;base64,…" },
  "icons1":  { "Regional Network": "data:image/png;base64,…" },
  "icons1h": { "Regional Network": "data:image/png;base64,…" },
  "errors": [{ "source": "espn-nhl", "since": "2026-10-23T18:00:00-04:00" }]
}
```

- `followed` is the followed team. When both teams are followed, `both_followed` is true, `followed` is the home team, and the row reads away "@" home, with the score in the same order. Otherwise `both_followed` is false.
- `score` is null for scheduled and postponed games; `status` is null unless live.
- The template derives "vs" or "@" from `followed.home`.
- Images are kept in shared tables so a team or channel that appears in several games is sent once:
  - A team's `logo` is a key into `logos`, written as `league-abbr` in lower case. It is null when the logo couldn't be fetched.
  - A channel's `icon` says whether `icons` has an entry under its `name`.
  - The tables only hold entries used by `games`.
- `logos` and `icons` are the 8-gray images used on the X.
- `logos1`/`icons1` (row size) and `logos1h`/`icons1h` (big view) hold the OG's 1-bit images. Any of them can be missing for a given key:
  - a missing `logos1` or `logos1h` entry means the OG shows the gray logo and the device dithers it;
  - a missing `icons1` or `icons1h` entry means the OG shows the channel's name.
- `featured` is false unless the featured-games rule picks the game.
- An `errors` entry's `source` is `espn-<league>` for a failing league, or `unknown-team:<league>:<abbr>` for a `GAME_TIME_TEAMS` entry that matches no team. `since` is the first run it failed on, kept until it recovers.
- **Size:** LaraPaper accepts webhooks up to about 5 MB ([ADR-0002](../adr/0002-posters-inlined-as-data-uris.md)), but the trmnlp preview rejects payloads over 100 KB. Fixtures must stay under 100 KB so they can be previewed: a nine-game fixture with 200 px, 8-gray logos is about 92 KB. If fixtures outgrow that, shrink the logos rather than trimming the fixtures.

## Repo structure

```
screens/game-time/
  src/full.liquid, src/settings.yml       trmnlp plugin
  fixtures/sample.json + variants         invented data and invented logos matching the payload contract
  collector/                              collect() -> payload dict
    channels.py                           channel map: normalised name → icon source or text-only (no artwork)
    logos.py                              fetch, convert and cache logos and icons; per-image overrides
    sources/espn.py, nba.py, mlb.py
  tests/
game-time.env.example                     GAME_TIME_TEAMS placeholder
```

### Module seams
- **Source adapters** (`espn`, `nba`, `mlb`) each wrap one source and raise one error type. Only they know URLs and response shapes.
- **Screen collector** picks followed games, classifies and orders channels, merges league sources, sets `featured`, and records unknown channels. Pure logic apart from the adapters, so it is tested with fake adapters.
- **Logo store** (`logos.py`) turns an image URL into the gray and 1-bit `data:` URIs, using a cache in the state directory. Conversion is a pure function of the image bytes, so it is tested on invented images without network access.
- **Runner** gains the "run me sooner" hook; nothing else about it changes.

## Configuration

- `.env`: `GAME_TIME_WEBHOOK_UUID`, plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`.
- `game-time.env`: `GAME_TIME_TEAMS`, kept separate because the list can grow. The deployment's compose file lists it under `env_file:` after `.env`. `game-time.env.example` is committed with placeholder teams.

## Design (template)

Decided in mock-ups, in the screen's private preview gallery.

### General
- The title bar reads "Game Time" with a scoreboard icon drawn in the template (no emoji).
- Minimal: no records, venues, odds or win/loss marks.
- The template includes its own `view view--full` wrapper, as on the Media screen.
- OG text is never smaller than 10 px.

### Layout by game count
The template counts the games in its rendered sections:
- **Spotlight** for 4 or fewer games: featured games in the big view, every other game as a row below.
- **Rows** for 5 or more games: every game is a row.

The rejected alternatives were Columns, Big rows and Split days.

### Big view (Spotlight)
- From top to bottom:
  - the league label, about 26 px;
  - the followed team's logo, "vs" or "@", then the opponent's logo. The "vs" or "@" is set as large as the logos, in regular weight;
  - one line: "8:00 PM on ESPN Peacock", "LIVE Q3 5:12 on Prime Video", "Final" or "Postponed".
- Once a game has started, the score takes the middle spot and "vs" or "@" moves under it.
- Two featured games are stacked with a rule between them.
- The big view shrinks as it shares space with rows (scale `--hk`). The OG uses a smaller big-view scale (`--hu: .58`).
- A team without a logo shows its abbreviation in the logo's place.

### Game rows
- Each **game row**: the league, the followed team (logo and abbreviation), "vs" or "@", the opponent, then the start time, the score with the live status, "Final" or "Postponed", then the channel icons.
- In the Rows layout, rows grow to fill the height: scale `k = 1.25 − 0.1 × (games − 5)`.
- A live row gets a black frame and a larger score.
- Final rows are dimmed on the X. On the OG they drop to regular weight, since 1-bit can't show gray.
- Channels without an icon are shown as their name in a text box.

### Still open in mock-ups
These don't block the issues:
- On text-only OG rows, the league label sits right against the team abbreviation.
- On busy days, the error banner (black, rounded) and the outlined channel-name boxes could become a ruled strip and plain text.
- 1-bit team logos on the OG are proven on a test sheet but not yet drawn in the template.

## Testing

- **Source adapters:** pytest against recorded ESPN scoreboards, an nba.com team page and an MLB Stats API schedule, trimmed to the fields used.
- **Screen collector:** pytest with fake adapters, covering:
  - channel selection: local only, local plus national, national only, streaming only, both teams followed, opponent-only fallback, package-only fallback, radio dropped, ESPN+ treated as a package for the NHL;
  - NBA and MLB overrides, including a failed or unmatched lookup falling back to ESPN with `channels_incomplete`;
  - postponed, cancelled and suspended statuses;
  - an unknown team entry in `GAME_TIME_TEAMS`;
  - the unknown-channel file updating one entry, not appending;
  - the "run sooner" decision near game time and while live;
  - featured games:
    - 1, 2, 3 and 4 games today;
    - 3–4 games today with and without a live game;
    - a tie on the next start time;
    - the two-game cap;
    - tomorrow-only;
    - 5 or more games in total;
  - image tables holding only the keys used by `games`.
- **Logo store:** pytest on invented images, never real logos:
  - the trim, fit and 8-gray output;
  - white-on-transparent art drawn black;
  - 1-bit output at the exact pixel height;
  - a mostly black 1-bit result and a mid-tone logo both falling back to no 1-bit entry;
  - an override;
  - the weekly cache refresh;
  - a failed fetch falling back to text.
- **Template:** checked in `trmnlp serve` on fixture variants:
  - Spotlight with 1, 2, 3 and 4 games;
  - Rows with 5 and 9 games;
  - nothing today with games tomorrow;
  - live games with fresh and old `updated_at`;
  - finals;
  - a game live past midnight;
  - postponed;
  - two followed teams meeting;
  - unknown and text-only channels;
  - many channels;
  - missing logos;
  - a stale league;
  - an error banner up 24 hours.

  Each variant is checked on the X and on the OG at 1-bit and 2-bit.

## Out of scope (v1)

- The `half_vertical` layout (a separate issue).
- Choosing teams in LaraPaper, and publishing as a public plugin.
- Leagues beyond the five, including college sports.
- Regional coverage for NFL afternoon games: the screen trusts ESPN's network per game.
- Alerts beyond the error banner.
- A "+N more" overflow row. Five followed teams give at most ten games in the game window, and Rows fits that. Add one only if the team list grows.

## Open items to verify early

1. Whether every NBA team's nba.com schedule page has the same embedded data as the one checked.
2. Whether the MLB Stats API lists streaming exclusives, or those still come from ESPN.
3. Whether ESPN throttles a client that polls every 5 minutes on busy evenings.
4. ~~Where channel icons can come from for a public repository.~~ Settled: nothing is committed, and the collector fetches the artwork at runtime ([ADR-0009](../adr/0009-logos-fetched-at-runtime.md)).
5. How the template gets the render-time local date in LaraPaper's Liquid renderer (the Calendar screen already does this).
