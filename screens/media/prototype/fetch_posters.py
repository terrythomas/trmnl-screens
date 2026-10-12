"""PROTOTYPE: cache grayscale posters from Plex's Continue Watching row, for judging 4-bit dithering.

Cached files are gitignored and never committed (real artwork). Fixtures keep invented titles.
    python screens/media/prototype/fetch_posters.py
"""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parents[2] / ".env")
plex, token = os.environ["PLEX_URL"].rstrip("/"), os.environ["PLEX_TOKEN"]
client = httpx.Client(base_url=plex, headers={"X-Plex-Token": token, "Accept": "application/json"}, timeout=30)

items = client.get("/hubs/continueWatching/items").raise_for_status().json()["MediaContainer"].get("Metadata", [])
out = HERE / "poster-cache"
out.mkdir(exist_ok=True)
n = 0
for item in items[:16]:
    thumb = item.get("grandparentThumb") or item.get("thumb")
    if not thumb:
        continue
    n += 1
    # Two sizes in device pixels (CSS px x 1.8): hero ~340x510 CSS, thumbnail ~130x195 CSS.
    for size, (w, h) in {"hero": (612, 918), "thumb": (234, 351)}.items():
        r = client.get("/photo/:/transcode", params={"url": thumb, "width": w, "height": h, "saturation": 0, "minSize": 1, "upscale": 1, "format": "jpeg", "quality": 80})
        r.raise_for_status()
        (out / f"{n:02d}-{size}.jpg").write_bytes(r.content)
print(f"cached {n} posters from {len(items)} Continue Watching items")
