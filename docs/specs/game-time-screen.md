# Spec: Game Time screen (v1)

Status: ready for mock-ups
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
- Every channel gets an icon from a curated set in `screens/game-time/channels/`, looked up by a normalised name (several source spellings map to one icon). A channel without an icon is shown by name and recorded as an **unknown channel**.

### Unknown channels
- `STATE_DIR/game-time/unknown-channels.json` holds one entry per unknown channel: name, league, first seen, last seen and times seen. Seeing it again updates the entry; nothing is appended. Adding an icon removes the entry on the next run.

### Logos
- Team logos are fetched from ESPN's logo URL, converted to grayscale and embedded as `data:` URIs ([ADR-0002](../adr/0002-posters-inlined-as-data-uris.md)). They are cached in the state directory and refreshed weekly.
- A logo that can't be fetched leaves the row with the team's abbreviation; it never marks the screen stale.

### Sections and visibility (template)
- Today: games starting on the render's local date, plus any game still live that started the day before. Tomorrow: games starting on the next local date.
- **Final** games stay in Today with their score until midnight. Postponed games stay in their section marked postponed, with no channels.
- Rows are sorted by start time. An empty section is hidden.
- The screen sets `TRMNL_SKIP_DISPLAY` when both sections are empty, unless the error banner has been up for 24 hours or more, so a broken collector is never mistaken for a day without games. The `half_vertical` layout (later) must not set it, as on the Calendar screen.
- A live game's status text is only shown while `updated_at` is under 20 minutes old; after that the row shows plain "Live".

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
      "followed": { "abbr": "BOS", "name": "Celtics", "logo": "data:image/png;base64,…", "score": 71, "home": true },
      "opponent": { "abbr": "CHI", "name": "Bulls", "logo": "data:image/png;base64,…", "score": 66, "home": false },
      "channels": [
        { "name": "Regional Network", "icon": "data:image/svg+xml;base64,…" },
        { "name": "Streaming Service", "icon": null }
      ],
      "channels_incomplete": false,
      "stale": false
    }
  ],
  "errors": [{ "source": "espn-nhl", "since": "2026-10-23T18:00:00-04:00" }]
}
```

- `followed` is the followed team. When both teams are followed, `followed` is the home team, and the row reads away "@" home.
- `score` is null for scheduled and postponed games; `status` is null unless live.
- The template derives "vs" or "@" from `followed.home`.

## Repo structure

```
screens/game-time/
  src/full.liquid, src/settings.yml       trmnlp plugin
  channels/                               curated channel icons and the name → icon map
  fixtures/sample.json + variants         invented data matching the payload contract
  collector/                              collect() -> payload dict
    sources/espn.py, nba.py, mlb.py
  tests/
game-time.env.example                     GAME_TIME_TEAMS placeholder
```

### Module seams
- **Source adapters** (`espn`, `nba`, `mlb`) each wrap one source and raise one error type. Only they know URLs and response shapes.
- **Screen collector** picks followed games, classifies and orders channels, merges league sources, and records unknown channels. Pure logic apart from the adapters, so it is tested with fake adapters.
- **Runner** gains the "run me sooner" hook; nothing else about it changes.

## Configuration

- `.env`: `GAME_TIME_WEBHOOK_UUID`, plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`.
- `game-time.env`: `GAME_TIME_TEAMS`, kept separate because the list can grow. The deployment's compose file lists it under `env_file:` after `.env`. `game-time.env.example` is committed with placeholder teams.

## Design (template)

Decided in mock-ups, in the screen's private preview gallery. Settled so far:

- Title "Game Time" with a stylised icon (no emoji), chosen in the mock-ups.
- Each **game row**: followed team (logo and abbreviation), "vs" or "@", opponent, then start time, or score with live status or "Final", or "Postponed", then channel icons.
- Minimal: no records, venues, odds or win/loss marks.
- On the OG, whether team logos and channel icons hold up at 1–2 bit is decided on mock-ups; text abbreviations are the fallback.
- The template includes its own `view view--full` wrapper, as on the Media screen.

## Testing

- **Source adapters:** pytest against recorded ESPN scoreboards, an nba.com team page and an MLB Stats API schedule, trimmed to the fields used.
- **Screen collector:** pytest with fake adapters, covering:
  - channel selection: local only, local plus national, national only, streaming only, both teams followed, opponent-only fallback, package-only fallback, radio dropped, ESPN+ treated as a package for the NHL;
  - NBA and MLB overrides, including a failed or unmatched lookup falling back to ESPN with `channels_incomplete`;
  - postponed, cancelled and suspended statuses;
  - an unknown team entry in `GAME_TIME_TEAMS`;
  - the unknown-channel file updating one entry, not appending;
  - the "run sooner" decision near game time and while live.
- **Template:** checked in `trmnlp serve` on fixture variants: nothing today with games tomorrow, live games with fresh and old `updated_at`, finals, a game live past midnight, postponed, two followed teams meeting, unknown channels, many channels, a stale league and an error banner up 24 hours, on the X and on the OG at 1-bit and 2-bit.

## Out of scope (v1)

- The `half_vertical` layout (a separate issue).
- Choosing teams in LaraPaper, and publishing as a public plugin.
- Leagues beyond the five, including college sports.
- Regional coverage for NFL afternoon games: the screen trusts ESPN's network per game.
- Alerts beyond the error banner.

## Open items to verify early

1. Whether every NBA team's nba.com schedule page has the same embedded data as the one checked.
2. Whether the MLB Stats API lists streaming exclusives, or those still come from ESPN.
3. Whether ESPN throttles a client that polls every 5 minutes on busy evenings.
4. Where channel icons can come from for a public repository, and whether network logos need a licence note.
5. How the template gets the render-time local date in LaraPaper's Liquid renderer (the Calendar screen already does this).
