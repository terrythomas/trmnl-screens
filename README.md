# trmnl-screens

Custom e-ink dashboard screens for [TRMNL](https://usetrmnl.com) devices, served by a self-hosted [LaraPaper](https://github.com/usetrmnl/larapaper) instance. Each screen pairs a Liquid template with a Python collector that gathers data from home services and pushes it to a LaraPaper webhook.

The first screen is the **Media screen**: what to keep watching from Plex, what is airing in Sonarr, and what is releasing today in Radarr. It is laid out for the TRMNL X, and the OG gets a text-only version of the same screen.

## Setup

The collector ships as a Docker image, `ghcr.io/terrythomas/trmnl-screens`. Every 15 minutes it collects each screen's data and pushes it to that screen's LaraPaper plugin. The same image also uploads the screen's template to LaraPaper, so you don't need Python or a clone of this repo.

### 1. Prerequisites

- A running LaraPaper instance with your TRMNL device added to it.
- Plex, Sonarr and Radarr.
- Docker with the Compose plugin, on a machine that can reach LaraPaper, Plex, Sonarr and Radarr over the network.

### 2. Get the files

Create a folder for the collector and download two files into it:

```sh
mkdir trmnl-screens && cd trmnl-screens
curl -fsSL -o docker-compose.yml https://raw.githubusercontent.com/terrythomas/trmnl-screens/main/docker-compose.example.yml
curl -fsSL -o .env https://raw.githubusercontent.com/terrythomas/trmnl-screens/main/.env.example
```

### 3. Fill in `.env`

Open `.env` and replace the placeholder values:

| Key | Value |
|---|---|
| `PLEX_URL`, `PLEX_TOKEN` | Your Plex server's address, including the port, and an [authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/). |
| `SONARR_URL`, `SONARR_API_KEY` | Sonarr's address, and the API key from **Settings → General → Security**. |
| `RADARR_URL`, `RADARR_API_KEY` | Radarr's address, and the API key from the same place in Radarr. |
| `LARAPAPER_URL` | LaraPaper's address. |
| `LARAPAPER_API_TOKEN` | A token from LaraPaper's **Settings → API Tokens**, of type "API". Keep the quotes: tokens contain `\|`. |
| `TZ` | Your time zone, e.g. `America/New_York`. It decides what "today" means. |
| `MEDIA_PLUGIN_ID`, `MEDIA_WEBHOOK_UUID` | Leave these for now. Step 5 fills them in. |

`INTERVAL_MINUTES` (default 15) and `NEW_AFTER_DAYS` (default 30) can stay as they are. In Docker, `STATE_DIR` is set by the compose file, so its value in `.env` is ignored.

### 4. Check the network

Every URL in `.env` is opened from inside the container, so:

- **Services on other machines:** use their LAN address or hostname. The default network reaches them.
- **Services in Docker on the same host:** join their Docker network (uncomment `networks:` in `docker-compose.yml` and set its name), then use container names, e.g. `http://larapaper:8080`.
- **Never use `localhost`:** inside the container it means the container itself. Use the host's LAN address instead, or set `network_mode: host`.

### 5. Create the plugin and deploy the template

```sh
docker compose pull
docker compose run --rm collector python scripts/deploy media
```

The first run creates a plugin in LaraPaper and prints its ID. Then:

1. Add the printed ID to `.env` as `MEDIA_PLUGIN_ID`.
2. In LaraPaper, open the new **What to Watch** plugin. Its page shows a webhook URL that ends in a UUID. Copy that UUID into `.env` as `MEDIA_WEBHOOK_UUID`.
3. Add the plugin to your device's playlist.
4. Run the deploy command again. It uploads the template and pushes the first data, and the screen fills in on the device's next refresh.

### 6. Start the collector

```sh
docker compose up -d
docker compose logs -f
```

Every 15 minutes the log shows `screen media: pushed`. The logs never include URLs, tokens or UUIDs.

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
