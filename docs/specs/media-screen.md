# Spec: Media screen (v1) and repo foundation

Status: ready for tickets
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

A household running Plex, Sonarr and Radarr has no ambient, at-a-glance view of what to watch next. The useful signals are scattered across three apps: titles that were started and then stalled, episodes of monitored series that have just aired or are about to, and tracked movies releasing today. This project puts those signals on a TRMNL e-ink display served by a self-hosted LaraPaper instance on the local network. The repository is public and is intended to grow into a collection of screens, so it needs a reusable structure and a strict secrets posture from the first commit.

## Solution

A public monorepo with one folder per **Screen**. Each screen has a trmnlp-format Liquid template and a **Collector** module. A shared Python runner calls every screen's collector every 15 minutes and pushes the result to that screen's LaraPaper webhook ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). The runner ships as a Docker image on GHCR.

The first screen is the **Media screen**, with three **Sections**:

1. **Continue Watching**: from the configured Plex server, grouped by **item state** (New, In progress, Next) with **neglect order** inside each group ([ADR-0004](../adr/0004-continue-watching-neglect-order.md)), with grayscale posters inlined in the payload ([ADR-0002](../adr/0002-posters-inlined-as-data-uris.md)).
2. **Airing**: monitored Sonarr episodes within the **airing window** (now ±12 h).
3. **Releasing Today**: Radarr movies with a theatrical release today (always shown) or a digital release today (only if not grabbed).

The primary **Device** is the TRMNL X. The OG renders the same template without posters ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)).

## Behaviour

### Continue Watching
- Source: `GET /hubs/continueWatching/items` on the configured server, using the configured account's token.
- Each item gets an item state:
  - **In progress** when `viewOffset` is present.
  - Otherwise **New** for a movie, an episode of a show with no watched episodes, or episode 1 of a season when the show's own `lastViewedAt` is at least `NEW_AFTER_DAYS` (default 30) days ago.
  - Otherwise **Next**. Binge-watching straight from one season into the next stays Next.
  - The show's history comes from one extra lookup per show (`/library/metadata/{grandparentRatingKey}`). A show counts as never watched when it has no `lastViewedAt`. Plex's `viewedLeafCount` only counts episodes still in the library, so it reads 0 for a long-watched show whose watched episodes were deleted.
- Sort by item state (New, In progress, Next), then ascending by `lastViewedAt` within each state. Items with no `lastViewedAt` sort first within their state, since they have never been touched.
- Item fields: kind (episode/movie), item state, show or movie title, season/episode number and episode title for episodes, runtime in minutes (`duration`), and for In progress items the percentage watched and minutes left (from `viewOffset`), last-watched date, poster.
- Poster: the show poster (`grandparentThumb`) for episodes and `thumb` for movies, fetched through Plex's `/photo/:/transcode` with `saturation=0`. All posters are the same size. Encoded as a `data:` URI.
- The collector sends at most N items (configurable, default 12) plus the total count. The template shows up to six as posters, lists the rest as text, and renders "and N more" for anything not sent.

