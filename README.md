# trmnl-screens

Custom e-ink dashboard screens for [TRMNL](https://usetrmnl.com) devices, served by a self-hosted [LaraPaper](https://github.com/usetrmnl/larapaper) instance. Each screen pairs a Liquid template with a Python collector that gathers data from home services and pushes it to a LaraPaper webhook.

The first screen is the **Media screen**: what to keep watching from Plex, what is airing in Sonarr, and which Radarr movies are in theaters or just out on streaming. Theatrical dates for your country come from TMDB's public release pages; no TMDB account is needed. It is laid out for the TRMNL X, and the OG gets a text-only version of the same screen.

The **Calendar screen** shows the meeting you're in and how long it has left (or how long until the next one), what's next, and the rest of today with free blocks and conflicts marked. An iOS Shortcut pushes the events from the phone's calendar, so it works with calendars no server can reach. It is laid out for the OG; the X gets the same layout with more room, and on a light day gives the whole screen to the current and next meeting. See [Calendar screen](#calendar-screen).

## Setup

The collector ships as a Docker image, `ghcr.io/terrythomas/trmnl-screens`. On each screen's schedule (every 15 minutes for Media) it collects that screen's data and pushes it to that screen's LaraPaper plugin. The same image also uploads the screen's template to LaraPaper, so you don't need Python or a clone of this repo.

### 1. Prerequisites

- Plex, Sonarr and Radarr.
- A TRMNL device (an X, or an OG).
- Docker with the Compose plugin, on a machine that can reach LaraPaper, Plex, Sonarr and Radarr over the network.
- A LaraPaper instance. Step 2 covers setting it up. The screen was built and tested against LaraPaper 0.44.

### 2. Set up LaraPaper

LaraPaper is the self-hosted server your TRMNL device gets its screens from. The collector pushes data to it, and LaraPaper renders the screen.

1. **Install LaraPaper.** Follow [its README](https://github.com/usetrmnl/larapaper). It runs as a Docker container.
2. **Connect your device.** In LaraPaper, open **Devices** and choose the button that permits auto join. Then point the device at LaraPaper's base URL in the device's Wi-Fi setup, as LaraPaper's README describes. The device appears under **Devices** once it checks in.
3. **Create an API token.** Open the user menu, then **API Tokens**. Enter a name, choose the token type **API**, and choose **Create token**. Copy the token now: LaraPaper shows it only once. It goes into `.env` in step 4.
4. **Leave the Liquid renderer on its default.** The alternative `trmnl-liquid` renderer refuses payloads over 128 KB, and this screen's payload holds its posters, so it is larger than that.
5. **Let LaraPaper reach the internet.** It loads the TRMNL framework's CSS from `trmnl.com` each time it renders a screen. If that load fails, the screen renders unstyled until the next refresh.

You don't create the plugin by hand. Step 6 creates it and uploads the template for you.

### 3. Get the files

Create a folder for the collector and download two files into it:

```sh
mkdir trmnl-screens && cd trmnl-screens
curl -fsSL -o docker-compose.yml https://raw.githubusercontent.com/terrythomas/trmnl-screens/main/docker-compose.example.yml
curl -fsSL -o .env https://raw.githubusercontent.com/terrythomas/trmnl-screens/main/.env.example
```

### 4. Fill in `.env`

Open `.env` and replace the placeholder values:

| Key | Value |
|---|---|
| `PLEX_URL`, `PLEX_TOKEN` | Your Plex server's address, including the port, and an [authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/). |
| `SONARR_URL`, `SONARR_API_KEY` | Sonarr's address, and the API key from **Settings → General → Security**. |
| `RADARR_URL`, `RADARR_API_KEY` | Radarr's address, and the API key from the same place in Radarr. |
| `LARAPAPER_URL` | LaraPaper's address. |
| `LARAPAPER_API_TOKEN` | The API token from step 2. Keep the quotes: tokens contain `\|`. |
| `TZ` | Your time zone, e.g. `America/New_York`. It decides what "today" means. |
| `MEDIA_PLUGIN_ID`, `MEDIA_WEBHOOK_UUID` | Leave these for now. Step 6 fills them in. |

`NEW_AFTER_DAYS` (default 30) can stay as it is. Each screen collects on its own default schedule (Media: every 15 minutes); set `<SCREEN>_INTERVAL_MINUTES`, e.g. `MEDIA_INTERVAL_MINUTES=30`, to change one screen, or `INTERVAL_MINUTES` to change every screen. An `INTERVAL_MINUTES` line left over from an older `.env` overrides every screen's default, so delete it unless you want that. In Docker, `STATE_DIR` is set by the compose file, so its value in `.env` is ignored.

`RELEASE_COUNTRY` in `docker-compose.yml` (default `US`) is the two-letter country code whose theatrical dates **In Theaters** uses.

### 5. Check the network

Every URL in `.env` is opened from inside the container, so:

- **Services on other machines:** use their LAN address or hostname. The default network reaches them.
- **Services in Docker on the same host:** join their Docker network (uncomment `networks:` in `docker-compose.yml` and set its name), then use container names, e.g. `http://larapaper:8080`.
- **Never use `localhost`:** inside the container it means the container itself. Use the host's LAN address instead, or set `network_mode: host`.

### 6. Create the plugin and deploy the template

```sh
docker compose pull
docker compose run --rm collector python scripts/deploy media
```

The first run creates a plugin in LaraPaper and prints its ID. Then:

1. Add the printed ID to `.env` as `MEDIA_PLUGIN_ID`.
2. In LaraPaper, open **Plugins** and select the new **What to Watch** plugin. Its data strategy is already set to **Webhook**. The **Webhook URL** on its page ends in a UUID: copy that UUID into `.env` as `MEDIA_WEBHOOK_UUID`. This is a different value from the plugin ID, and sending data with the wrong one fails with HTTP 404.
3. On the same page, choose **Add to Playlist** and add the plugin to your device's playlist. If you have more than one device, do this for each one. The X and the OG use the same plugin, and each gets its own layout.
4. Run the deploy command again. It uploads the template and pushes the first data, and the screen fills in on the device's next refresh.

Each deploy replaces the template and clears the plugin's stored data, so the deploy command always pushes fresh data afterwards. Don't edit the template in LaraPaper's editor: the next deploy overwrites it.

### 7. Start the collector

```sh
docker compose up -d
docker compose logs -f
```

At startup the log shows each screen's schedule, e.g. `screen media: every 15 minutes`, and after each run `screen media: pushed`. The logs never include URLs, tokens or UUIDs.

Each screen is opt-in: the collector runs only the screens that have a `<SCREEN>_WEBHOOK_UUID` in `.env`. At startup it logs every other screen once as `off`, so you can run just the screens you want.

If a source is down, the screen keeps showing that section's last good data, marks it stale, and shows an error banner. That data lives in the `state` volume, so it survives restarts. If you bind-mount a folder there instead, make it writable by user ID 10001: the container does not run as root.

### Calendar screen

The Calendar screen's events come from an iOS Shortcut, not from the collector ([ADR-0007](docs/adr/0007-calendar-screen-fed-by-phone-kept-fresh-by-collector.md)).

1. Deploy it like the Media screen: `scripts/deploy calendar`, then add `CALENDAR_PLUGIN_ID` and `CALENDAR_WEBHOOK_UUID` to `.env`, add the plugin to the device's playlist, and deploy again.
2. Sign `screens/calendar/shortcut/Calendar Sync.shortcut` on a Mac, AirDrop it to the phone and run it once: it asks for the webhook and which calendars to show. Then add its automations. See [docs/calendar-sync.md](docs/calendar-sync.md). The phone must be able to reach LaraPaper.
3. Set the workday in the plugin's settings in LaraPaper (default 9:00 to 17:00). Free blocks are only shown inside it.

With `CALENDAR_WEBHOOK_UUID` set, the collector refreshes the screen every 15 minutes without touching the events, so Now and Next stay current between syncs. A deploy clears the stored events, so run the Shortcut once afterwards.

The Calendar screen also has a `half_vertical` layout for LaraPaper mashups: just the agenda, with Now and Next marked. The Media screen is full-screen only.

### Updating

```sh
docker compose pull && docker compose up -d
docker compose run --rm collector python scripts/deploy media
```

Deploy again after every update, in case the template changed. `latest` follows the main branch. Releases are also tagged by version (e.g. `:0.1`) for pinning.

## Development

Python 3.12 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra dev
uv run pytest
uv run python -m collector --once   # one tick against the services in .env
uv run scripts/deploy media         # deploy the template from your clone
docker build -t trmnl-screens:dev . && scripts/check-image trmnl-screens:dev
```

### Adding a screen

A screen is a folder under `screens/` with a `collector` package whose `__init__.py` defines `collect()`, which returns the payload for the screen's LaraPaper webhook. It can also set `INTERVAL_MINUTES`, its default schedule. The collector finds screens by folder name and imports only the enabled ones, so a screen that isn't enabled never loads.

If a screen needs Python packages that the others don't, list them in `pyproject.toml` as an optional extra named after the screen, then run `uv lock`:

```toml
[project.optional-dependencies]
weather = ["some-package>=1.0"]
```

Running from source, install it with `uv sync --extra weather`. The Docker image installs every screen's extra.

To preview templates, use [trmnlp](https://github.com/usetrmnl/trmnlp). `python screens/media/fixtures/variants.py` writes a set of sample payloads, and `scripts/preview-data` loads one of them. See the [spec's testing section](docs/specs/media-screen.md#testing).

## Docs

- [CONTEXT.md](CONTEXT.md): glossary of the project's terms
- [docs/specs/media-screen.md](docs/specs/media-screen.md): Media screen spec
- [docs/calendar-sync.md](docs/calendar-sync.md): Calendar screen payload and Shortcut
- [docs/adr/](docs/adr/): architecture decisions

## Secrets

The repo is public, so tokens, webhook UUIDs, IPs and hostnames live only in an untracked `.env` ([ADR-0003](docs/adr/0003-public-repo-secrets-policy.md)). The image never contains `.env`, tests, fixtures or recorded responses: `.dockerignore` is an allowlist, and CI runs `scripts/check-image` on every build. When working on the repo, install the gitleaks pre-commit hook:

```sh
pre-commit install
```

## License

See [LICENSE](LICENSE).
