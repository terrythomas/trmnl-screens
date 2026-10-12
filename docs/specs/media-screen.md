# Spec: Media screen (v1) and repo foundation

Status: ready for tickets
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

A household running Plex, Sonarr and Radarr has no ambient, at-a-glance view of what to watch next. The useful signals are scattered across three apps: titles that were started and then stalled, episodes of monitored series that have just aired or are about to, and tracked movies releasing today. This project puts those signals on a TRMNL e-ink display served by a self-hosted LaraPaper instance on the local network. The repository is public and is intended to grow into a collection of screens, so it needs a reusable structure and a strict secrets posture from the first commit.

## Solution

A public monorepo with one folder per **Screen**. Each screen has a trmnlp-format Liquid template and a **Collector** module. A shared Python runner calls every screen's collector every 15 minutes and pushes the result to that screen's LaraPaper webhook ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). The runner ships as a Docker image on GHCR.

The first screen is the **Media screen**, with three **Sections**:

1. **Continue Watching**: from the configured Plex server, grouped by **item state** (New, In progress, Next) with **neglect order** inside each group ([ADR-0004](../adr/0004-continue-watching-neglect-order.md)), with grayscale posters inlined in the payload ([ADR-0002](../adr/0002-posters-inlined-as-data-uris.md)).
2. **Airing**: monitored Sonarr episodes within the **airing window** (now ±12 h), each marked **grabbed** or not.
3. **Releasing Today**: Radarr movies with a theatrical release today (always shown) or a digital release today (only if not grabbed).

The primary **Device** is the TRMNL X. The OG renders the same template without posters ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)).

## Behaviour

### Continue Watching
- Source: `GET /hubs/continueWatching/items` on the configured server, using the configured account's token.
- Each item gets an item state: **In progress** when `viewOffset` is present; otherwise **New** for episode 1 of a season, a show with no watched episodes, or a movie; otherwise **Next**.
- Sort by item state (New, In progress, Next), then ascending by `lastViewedAt` within each state. Items with no `lastViewedAt` sort first within their state, since they have never been touched.
- Item fields: kind (episode/movie), show or movie title, season/episode number and episode title for episodes, in-progress percentage when `viewOffset` is present, last-watched date, poster.
- Poster: the show poster (`grandparentThumb`) for episodes and `thumb` for movies, fetched through Plex's `/photo/:/transcode` with `saturation=0`. All posters are the same size. Encoded as a `data:` URI.
- The collector sends at most N items (configurable, default 12) plus the total count. The template shows up to six as posters, lists the rest as text, and renders "and N more" for anything not sent.

### Airing
- Source: Sonarr `GET /api/v3/calendar` with `start=now-12h`, `end=now+12h`, `includeSeries=true`, filtered to monitored series and monitored episodes.
- Item fields: series title, SxxEyy, episode title, air time as an absolute local time, past or upcoming, grabbed (`hasFile`).
- The template shows "aired 3h ago" or "airs 9:00 PM", with filled or hollow markers for grabbed.
- Sorted by air time ascending.

### Releasing Today
- Source: Radarr `GET /api/v3/calendar` for the local calendar day (timezone from `TZ`).
- Include a movie if `inCinemas` is today. Also include it if `digitalRelease` is today and `hasFile` is false. Ignore `physicalRelease`.
- Item fields: title, year, release kind (`theatrical` | `digital`), grabbed, optional poster (from Radarr's images, run through the same grayscale pipeline).
- A movie that qualifies both ways appears once, as theatrical.

### Empty and failure behaviour
- A Section with zero items is left out of the payload, and the template removes it so the remaining sections reflow.
- If every section is empty, the template renders a single designed fallback state.
- When a **Source** fails (timeout, non-2xx, parse error), the runner reuses that section's last good data and marks it **stale**. It also adds an **Error banner** entry `{source, since}` to the payload. No other alerting channel exists.
- Last good data persists in a small local state file (a volume in Docker), so a container restart doesn't wipe it.
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
      "title": "Example Show",
      "episode": { "season": 4, "number": 1, "title": "…" },
      "progress": null,
      "last_viewed": "2026-06-29",
      "poster": "data:image/png;base64,…"
    }]
  },
  "airing": {
    "stale": true,
    "items": [{
      "series": "…", "season": 2, "number": 7, "title": "…",
      "air_time": "2026-10-12T21:00:00-04:00", "aired": false, "grabbed": false
    }]
  },
  "releasing_today": {
    "stale": false,
    "items": [{ "title": "…", "year": 2026, "kind": "theatrical", "grabbed": false, "poster": "data:…" }]
  }
}
```

Sections that are absent mean empty. The template must treat an absent key and an empty `items` list the same way.

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

`PLEX_URL`, `PLEX_TOKEN`, `SONARR_URL`, `SONARR_API_KEY`, `RADARR_URL`, `RADARR_API_KEY`, `LARAPAPER_URL`, `MEDIA_WEBHOOK_UUID`, `LARAPAPER_API_TOKEN` (deploy script only), `TZ`, `INTERVAL_MINUTES`.

`.env.example` lists every key with placeholder values. Per [ADR-0003](../adr/0003-public-repo-secrets-policy.md), no IPs, hostnames, tokens or UUIDs appear anywhere in tracked files, including tests, fixtures, docs and commit messages.

## Design (template)

- **Hybrid poster and type layout** on the X (1040×780 CSS px, 4-bit), with Continue Watching first.
- Grayscale e-ink constraints apply: high contrast, no thin hairlines or gradients, and legible from across a room.
- The OG (800×480, 1–2 bit) hides posters through the framework's `md:` and bit-depth classes and becomes a dense typographic list.
- The layout gets decided in a prototype first. Template tickets depend on it.

## Testing

- **Source adapters:** pytest against recorded JSON responses with real titles kept but every secret, IP and hostname scrubbed.
- **Screen collector:** pytest with fake adapters, covering:
  - neglect-order sort, including items with no `lastViewedAt`;
  - the airing-window boundaries at exactly ±12 h;
  - the releasing-today matrix (theatrical × digital × grabbed);
  - an empty section being left out;
  - a stale section reusing last good data and adding an error entry.
- **Runner:** test that one screen's failure doesn't block another, and that state survives a restart.
- **Template:** checked by eye in `trmnlp serve` using `fixtures/sample.json` plus fixture variants: all sections full, each section empty, everything empty, an error banner, a long title. Check at both X and OG sizes.
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

