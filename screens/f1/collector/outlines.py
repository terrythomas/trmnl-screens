"""Circuit outlines, drawn at runtime from the bacinger/f1-circuits GeoJSON set (ADR-0010).

No outline is ever committed: lines are downloaded, cached in the state directory and laid out
for the Poster (fit.py), so the payload carries each as an SVG path the template draws inline.
"""

import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import httpx

from . import fit

log = logging.getLogger(__name__)

BASE = "https://raw.githubusercontent.com/bacinger/f1-circuits/master"
REFRESH = timedelta(days=30)
# The nearest outline counts only within this distance, so a circuit missing from the set
# shows its name rather than a neighbour's track.
MAX_KM = 25
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

    def outline(self, circuit: str, lat: float, lon: float, year: int, name: str, location: str,
                now: datetime | None = None) -> dict | None:
        """The circuit's outline laid out for this Grand Prix (fit.layout); None when there is none.
        The line is cached for a month; the layout is kept with it until the name or the layout changes."""
        now = now or datetime.now(timezone.utc)
        path = self.cache_dir / f"{re.sub(r'[^a-z0-9_-]+', '-', circuit.lower())}.json"
        try:
            cached = json.loads(path.read_text())
            cached["coordinates"]  # a cache from before layouts holds no line
        except (OSError, ValueError, KeyError, TypeError):
            cached = None
        key = f"{fit.LAYOUT}|{name}|{location}"
        if cached and now - datetime.fromisoformat(cached["fetched_at"]) < REFRESH:
            line, fetched_at = cached["coordinates"], cached["fetched_at"]
        else:
            try:
                line, fetched_at = self._line(lat, lon, year), now.isoformat()
            except Exception as e:  # any bad download or file: the screen shows the circuit name instead
                # Never log the exception text: httpx messages carry the URL.
                reason = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
                log.warning("outline for %s skipped: %s", circuit, reason)
                if not cached:
                    return None
                line, fetched_at = cached["coordinates"], cached["fetched_at"]
        if cached and cached.get("key") == key and cached["coordinates"] == line:
            return cached["outline"]
        try:
            outline = fit.layout(line, name, location)
        except (ValueError, ZeroDivisionError, TypeError, IndexError) as e:  # a line too short or odd to lay out
            log.warning("outline for %s skipped: %s", circuit, type(e).__name__)
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": fetched_at, "coordinates": line, "key": key, "outline": outline}))
        return outline

    def _line(self, lat, lon, year):
        if year not in self._locations:
            self._locations[year] = json.loads(self._locations_file(year))
        nearest = min(self._locations[year], key=lambda loc: _km(lat, lon, loc["lat"], loc["lon"]))
        if _km(lat, lon, nearest["lat"], nearest["lon"]) > MAX_KM:
            raise LookupError("no outline nearby")
        geojson = json.loads(self.fetch(f"{BASE}/circuits/{nearest['id']}.geojson"))
        return geojson["features"][0]["geometry"]["coordinates"]
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

