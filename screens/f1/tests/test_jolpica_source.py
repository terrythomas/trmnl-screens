import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
jolpica = importlib.import_module("trmnl_screens.f1.collector.sources.jolpica")

SEASON = json.loads((Path(__file__).parent / "recordings" / "jolpica_season.json").read_text())


def source(handler):
    return jolpica.JolpicaSource(transport=httpx.MockTransport(handler))


def replay(body):
    return lambda request: httpx.Response(200, json=body)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_season_asks_for_the_years_schedule():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(200, json=SEASON)

    source(handler).season(2026)

    [request] = requested
    assert (request.url.host, request.url.path) == ("api.jolpi.ca", "/ergast/f1/2026.json")


def test_season_maps_a_conventional_weekend():
    brazil = source(replay(SEASON)).season(2026)[3]
    assert brazil == jolpica.GrandPrix(
        round=20, name="Brazilian Grand Prix", location="São Paulo, Brazil", circuit="interlagos",
        lat=-23.7036, lon=-46.6997,
        sessions=(
            ("practice_1", utc(2026, 11, 6, 15, 30)),
            ("practice_2", utc(2026, 11, 6, 19, 0)),
            ("practice_3", utc(2026, 11, 7, 14, 30)),
            ("qualifying", utc(2026, 11, 7, 18, 0)),
            ("race", utc(2026, 11, 8, 17, 0)),
        ),
    )


def test_a_sprint_weekends_sessions_are_in_start_order():
    singapore = source(replay(SEASON)).season(2026)[0]
    assert [kind for kind, _ in singapore.sessions] == [
        "practice_1", "sprint_qualifying", "sprint", "qualifying", "race"]


def fails_with(response=None, error=None):
    def handler(request):
        if error:
            raise error
        return response

    return handler


@pytest.mark.parametrize("handler, message", [
    (fails_with(httpx.Response(503)), "Jolpica returned HTTP 503"),
    (fails_with(error=httpx.ConnectError("boom")), "Jolpica request failed: ConnectError"),
    (fails_with(httpx.Response(200, json={"MRData": {}})), "Jolpica returned an unexpected response"),
])
def test_failures_raise_one_error_type(handler, message):
    with pytest.raises(jolpica.JolpicaError, match=message):
        source(handler).season(2026)