### Airing
- Source: Sonarr `GET /api/v3/calendar` with `start=now-12h`, `end=now+12h`, `includeSeries=true`, filtered to monitored series and monitored episodes.
- Item fields: series title, SxxEyy, episode title, air time as an absolute local time, past or upcoming, grabbed (`hasFile`), runtime in minutes, milestone, series poster (Sonarr's public poster URL, made grayscale by the same Plex transcoder as Continue Watching).
- Several episodes of the same series and season airing at the same time (a whole season dropping at once) collapse into one row with an episode range, e.g. S1E1–10. The row has no episode title, uses the first episode's runtime, and counts as grabbed only when every episode in it is.
- **Milestone**: `entire_season` for a collapsed row that starts at episode 1 and contains a finale. Otherwise `series_finale`, `season_finale` or `midseason_finale` from Sonarr's `finaleType` of any episode in the row; otherwise `series_premiere` for a row starting at S1E1 and `season_premiere` for a row starting at any other episode 1; otherwise none.
- The template shows "airs 9:00 PM" for upcoming episodes and "aired 3h ago" for aired ones.
- Sorted by air time ascending.

### Releasing Today
- Source: Radarr `GET /api/v3/calendar` for the local calendar day (timezone from `TZ`). Only monitored movies count.
- Radarr stores release dates as midnight UTC, so they are read as plain calendar dates, never converted to local time (which would move them to the evening before).
- Include a movie if `inCinemas` is today. Also include it if `digitalRelease` is today and `hasFile` is false. Ignore `physicalRelease`.
- Item fields: title, year, release kind (`theatrical` | `digital`), grabbed, runtime in minutes, poster (Radarr's public poster URL, made grayscale by Plex's transcoder like Airing's).
- A movie that qualifies both ways appears once, as theatrical. Theatrical releases come first, then digital, each by title.

### Empty and failure behaviour
- A Section with zero items is left out of the payload, and the template removes it so the remaining sections reflow.
- If every section is empty, the template renders a single designed fallback state.
- When a **Source** fails (timeout, non-2xx, parse error), the runner reuses that section's last good data and marks it **stale**. It also adds an **Error banner** entry `{source, since}` to the payload. No other alerting channel exists.
- Last good data persists in a small local state file (a volume in Docker), so a container restart doesn't wipe it.
- `since` is the time of the first consecutive failure; it resets when the source recovers. A section that became empty is not brought back by a later failure.
- Posters come from Plex for every section. When Plex can't make one, the row is shown without a poster; Airing and Releasing Today don't go stale for it.
- The payload always includes `updated_at`, which the template shows as the "updated HH:MM" footer.
- A failed webhook push is logged and retried on the next tick. Nothing is surfaced on screen, because the screen can't be reached in that case anyway.

### Schedule
- The runner ticks every 15 minutes (configurable) and immediately on startup.
- Device refresh rate and playlist rotation are configured in LaraPaper and are out of scope.

## Payload contract (Media screen)

The single interface between the collector and the template. `fixtures/sample.json` must match it.

```json
{
  "updated_at": "2026-10-12T14:30:00-04:00",
  "errors": [{ "source": "sonarr", "since": "2026-10-12T13:45:00-04:00" }],
  "continue_watching": {
    "stale": false,
    "total": 14,
    "items": [{
      "kind": "episode",
      "state": "in_progress",
      "title": "Example Show",
      "episode": { "season": 4, "number": 1, "title": "…" },
      "duration_min": 52,
      "progress": 42,
      "remaining_min": 30,
      "last_viewed": "2026-06-29",
      "poster": "data:image/jpeg;base64,…"
    }]
  },
  "airing": {
    "stale": true,
    "items": [{
      "series": "…", "season": 1, "number": 1, "number_end": 10, "title": "…",
      "air_time": "2026-10-12T21:00:00-04:00", "aired": false, "grabbed": false,
      "runtime_min": 44, "milestone": "series_premiere", "poster": "data:…"
    }]
  },
  "releasing_today": {
    "stale": false,
    "items": [{ "title": "…", "year": 2026, "kind": "theatrical", "grabbed": false, "runtime_min": 112, "poster": "data:…" }]
  }
}
```

- `state` is `new`, `in_progress` or `next`. `progress` and `remaining_min` are null unless the state is `in_progress`.
- `number_end` is null unless the row covers several episodes. `runtime_min` is null when Sonarr or Radarr doesn't know it yet, which is common for a new series. `milestone` is null or one of `series_premiere`, `season_premiere`, `midseason_finale`, `season_finale`, `series_finale`, `entire_season`.
- Posters may be JPEG or PNG `data:` URIs.

`errors` is always present, as an empty list when every source is healthy. Sections that are absent mean empty. The template must treat an absent key and an empty `items` list the same way.

## Repo structure

```
screens/media/
  src/full.liquid, src/settings.yml     trmnlp plugin (Liquid, TRMNL framework CSS)
  fixtures/sample.json                  invented data matching the payload contract
  collector/                            Python package: collect() -> payload dict
    sources/plex.py, sonarr.py, radarr.py
  tests/                                pytest with scrubbed recorded responses
collector/                              shared runner: scheduler, webhook push, stale/error state, image utils, config
scripts/deploy                          zip screens/<name>/src and upload to LaraPaper
.env.example, .gitignore, .pre-commit-config.yaml (gitleaks)
Dockerfile, docker-compose.example.yml
.github/workflows/                      build and publish image to GHCR
```

### Module seams
- **Source adapters** (`plex`, `sonarr`, `radarr`) wrap one service each. They return plain domain objects and raise one error type on failure. They are the only modules that know about HTTP or API shapes.
- **Screen collector** (`screens/media/collector`) turns adapter results into the payload: sorting, windowing, the releasing-today rule, poster encoding. It is pure logic apart from the adapters it receives, so it can be tested with fake adapters.
- **Runner** discovers screens and runs each screen's collector per tick. It also owns the stale and error state and pushes to the webhook URL from config. It knows nothing about media.

Adding a screen means a new `screens/<name>/` folder plus one webhook entry in `.env`.

## Configuration (`.env`, never committed)

`PLEX_URL`, `PLEX_TOKEN`, `SONARR_URL`, `SONARR_API_KEY`, `RADARR_URL`, `RADARR_API_KEY`, `LARAPAPER_URL`, `MEDIA_WEBHOOK_UUID`, `LARAPAPER_API_TOKEN` (deploy script only), `TZ`, `INTERVAL_MINUTES`, `NEW_AFTER_DAYS`, `STATE_DIR`.

`.env.example` lists every key with placeholder values. Per [ADR-0003](../adr/0003-public-repo-secrets-policy.md), no IPs, hostnames, tokens or UUIDs appear anywhere in tracked files, including tests, fixtures, docs and commit messages.

## Design (template)

Approved in the layout prototype (#5). Screenshots and the prototype template are on the `prototype/media-layout` branch.

- **Continue Watching:** up to six equal posters in one row. In progress items show a progress bar across the poster with the time left printed on it; New and Next items get a corner tag. Under each poster, the one-line details (TV or film icon, SxEy, runtime) come first so they line up across the row; the title wraps below.
- **Also waiting:** items seven to twelve as text in two left-aligned columns, each with its icon, SxEy and either time left or new/next. Anything the collector did not send is counted as "and N more not shown". When this list shows, shelf posters crop a little shorter.
- **Airing today** and **Releasing today:** side by side below. Each row has a small poster, the title, and details on the right; Airing rows can carry a milestone label. Upcoming episodes show "airs 9:00 PM" and aired ones "aired 3h ago", worked out from `updated_at`. The screen does not mark whether an item is grabbed; `grabbed` stays in the payload for a later feature. Airing shows up to eight rows and Releasing up to three, with "and N more" beside the header past that. Airing switches to two columns past four rows, or past two when Also waiting is showing. Rows share the remaining height and size their poster and text to it (CSS container units), so fewer waiting items means larger rows.
- **Error banner:** one black pill per failing source above everything else, "Sonarr down since 5:45 PM", adding "showing its last data" when that source's section is on screen stale. A stale section's header carries a STALE tag.
- **Section headers:** white text on a black rounded pill with a TV, film or stack-of-cards icon. Icons are inline SVG, never emoji.
- Grayscale e-ink constraints apply: high contrast, no hairlines or gradients, legible from across a room. Posters reduce to 16 flat grays rather than dithering, and stay recognisable at shelf size; below roughly 40 CSS px wide they stop being recognisable.
- **LaraPaper does not wrap the template in `<div class="view view--full">`** (trmnlp and TRMNL's cloud do), so the template must include that wrapper itself for the framework's layout rules to apply.
- **The OG** (800×480, 1–2 bit) drops posters, which turn to mud at that depth, and gets a denser layout from the same template:
  - Continue Watching becomes a list in two columns under its own header: icon, title, SxEy and either time left or new/next. It shows eight items, or twelve when Airing and Releasing are both missing, with "and N more" beside the header.
  - Airing and Releasing keep their rows without posters, one column each. Airing shows four rows, or seven when Continue Watching is missing; Releasing shows three.
  - The switch is the `screen--1bit` / `screen--2bit` class on `.screen`. It is the one device signal that LaraPaper, trmnlp and TRMNL's cloud all set: LaraPaper sets no size class, so the framework's `sm:`/`md:`/`lg:` classes never match there. X-only markup carries `.wtw-x`, OG-only markup `.wtw-og`.

## Testing

- **Source adapters:** pytest against recorded JSON responses that keep the real response shape, with titles and other library details replaced by invented values and every secret, IP and hostname scrubbed.
- **Screen collector:** pytest with fake adapters, covering:
  - neglect-order sort, including items with no `lastViewedAt`;
  - the airing-window boundaries at exactly ±12 h;
  - the releasing-today matrix (theatrical × digital × grabbed);
  - an empty section being left out;
  - a stale section reusing last good data and adding an error entry.
- **Runner:** test that one screen's failure doesn't block another, and that state survives a restart.
- **Template:** checked by eye in `trmnlp serve` using `fixtures/sample.json` plus the fixture variants that `python screens/media/fixtures/variants.py` writes to `fixtures/variants/` (load one with `scripts/preview-data media variants/full.json`): all sections full, each section absent or empty, everything empty, stale sections and error banners, long titles, 1–12 Continue Watching items and a crowded Airing. Titles are invented and posters are abstract stand-ins. Check every variant on the X and on the OG at 1-bit and 2-bit; a change for one device must leave the other's renders byte-identical.
- **Security:** gitleaks runs in pre-commit and in CI.

## Out of scope (v1)

- Mashup and half/quadrant views.
- Push notifications or any alerting beyond the on-screen banner.
- Other Plex users and other Plex servers.
- Device refresh and rotation settings.
- Other screens.

## Open items to verify early

1. Whether LaraPaper's `POST /api/plugin_settings/{id}/archive` (or `trmnlp push` with a custom server) accepts a trmnlp zip end to end. If not, deploy falls back to uploading the zip in the UI, documented in the README.
2. Whether the collector container can reach LaraPaper and every source on the deployment's network, and which Docker networking mode the example compose file should recommend.
3. Whether LaraPaper's Liquid renderer, the default PHP keepsuit one, supports the filters the template needs (`date`, `size`, `slice`). If not, use `preferred_renderer: trmnl-liquid` or move the formatting into the collector.

