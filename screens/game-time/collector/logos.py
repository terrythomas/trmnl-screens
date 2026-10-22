"""Team logos and channel icons, fetched at runtime and converted for each device (ADR-0009).

Nothing here is ever committed as artwork: images are downloaded, converted and cached
in the state directory, and inlined as data: URIs (ADR-0002).
"""

import base64
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, NamedTuple

import cairosvg
import httpx
from PIL import Image, ImageOps, ImageStat

log = logging.getLogger(__name__)

REFRESH = timedelta(days=7)

# X boxes in device pixels, and OG heights (rows, big view) in device pixels.
LOGO_BOX, ICON_BOX = (200, 200), (240, 96)
LOGO_HEIGHTS, ICON_HEIGHTS = (32, 64), (20, 30)

# Channel icons are flat marks, so one threshold suits them all (approved mock-ups).
ICON_THRESHOLD = 150
# A logo falls back to the device's dithering when it is built from mid-tones, or when more
# than BLACK_SHARE of its 1-bit image is black. Built from mid-tones means both: its grays
# don't split cleanly into dark and light (Otsu separability, 1 for two tones, 0.75 for a
# gradient), and they are shaded rather than flat (share of inked pixels in the 8 most
# common grays). Flat logos of three or more tones split poorly but still threshold well.
SEPARABILITY = 0.85
FLATNESS = 0.85
BLACK_SHARE = 0.85

# Keyed by team ("league-abbr") or channel name: a fixed 1-bit threshold, or None to
# force the fallback, for the few images the automatic choice gets wrong.
OVERRIDES: dict[str, int | None] = {}


class Images(NamedTuple):
    gray: str  # X: 8 grays
    onebit: str | None  # OG row height; None lets the device dither the gray image
    onebit_big: str | None  # OG big-view height


Fetch = Callable[[str], bytes]


def fetch(url: str) -> bytes:
    response = httpx.get(url, timeout=20, follow_redirects=True)
    response.raise_for_status()
    return response.content


class LogoStore:
    def __init__(self, cache_dir: Path, fetch: Fetch = fetch, overrides: dict[str, int | None] = OVERRIDES):
        self.cache_dir = cache_dir
        self.fetch = fetch
        self.overrides = overrides

    def logo(self, key: str, url: str, now: datetime | None = None) -> Images | None:
        return self._get("logo", key, url, now)

    def icon(self, key: str, url: str, now: datetime | None = None) -> Images | None:
        return self._get("icon", key, url, now)

    def _get(self, kind: str, key: str, url: str, now: datetime | None) -> Images | None:
        """The cached images while they are under a week old, else fresh ones; None when neither exists."""
        now = now or datetime.now(timezone.utc)
        override = self.overrides.get(key, "auto")
        path = self.cache_dir / f"{kind}-{re.sub(r'[^a-z0-9]+', '-', key.lower())}.json"
        try:
            cached = json.loads(path.read_text())
        except (OSError, ValueError):
            cached = None
        same = cached and cached["url"] == url and cached["override"] == override
        if same and now - datetime.fromisoformat(cached["fetched_at"]) < REFRESH:
            return Images(*cached["images"])
        try:
            images = convert(self.fetch(url), kind, override)
        except Exception as e:  # any bad download or image: the screen shows text instead
            # Never log the exception text: httpx messages carry the URL and its tokens.
            reason = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
            log.warning("%s for %s skipped: %s", kind, key, reason)
            return Images(*cached["images"]) if same else None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        entry = {"url": url, "override": override, "fetched_at": now.isoformat(), "images": images}
        path.write_text(json.dumps(entry))
        return images


def convert(data: bytes, kind: str, override: int | None | str = "auto") -> Images:
    g = _flatten(_open(data))
    box, heights = (LOGO_BOX, LOGO_HEIGHTS) if kind == "logo" else (ICON_BOX, ICON_HEIGHTS)
    gray = _uri(_fit(g, box).quantize(8))
    if override is None:
        return Images(gray, None, None)
    if override == "auto" and kind == "logo" and _otsu(g)[1] < SEPARABILITY and _flatness(g) < FLATNESS:
        return Images(gray, None, None)
    threshold = ICON_THRESHOLD if override == "auto" and kind == "icon" else override
    return Images(gray, *(_onebit(g, h, threshold) for h in heights))


def _open(data: bytes) -> Image.Image:
    if data.lstrip()[:5] in (b"<svg ", b"<?xml"):
        # Well above the largest size used. cairosvg's safe default follows only data: URLs.
        data = cairosvg.svg2png(bytestring=data, output_height=512)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _flatten(im: Image.Image) -> Image.Image:
    """Grayscale on white, trimmed to the artwork, with white-on-transparent art turned black."""
    alpha = im.getchannel("A")
    opaque = alpha.point(lambda v: 255 if v > 128 else 0)
    if alpha.getextrema()[0] < 255 and ImageStat.Stat(im.convert("L"), mask=opaque).mean[0] > 200:
        # White artwork made for dark backgrounds: draw its shape in black instead.
        im = Image.merge("RGBA", (*Image.new("RGB", im.size, 0).split(), alpha))
    bg = Image.new("RGBA", im.size, "white")
    bg.alpha_composite(im)
    g = ImageOps.autocontrast(bg.convert("L"), cutoff=1)
    box = ImageOps.invert(g).getbbox()
    if box is None:
        raise ValueError("blank image")
    return g.crop(box)


def _fit(g: Image.Image, box: tuple[int, int]) -> Image.Image:
    scale = min(box[0] / g.width, box[1] / g.height)
    return g.resize((max(1, round(g.width * scale)), max(1, round(g.height * scale))), Image.LANCZOS)


def _flatness(g: Image.Image) -> float:
    inked = g.histogram()[:250]
    return sum(sorted(inked)[-8:]) / sum(inked) if sum(inked) else 1.0


def _onebit(g: Image.Image, height: int, threshold: int | str) -> str | None:
    """A 1-bit image at exactly `height` device pixels, so the OG has no gray to dither."""
    big = g.resize((max(4, round(g.width * height * 4 / g.height)), height * 4), Image.LANCZOS)
    small = big.resize((big.width // 4, height), Image.BOX)
    auto = threshold == "auto"
    t = _otsu(small)[0] if auto else threshold
    bits = small.point(lambda v: 0 if v < t else 255).convert("1")
    if auto and bits.histogram()[0] > BLACK_SHARE * bits.width * bits.height:
        return None  # mostly solid black: the device's dithering keeps more of it
    return _uri(bits)


def _otsu(g: Image.Image) -> tuple[int, float]:
    """The threshold that best splits the image into dark and light (Otsu's method), and how
    much of the image's variance that split explains."""
    hist = g.histogram()
    total, total_sum = sum(hist), sum(i * n for i, n in enumerate(hist))
    variance = sum(i * i * n for i, n in enumerate(hist)) / total - (total_sum / total) ** 2
    best, best_t, count, dark_sum = -1.0, 128, 0, 0
    for t in range(255):
        count += hist[t]
        dark_sum += t * hist[t]
        light = total - count
        if count and light:
            spread = count * light * (dark_sum / count - (total_sum - dark_sum) / light) ** 2
            if spread > best:
                best, best_t = spread, t + 1
    return best_t, (best / total**2 / variance if variance > 0 else 1.0)


def _uri(im: Image.Image) -> str:
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
