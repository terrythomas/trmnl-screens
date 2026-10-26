"""Circuit outlines, drawn at runtime from the bacinger/f1-circuits GeoJSON set (ADR-0010).

No outline is ever committed: lines are downloaded, projected to an SVG path, cached in
the state directory and inlined as data: URIs (ADR-0002).
"""

import base64
import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import httpx

log = logging.getLogger(__name__)

BASE = "https://raw.githubusercontent.com/bacinger/f1-circuits/master"
REFRESH = timedelta(days=30)
# The nearest outline counts only within this distance, so a circuit missing from the set
# shows its name rather than a neighbour's track.
MAX_KM = 25
# The longer side of the drawing, and the line width, in SVG units.
SIZE, STROKE = 1000, 12

Fetch = Callable[[str], bytes]


def fetch(url: str) -> bytes:
    response = httpx.get(url, timeout=20, follow_redirects=True)
    response.raise_for_status()
    return response.content


class OutlineStore:
    def __init__(self, cache_dir: Path, fetch: Fetch = fetch):
        self.cache_dir = cache_dir
        self.fetch = fetch
        self._locations: dict[int, list] = {}  # this run's locations file per season

    def outline(self, circuit: str, lat: float, lon: float, year: int, now: datetime | None = None) -> str | None:
        """The circuit's outline as a data: URI, cached for a month; None when there is none."""
        now = now or datetime.now(timezone.utc)
        path = self.cache_dir / f"{re.sub(r'[^a-z0-9_-]+', '-', circuit.lower())}.json"
        try:
            cached = json.loads(path.read_text())
        except (OSError, ValueError):
            cached = None
        if cached and now - datetime.fromisoformat(cached["fetched_at"]) < REFRESH:
            return cached["uri"]
        try:
            uri = self._draw(lat, lon, year)
        except Exception as e:  # any bad download or file: the screen shows the circuit name instead
            # Never log the exception text: httpx messages carry the URL.
            reason = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
            log.warning("outline for %s skipped: %s", circuit, reason)
            return cached["uri"] if cached else None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": now.isoformat(), "uri": uri}))
        return uri

    def _draw(self, lat, lon, year):
        if year not in self._locations:
            self._locations[year] = json.loads(self._locations_file(year))
        nearest = min(self._locations[year], key=lambda loc: _km(lat, lon, loc["lat"], loc["lon"]))
        if _km(lat, lon, nearest["lat"], nearest["lon"]) > MAX_KM:
            raise LookupError("no outline nearby")
        geojson = json.loads(self.fetch(f"{BASE}/circuits/{nearest['id']}.geojson"))
        return svg_uri(geojson["features"][0]["geometry"]["coordinates"])

    def _locations_file(self, year):
        try:
            return self.fetch(f"{BASE}/championships/f1-locations-{year}.json")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            # bacinger publishes a season's file some time after Jolpica lists the season.
            return self.fetch(f"{BASE}/championships/f1-locations-{year - 1}.json")


def _km(lat1, lon1, lat2, lon2):
    # Equirectangular is plenty for telling circuits apart.
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371 * math.hypot(x, math.radians(lat2 - lat1))


def svg_uri(coordinates: list[list[float]]) -> str:
    """A GeoJSON line of [lon, lat] points as a north-up SVG line drawing."""
    mid = math.radians(sum(lat for _, lat in coordinates) / len(coordinates))
    # Scaling longitude by cos(latitude) keeps the track's shape; y grows downwards, so north is up.
    xs = [lon * math.cos(mid) for lon, _ in coordinates]
    ys = [-lat for _, lat in coordinates]
    left, top = min(xs), min(ys)
    scale = (SIZE - 2 * STROKE) / max(max(xs) - left, max(ys) - top)
    pts = [(round((x - left) * scale) + STROKE, round((y - top) * scale) + STROKE) for x, y in zip(xs, ys)]
    width = max(x for x, _ in pts) + STROKE
    height = max(y for _, y in pts) + STROKE
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<path d="{d}" fill="none" stroke="#000" stroke-width="{STROKE}" stroke-linejoin="round" stroke-linecap="round"/>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
