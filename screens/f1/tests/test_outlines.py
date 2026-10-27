import importlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
outlines = importlib.import_module("trmnl_screens.f1.collector.outlines")
fit = importlib.import_module("trmnl_screens.f1.collector.fit")

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
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError(f"not found: {url}", request=request, response=httpx.Response(404, request=request))
        return files[url]

    s = outlines.OutlineStore(tmp_path / "outlines", fetch=fetch)
    s.calls = calls
    return s


GP = ("Example Grand Prix", "Example City, Country")


def points(outline):
    """The outline's path as (x, y) points."""
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", outline["d"])]
    return list(zip(numbers[::2], numbers[1::2]))


def size(pts):
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def test_the_outline_nearest_the_circuit_is_drawn(tmp_path):
    s = store(tmp_path)
    s.outline("square_ring", 60.01, 10.02, 2026, *GP, NOW)
    assert s.calls == [f"{BASE}/championships/f1-locations-2026.json", f"{BASE}/circuits/xx-1.geojson"]


def test_longitude_is_scaled_by_the_cosine_of_latitude(tmp_path):
    width, height = size(points(store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)))
    assert abs(width / height - 1) < 0.02


def test_an_outline_that_fits_as_it_is_stays_north_up(tmp_path):
    assert store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)["angle"] == 0


def test_a_tall_outline_turns_to_fill_the_wide_area(tmp_path):
    outline = store(tmp_path).outline("north_line", 60.0, 10.5, 2026, *GP, NOW)
    pts = points(outline)
    width, height = size(pts)
    assert outline["angle"] != 0 and width > height
    # Clockwise is positive: turned clockwise, north points to the right.
    assert (pts[1][0] - pts[0][0]) * outline["angle"] > 0


def test_no_outline_turns_more_than_a_quarter_turn():
    # An L shape, and the same L turned upside down.
    ell = [[0, 0], [0.004, 0], [0.004, 0.001], [0.001, 0.001], [0.001, 0.003], [0, 0.003]]
    assert all(abs(fit.layout(ell, *GP)["angle"]) <= 90 for ell in (ell, [[-x, -y] for x, y in ell]))


def test_a_long_name_pushes_the_outline_into_less_room(tmp_path):
    short = fit.layout(SQUARE["features"][0]["geometry"]["coordinates"], *GP)
    long = fit.layout(SQUARE["features"][0]["geometry"]["coordinates"], "Exampleistanian Grand Prix", GP[1])
    assert long["x"]["width"] < short["x"]["width"] and long["og"]["width"] < short["og"]["width"]


def test_the_north_arrow_sits_outside_the_circuit_on_both_devices(tmp_path):
    outline = store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)
    for dev in ("x", "og"):
        box = fit.DEVICES[dev]
        x, y = outline[dev]["north"]
        # The square is anchored bottom-right at its share of the area's width; the arrow is left of it or above it.
        left = 100 - outline[dev]["width"]
        top = 100 - outline[dev]["width"] * (box["w"] - box["line"]) / (box["h"] - box["line"]) * outline["h"] / outline["w"]
        assert x < left or y < top, dev


def test_a_new_name_lays_the_cached_line_out_again_without_a_download(tmp_path):
    store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)
    again = store(tmp_path)
    renamed = again.outline("square_ring", 60.0, 10.0, 2026, "Exampleistanian Grand Prix", GP[1], NOW)
    assert again.calls == []
    assert renamed == fit.layout(SQUARE["features"][0]["geometry"]["coordinates"], "Exampleistanian Grand Prix", GP[1])


def test_a_cache_from_before_layouts_is_downloaded_again(tmp_path):
    (tmp_path / "outlines").mkdir()
    (tmp_path / "outlines" / "square_ring.json").write_text(json.dumps({"fetched_at": NOW.isoformat(), "uri": "data:,"}))
    s = store(tmp_path)
    assert s.outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)["d"]
    assert len(s.calls) == 2


def test_a_line_too_short_to_lay_out_only_logs(tmp_path, caplog):
    files = {**FILES, f"{BASE}/circuits/xx-1.geojson": json.dumps(line([10.0, 60.0])).encode()}
    with caplog.at_level(logging.WARNING):
        assert store(tmp_path, files).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW) is None
    assert "outline for square_ring skipped" in caplog.text


def test_outlines_are_cached_and_refreshed_after_a_month(tmp_path):
    first = store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)

    # The next collector run reads the same cache.
    again = store(tmp_path)
    assert again.outline("square_ring", 60.0, 10.0, 2026, *GP, NOW + timedelta(days=29)) == first
    assert again.calls == []

    again.outline("square_ring", 60.0, 10.0, 2026, *GP, NOW + timedelta(days=31))
    assert len(again.calls) == 2


def test_the_locations_file_is_fetched_once_per_run(tmp_path):
    s = store(tmp_path)
    s.outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)
    s.outline("north_line", 60.0, 10.5, 2026, *GP, NOW)
    assert len(s.calls) == 3


def test_a_failed_outline_only_logs_and_hides_the_url(tmp_path, caplog):
    files = {k: v for k, v in FILES.items() if "xx-1" not in k}
    with caplog.at_level(logging.WARNING):
        assert store(tmp_path, files).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW) is None
    assert "outline for square_ring skipped: HTTP 404" in caplog.text
    assert "githubusercontent" not in caplog.text


def test_a_new_season_without_a_locations_file_uses_the_previous_seasons(tmp_path):
    files = {k.replace("2026", "2025"): v for k, v in FILES.items()}
    s = store(tmp_path, files)
    assert s.outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)
    assert s.calls[:2] == [f"{BASE}/championships/f1-locations-2026.json", f"{BASE}/championships/f1-locations-2025.json"]


def test_a_circuit_far_from_every_outline_gets_none(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert store(tmp_path).outline("elsewhere", 26.0, 50.5, 2026, *GP, NOW) is None
    assert "outline for elsewhere skipped" in caplog.text


def test_a_failed_refresh_keeps_the_cached_outline(tmp_path):
    first = store(tmp_path).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW)
    assert store(tmp_path, {}).outline("square_ring", 60.0, 10.0, 2026, *GP, NOW + timedelta(days=31)) == first
