"""Fills the Game Time fixtures' logo and icon tables with invented images, run through the real logo store.

    uv run python screens/game-time/fixtures/images.py

No real logo or icon is used (ADR-0009): team logos are badges with the team's invented abbreviation,
channel icons are the invented channel's name set in type. Some are left out on purpose, so every
fixture also shows the fallbacks.
"""

import importlib
import io
import json
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from collector.discovery import discover_screens

discover_screens()
convert = importlib.import_module("trmnl_screens.game-time.collector.logos").convert

HERE = Path(__file__).parent
NO_LOGO = {"QRY", "ORC", "CPT"}  # the logo couldn't be fetched: the abbreviation stands alone
SHADED = {"LKS"}  # built from mid-tones: no 1-bit logo, so the OG dithers the gray one
TEXT_ONLY = {"StreamCo", "Lakeside Community Access", "Valley Public Sports"}  # no icon source in the channel map
NO_ONEBIT_ICON = {"Sportsline Plus"}  # forced to fall back: the OG shows its name


def _png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def badge(abbr: str) -> bytes:
    """A two-tone badge, its shape picked from the abbreviation, with the abbreviation on it."""
    n = zlib.crc32(abbr.encode())
    im = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    dark = (20 + n % 60, 30, 90 + n % 100, 255)
    shapes = [
        lambda: d.ellipse((10, 10, 290, 290), fill=dark),
        lambda: d.polygon([(30, 10), (270, 10), (270, 170), (150, 290), (30, 170)], fill=dark),
        lambda: d.polygon([(150, 5), (295, 150), (150, 295), (5, 150)], fill=dark),
        lambda: d.rounded_rectangle((10, 40, 290, 260), radius=40, fill=dark),
    ]
    shapes[n % len(shapes)]()
    d.text((150, 150), abbr, font=ImageFont.load_default(size=80), anchor="mm", fill="white")
    if abbr in SHADED:
        shade = Image.linear_gradient("L").resize(im.size)
        im = Image.merge("RGBA", (shade, shade, shade, im.getchannel("A")))
    return _png(im)


def wordmark(name: str) -> bytes:
    """A round mark and the channel's name in heavy type on transparency, like a flat channel mark."""
    font = ImageFont.load_default(size=72)
    box = font.getbbox(name, stroke_width=3)
    h = box[3] + 20
    im = Image.new("RGBA", (h + box[2] + 20, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 6, h - 6, h - 6), fill=(200, 20, 40, 255))
    d.text((h + 10, 10), name, font=font, fill=(200, 20, 40, 255), stroke_width=3, stroke_fill=(200, 20, 40, 255))
    return _png(im)


def fill(payload: dict) -> dict:
    tables = {name: {} for name in ("logos", "logos1", "logos1h", "icons", "icons1", "icons1h")}

    def add(names, key, images):
        for name, uri in zip(names, images):
            if uri:
                tables[name][key] = uri

    for g in payload["games"]:
        for t in (g["followed"], g["opponent"]):
            key = f"{g['league']}-{t['abbr'].lower()}"
            t["logo"] = None if t["abbr"] in NO_LOGO else key
            if t["logo"]:
                add(("logos", "logos1", "logos1h"), key, convert(badge(t["abbr"]), "logo"))
        for c in g["channels"]:
            c["icon"] = c["name"] not in TEXT_ONLY
            if c["icon"]:
                override = None if c["name"] in NO_ONEBIT_ICON else "auto"
                add(("icons", "icons1", "icons1h"), c["name"], convert(wordmark(c["name"]), "icon", override))
    # The tables go just before errors, as in the payload contract.
    rest = {k: v for k, v in payload.items() if k not in tables and k != "errors"}
    return rest | tables | {"errors": payload["errors"]}


if __name__ == "__main__":
    for path in sorted(HERE.glob("*.json")):
        payload = fill(json.loads(path.read_text()))
        path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"{path.name}: {len(json.dumps(payload)) // 1024} KB")
