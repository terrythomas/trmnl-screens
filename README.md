# trmnl-screens

Custom e-ink dashboard screens for [TRMNL](https://usetrmnl.com) devices, served by a self-hosted [LaraPaper](https://github.com/usetrmnl/larapaper) instance. Each screen pairs a Liquid template with a Python collector that gathers data from home services and pushes it to a LaraPaper webhook.

The first screen is the **Media screen**: what to keep watching from Plex, what is airing in Sonarr, and which Radarr movies are in theaters or just out on streaming. Theatrical dates for your country come from TMDB's public release pages; no TMDB account is needed. It is laid out for the TRMNL X, and the OG gets a text-only version of the same screen.

## Setup

The collector ships as a Docker image, `ghcr.io/terrythomas/trmnl-screens`. Every 15 minutes it collects each screen's data and pushes it to that screen's LaraPaper plugin. The same image also uploads the screen's template to LaraPaper, so you don't need Python or a clone of this repo.

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

`INTERVAL_MINUTES` (default 15) and `NEW_AFTER_DAYS` (default 30) can stay as they are. In Docker, `STATE_DIR` is set by the compose file, so its value in `.env` is ignored.

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

Every 15 minutes the log shows `screen media: pushed`. The logs never include URLs, tokens or UUIDs.

Each screen is opt-in: the collector runs only the screens that have a `<SCREEN>_WEBHOOK_UUID` in `.env`. At startup it logs every other screen once as `off`, so you can run just the screens you want.

If a source is down, the screen keeps showing that section's last good data, marks it stale, and shows an error banner. That data lives in the `state` volume, so it survives restarts. If you bind-mount a folder there instead, make it writable by user ID 10001: the container does not run as root.

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

To preview templates, use [trmnlp](https://github.com/usetrmnl/trmnlp). `python screens/media/fixtures/variants.py` writes a set of sample payloads, and `scripts/preview-data` loads one of them. See the [spec's testing section](docs/specs/media-screen.md#testing).

## Docs

- [CONTEXT.md](CONTEXT.md): glossary of the project's terms
- [docs/specs/media-screen.md](docs/specs/media-screen.md): Media screen spec
- [docs/adr/](docs/adr/): architecture decisions

## Secrets

The repo is public, so tokens, webhook UUIDs, IPs and hostnames live only in an untracked `.env` ([ADR-0003](docs/adr/0003-public-repo-secrets-policy.md)). The image never contains `.env`, tests, fixtures or recorded responses: `.dockerignore` is an allowlist, and CI runs `scripts/check-image` on every build. When working on the repo, install the gitleaks pre-commit hook:

```sh
pre-commit install
```

## License

See [LICENSE](LICENSE).
