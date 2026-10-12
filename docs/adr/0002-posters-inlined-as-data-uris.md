# Posters are inlined in the webhook payload as base64 data URIs

LaraPaper's headless browser has to load poster images from somewhere. Plex image URLs carry the Plex token, which would then live in LaraPaper's stored data and logs, and serving images from the collector would mean another exposed port. Instead the collector fetches posters already resized and desaturated by Plex's transcoder and embeds them in the payload. A handful of posters is far below LaraPaper's roughly 5 MB webhook limit. If a future screen needs many large images, revisit this.
