import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
sonarr = importlib.import_module("trmnl_screens.media.collector.sources.sonarr")

RECORDING = Path(__file__).parent / "recordings" / "sonarr_calendar.json"
API_KEY = "secret-sonarr-key"
START = datetime(2026, 10, 12, 6, 30, tzinfo=timezone.utc)
END = START + timedelta(hours=24)


def source(handler):
    return sonarr.SonarrSource("http://sonarr.example:8989", API_KEY, transport=httpx.MockTransport(handler))


def replay(request):
    return httpx.Response(200, json=json.loads(RECORDING.read_text()))


def test_calendar_asks_for_the_window_with_series():
    requested = []

    def handler(request):
        requested.append(request)
        return replay(request)

    source(handler).calendar(START, END)

    [request] = requested
    assert request.url.path == "/api/v3/calendar"
    assert dict(request.url.params) == {
        "start": "2026-10-12T06:30:00Z", "end": "2026-10-13T06:30:00Z", "includeSeries": "true",
    }
    assert request.headers["X-Api-Key"] == API_KEY


def test_calendar_maps_episodes():
    episodes = source(replay).calendar(START, END)

    assert len(episodes) == 13
    assert episodes[7] == sonarr.SonarrEpisode(
        series="Night Market",
        series_id=100,
        season=2,
        number=8,
        title="Homecoming",
        air_time=datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc),
        runtime_min=26,
        grabbed=False,
        monitored=False,
        series_monitored=True,
        finale="season",
        poster_url="https://artworks.example/banners/posters/100-1.jpg",
    )
    assert episodes[0].finale is None
    last = episodes[-1]
    assert (last.series, last.grabbed, last.monitored) == ("Signal Fires", True, True)


def test_unknown_episode_runtime_falls_back_to_the_series_runtime():
    [episode] = json.loads(RECORDING.read_text())[:1]
    episode["runtime"] = 0
    episode["series"]["runtime"] = 44

    [mapped] = source(lambda request: httpx.Response(200, json=[episode])).calendar(START, END)

    assert mapped.runtime_min == 44


def fails_with(response=None, error=None):
    def handler(request):
        if error:
            raise error
        return response
    return handler


@pytest.mark.parametrize("handler", [
    fails_with(response=httpx.Response(401)),
    fails_with(response=httpx.Response(200, text="<html>not json</html>")),
    fails_with(response=httpx.Response(200, json=[{"unexpected": True}])),
    fails_with(error=httpx.ConnectError(f"cannot reach http://sonarr.example:8989/?apikey={API_KEY}")),
])
def test_failures_raise_sonarr_error_without_the_key(handler):
    with pytest.raises(sonarr.SonarrError) as raised:
        source(handler).calendar(START, END)

    error = raised.value
    assert API_KEY not in str(error) and "sonarr.example" not in str(error)
    assert error.__cause__ is None and error.__suppress_context__


def test_runtime_is_unknown_when_neither_episode_nor_series_has_one():
    # A brand-new series often has no runtime yet; 0 would print as "0m".
    [episode] = json.loads(RECORDING.read_text())[:1]
    episode["runtime"] = 0
    episode["series"]["runtime"] = 0

    [mapped] = source(lambda request: httpx.Response(200, json=[episode])).calendar(START, END)

    assert mapped.runtime_min is None
