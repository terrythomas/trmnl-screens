import importlib
import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
radarr = importlib.import_module("trmnl_screens.media.collector.sources.radarr")

RECORDING = Path(__file__).parent / "recordings" / "radarr_calendar.json"
API_KEY = "secret-radarr-key"
DAY = date(2026, 10, 12)
NEXT_DAY = DAY + timedelta(days=1)
TMDB_ID = 700001


def source(handler):
    return radarr.RadarrSource("http://radarr.example:7878", API_KEY, transport=httpx.MockTransport(handler))


def replay(request):
    return httpx.Response(200, json=json.loads(RECORDING.read_text()))


def test_calendar_asks_for_the_range():
    requested = []

    def handler(request):
        requested.append(request)
        return replay(request)

    source(handler).calendar(DAY, NEXT_DAY)

    request = requested[0]
    assert request.url.path == "/api/v3/calendar"
    # Explicit UTC: Radarr reads a bare date in its own zone, which misses midnight-UTC releases.
    assert dict(request.url.params) == {"start": "2026-10-12T00:00:00Z", "end": "2026-10-13T00:00:00Z"}

    source(handler).calendar(DAY - timedelta(days=90), NEXT_DAY)
    assert dict(requested[-1].url.params)["start"] == "2026-07-14T00:00:00Z"
    assert request.headers["X-Api-Key"] == API_KEY


def test_calendar_maps_movies():
    movies = source(replay).calendar(DAY, NEXT_DAY)

    assert [m.title for m in movies] == ["Harbor Lights", "The Long Field", "Paper Moons", "Quiet Hours", "Cold Open"]
    assert movies[0] == radarr.RadarrMovie(
        tmdb_id=TMDB_ID,
        title="Harbor Lights",
        year=2026,
        in_cinemas=date(2026, 10, 12),
        digital_release=None,
        grabbed=False,
        monitored=True,
        runtime_min=112,
        poster_url="https://images.example/t/p/original/1-poster.jpg",
    )
    assert (movies[2].digital_release, movies[2].grabbed) == (date(2026, 10, 12), True)
    assert movies[3].monitored is False


def test_release_dates_are_calendar_dates_not_moments():
    # Radarr stores a release date as midnight UTC. Converting it to a zone west of UTC
    # would land on the evening before, so it must be read as a plain date.
    [movie] = source(lambda request: httpx.Response(200, json=[
        {**json.loads(RECORDING.read_text())[0], "inCinemas": "2026-10-14T00:00:00Z"},
    ])).calendar(DAY, NEXT_DAY)

    assert movie.in_cinemas == date(2026, 10, 14)


def test_unknown_runtime_and_missing_poster():
    long_field = source(replay).calendar(DAY, NEXT_DAY)[1]

    assert (long_field.runtime_min, long_field.poster_url) == (None, None)


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
    fails_with(error=httpx.ConnectError(f"cannot reach http://radarr.example:7878/?apikey={API_KEY}")),
])
def test_failures_raise_radarr_error_without_the_key(handler):
    with pytest.raises(radarr.RadarrError) as raised:
        source(handler).calendar(DAY, NEXT_DAY)

    error = raised.value
    assert API_KEY not in str(error) and "radarr.example" not in str(error)
    assert error.__cause__ is None and error.__suppress_context__
