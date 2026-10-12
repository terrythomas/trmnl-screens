# Collectors push to LaraPaper webhooks instead of LaraPaper polling sources

LaraPaper could poll the home services directly, but each screen needs several sources fetched in parallel, image processing, and API keys that we don't want stored in LaraPaper. A collector in this repo pulls every source on a 15-minute schedule and pushes a single payload to the screen's LaraPaper webhook over the local Docker network. LaraPaper's 10-second polling timeout and its role as a pure renderer were the deciding factors.

## Considered Options

- **LaraPaper polls a JSON endpoint served by this repo**: one HTTP round trip per render, bound by the poll timeout, and needs a long-running HTTP server.
- **Render the PNG ourselves and push to an `image_webhook` plugin**: full control over pixels, but it loses the TRMNL framework CSS, trmnlp previews, and portability for anyone reusing the screens.
