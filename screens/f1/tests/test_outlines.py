import base64
import importlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
outlines = importlib.import_module("trmnl_screens.f1.collector.outlines")

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
BASE = "https://raw.githubusercontent.com/bacinger/f1-circuits/master"

# Every line below is invented here; no real circuit outline is used (ADR-0010).
LOCATIONS = [
    {"lon": 10.0, "lat": 60.0, "id": "xx-1"},
    {"lon": 10.5, "lat": 60.0, "id": "xx-2"},
]


def line(*points):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": list(points)}}]}


# A rectangle 2 degrees of longitude wide and 1 of latitude tall: square on the ground at 60 degrees north.
SQUARE = line([9.0, 59.5], [11.0, 59.5], [11.0, 60.5], [9.0, 60.5], [9.0, 59.5])
# A tall thin line from south to north.
NORTHBOUND = line([10.5, 59.9], [10.5, 60.1], [10.51, 60.1])

FILES = {
    f"{BASE}/championships/f1-locations-2026.json": json.dumps(LOCATIONS).encode(),
    f"{BASE}/circuits/xx-1.geojson": json.dumps(SQUARE).encode(),
    f"{BASE}/circuits/xx-2.geojson": json.dumps(NORTHBOUND).encode(),
}


def store(tmp_path, files=FILES):
    calls = []

    def fetch(url):
        calls.append(url)
        if url not in files:
            raise httpx.ConnectError(f"cannot reach {url}")
        return files[url]

    s = outlines.OutlineStore(tmp_path / "outlines", fetch=fetch)
    s.calls = calls
    return s


def points(uri):
    """The outline's path as (x, y) points."""
    prefix = "data:image/svg+xml;base64,"
    assert uri.startswith(prefix)
    svg = base64.b64decode(uri[len(prefix):]).decode()
    d = re.search(r' d="([^"]+)"', svg).group(1)
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    return list(zip(numbers[::2], numbers[1::2]))


def size(pts):
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def test_the_outline_nearest_the_circuit_is_drawn(tmp_path):
    s = store(tmp_path)
    s.outline("square_ring", 60.01, 10.02, 2026, NOW)
    assert s.calls == [f"{BASE}/championships/f1-locations-2026.json", f"{BASE}/circuits/xx-1.geojson"]


def test_longitude_is_scaled_by_the_cosine_of_latitude(tmp_path):
    width, height = size(points(store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, NOW)))
    assert abs(width / height - 1) < 0.02


def test_outlines_are_drawn_north_up(tmp_path):
    pts = points(store(tmp_path).outline("north_line", 60.0, 10.5, 2026, NOW))
    width, height = size(pts)
    assert height > 5 * width
    assert pts[0][1] > pts[1][1]  # heading north goes up the image


def test_outlines_are_cached_and_refreshed_after_a_month(tmp_path):
    first = store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, NOW)

    # The next collector run reads the same cache.
    again = store(tmp_path)
    assert again.outline("square_ring", 60.0, 10.0, 2026, NOW + timedelta(days=29)) == first
    assert again.calls == []

    again.outline("square_ring", 60.0, 10.0, 2026, NOW + timedelta(days=31))
    assert len(again.calls) == 2


def test_the_locations_file_is_fetched_once_per_run(tmp_path):
    s = store(tmp_path)
    s.outline("square_ring", 60.0, 10.0, 2026, NOW)
    s.outline("north_line", 60.0, 10.5, 2026, NOW)
    assert len(s.calls) == 3


def test_a_failed_outline_only_logs_and_hides_the_url(tmp_path, caplog):
    files = {k: v for k, v in FILES.items() if "xx-1" not in k}
    with caplog.at_level(logging.WARNING):
        assert store(tmp_path, files).outline("square_ring", 60.0, 10.0, 2026, NOW) is None
    assert "outline for square_ring skipped: ConnectError" in caplog.text
    assert "githubusercontent" not in caplog.text


def test_a_circuit_far_from_every_outline_gets_none(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert store(tmp_path).outline("elsewhere", 26.0, 50.5, 2026, NOW) is None
    assert "outline for elsewhere skipped" in caplog.text


def test_a_failed_refresh_keeps_the_cached_outline(tmp_path):
    first = store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, NOW)
    assert store(tmp_path, {}).outline("square_ring", 60.0, 10.0, 2026, NOW + timedelta(days=31)) == first
