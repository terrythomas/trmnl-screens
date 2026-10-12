# LaraPaper deploy path, Liquid renderers and webhook limits

Spike for #3. Tested against LaraPaper 0.44.0 (Docker image) and trmnlp 0.27.0 (Docker image), using a throwaway webhook plugin that was deleted afterwards.

## Summary

- **Deploy:** upload a zip of `src/` to `POST /api/plugin_settings/{id}/archive` with a LaraPaper API token. `trmnlp push` uses the same endpoint and also works, but it rewrites `src/settings.yml`.
- **Renderer:** use the default PHP renderer. `trmnl-liquid` refuses payloads over 128 KB, so it can't handle inline posters.
- **Webhook:** `POST /api/custom_plugins/{uuid}` replaces the stored data. A 1.27 MB payload with inline PNGs was accepted and rendered to a device image.
- **Deploying wipes the plugin's webhook data.** Push fresh data right after every deploy.

## 1. Deploy path

### Authentication

LaraPaper uses Laravel Sanctum. Create a token under **Settings → API Tokens** with type "API", then send it as `Authorization: Bearer <token>`. Tokens have the form `<id>|<secret>`. Quote the value in `.env`, because an unquoted `|` breaks shell sourcing.

### Plugin identity: two different IDs

| ID | What it is | Where it comes from |
|---|---|---|
| Plugin settings ID (`trmnlp_id`) | Identifies the plugin for the archive API | Returned by `POST /api/plugin_settings`, or listed by `GET /api/plugin_settings` |
| Webhook UUID | The `{uuid}` in `/api/custom_plugins/{uuid}` | Shown only in the web UI, on the plugin's page under the webhook URL. No API returns it. |

These are different values. Sending data to the webhook with the plugin settings ID returns 404. Both are UUIDs, so the repo's gitleaks UUID rule keeps them out of tracked files. Keep both in `.env`.

### Option A: archive API directly (tested, works)

```sh
# One time: create an empty plugin and note the returned data.id
curl -X POST -H "Authorization: Bearer $LARAPAPER_API_TOKEN" -H "Accept: application/json" \
  "$LARAPAPER_URL/api/plugin_settings"

# Every deploy: zip the files in src/ (no folder prefix) and upload
curl -H "Authorization: Bearer $LARAPAPER_API_TOKEN" -H "Accept: application/json" \
  -F "file=@plugin.zip" "$LARAPAPER_URL/api/plugin_settings/$PLUGIN_ID/archive"
```

- The upload updates the plugin in place. Its name, markup and settings changed, and the webhook UUID stayed the same across three deploys.
- `strategy: webhook` in `settings.yml` sets the plugin's data strategy.
- `preferred_renderer` in `settings.yml` is **not** imported. The plugin kept the default renderer. Set it in the UI if it's ever needed.
- The response echoes `settings.yml` with an `id:` line added. Ignore it.

### Option B: `trmnlp push` (tested, works)

```sh
trmnlp login --server "$LARAPAPER_URL"   # prompts for the API token; or set TRMNL_API_KEY
trmnlp push                              # first push creates the plugin
trmnlp push --id "$PLUGIN_ID" --force    # later pushes, no prompts
```

After each push, trmnlp writes the server's `id:` into `src/settings.yml`. In this repo the gitleaks UUID rule would block committing that file, so a wrapper has to strip the line every time. trmnlp also needs Docker or Ruby.

### Option C: zip upload in the web UI

Not tested, because Options A and B both work. It stays the manual fallback.

### Recommendation for `scripts/deploy`

Use **Option A**. It needs only an HTTP client and the token, it doesn't touch tracked files, and it's the same request `trmnlp push` makes. Suggested flow:

1. If the screen's plugin settings ID isn't in `.env`, create the plugin, print the ID, and ask the user to add it to `.env`.
2. Zip `screens/<name>/src/*` and upload it to the archive endpoint.
3. Run the collector once for that screen, to replace the data the upload wiped (see below).

The webhook UUID still has to be copied from the plugin's page in the UI once, after the first deploy.

## 2. Liquid renderers

Both renderers ship in the LaraPaper image. `trmnl-liquid` is enabled with `TRMNL_LIQUID_ENABLED=1`.

| Check | PHP renderer (default) | `trmnl-liquid` |
|---|---|---|
| `date: "%H:%M"` on an ISO string with offset | ✅ formats the time as given | ✅ same |
| `date: "%-I:%M %p", "<IANA zone>"` | ⚠️ zone argument ignored | ❌ Liquid error (wrong number of arguments) |
| `in_time_zone: "<IANA zone>"` | ⚠️ no conversion | ⚠️ no conversion |
| `size` on arrays, strings and absent keys | ✅ (absent → 0) | ✅ |
| `slice: 0, 4` | ✅ | ✅ |
| `for … limit: 2` | ✅ | ✅ |
| `default` | ✅ | ✅ |
| `where: "key", true` | ✅ | ✅ |
| 1.27 MB payload | ✅ | ❌ "Context too large": the payload is passed as a command-line argument, capped at 128 KB |

Consequences:

- Use the default PHP renderer. Inline posters (ADR-0002) rule out `trmnl-liquid`.
- Don't convert timezones in the template. The collector sends ISO timestamps that are already in local time (`TZ`), and the template only formats them with `date`.
- `size` on an absent key returns 0, so `{% if section.items.size > 0 %}` handles absent and empty sections the same way.

## 3. Webhook

- `POST /api/custom_plugins/{uuid}` with `{"merge_variables": {...}}` **replaces** the stored data. After two pushes, keys that were only in the first one were gone, including nested keys. Merging happens only when `merge_strategy` is `deep_merge` or `stream`.
- A body without `merge_variables` returns 400. The endpoint needs no auth beyond the UUID.
- The size limit is LaraPaper's Livewire payload cap, about 5 MB minus headroom. Larger payloads return 413.
- A 1.27 MB payload with eight inline PNG `data:` URIs was accepted. It rendered to HTML with the `<img>` intact, then to a 1872×1404 4-bit device image with the poster visible, in about 10 seconds.
- **An archive upload clears the stored webhook data.** Until the next push, the template renders with an empty payload.

## Not covered

- How a page scales for a real TRMNL X. The image test called LaraPaper's image generator without a device, so the page filled only the default 800×480 area. The tracer bullet (#4) checks this on hardware.
- `GET /api/companion/plugin_settings` plus `POST /api/companion/plugin_settings/{id}/data` is an authenticated alternative to the webhook. It wasn't tested, and it would need the full-access API token in the collector, while the webhook only needs a UUID scoped to one plugin.
