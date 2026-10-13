import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
plex = importlib.import_module("trmnl_screens.media.collector.sources.plex")

RECORDINGS = Path(__file__).parent / "recordings"
TOKEN = "secret-plex-token"


def source(handler):
    return plex.PlexSource("http://plex.example:32400", TOKEN, transport=httpx.MockTransport(handler))


def replay(name):
    body = json.loads((RECORDINGS / name).read_text())
    return lambda request: httpx.Response(200, json=body)


def test_continue_watching_maps_episodes_and_movies():
    items = source(replay("plex_continue_watching.json")).continue_watching()

    assert len(items) == 11
    assert items[0] == plex.PlexItem(
        kind="episode",
        title="The Lighthouse Keepers",
        season=2,
        number=7,
        episode_title="Low Tide",
        duration_ms=1_560_000,
        view_offset_ms=655_000,
        last_viewed_at=datetime.fromtimestamp(1791000000, timezone.utc),
        show_key="4000",
        poster_path="/library/metadata/4000/thumb/1791000000",
    )
    movie = items[3]
    assert (movie.kind, movie.title, movie.season, movie.episode_title, movie.show_key) == (
        "movie", "A Quiet Orbit", None, None, None)
    assert movie.poster_path == "/library/metadata/5003/thumb/1791000000"
    assert items[1].view_offset_ms is None


def fails_with(response=None, error=None):
    def handler(request):
        if error:
            raise error
        return response
    return handler


@pytest.mark.parametrize("handler", [
    fails_with(response=httpx.Response(401)),
    fails_with(response=httpx.Response(200, text="<html>not json</html>")),
    fails_with(response=httpx.Response(200, json={"unexpected": True})),
    fails_with(error=httpx.ConnectError(f"cannot reach http://plex.example:32400/?X-Plex-Token={TOKEN}")),
])
def test_failures_raise_plex_error_without_the_token(handler):
    with pytest.raises(plex.PlexError) as raised:
        source(handler).continue_watching()

    error = raised.value
    assert TOKEN not in str(error) and "plex.example" not in str(error)
    assert error.__cause__ is None and error.__suppress_context__


def test_show_history_reads_when_the_show_was_last_viewed():
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return replay("plex_show.json")(request)

    history = source(handler).show_history("4000")

    assert requested == ["/library/metadata/4000"]
    assert history == plex.ShowHistory(last_viewed_at=datetime.fromtimestamp(1790740800, timezone.utc))


def test_show_history_of_a_never_watched_show():
    body = {"MediaContainer": {"Metadata": [{"ratingKey": "4001", "type": "show", "leafCount": 8}]}}

    history = source(lambda request: httpx.Response(200, json=body)).show_history("4001")

    assert history == plex.ShowHistory(last_viewed_at=None)


def test_show_whose_watched_episodes_were_deleted_still_has_history():
    # viewedLeafCount only counts episodes still in the library; lastViewedAt keeps the history.
    body = {"MediaContainer": {"Metadata": [{
        "ratingKey": "4002", "type": "show", "leafCount": 3, "viewedLeafCount": 0,
        "viewCount": 48, "lastViewedAt": 1790740800,
    }]}}

    history = source(lambda request: httpx.Response(200, json=body)).show_history("4002")

    assert history == plex.ShowHistory(last_viewed_at=datetime.fromtimestamp(1790740800, timezone.utc))


def test_show_history_of_a_missing_show_raises_plex_error():
    with pytest.raises(plex.PlexError):
        source(lambda request: httpx.Response(200, json={"MediaContainer": {"size": 0}})).show_history("4999")


def test_poster_is_fetched_grayscale_at_the_requested_size():
    requested = []

    def handler(request):
        requested.append(request.url)
        return httpx.Response(200, content=b"\xff\xd8jpeg-bytes")

    poster = source(handler).poster("/library/metadata/4000/thumb/1791000000", width=234, height=351)

    assert poster == b"\xff\xd8jpeg-bytes"
    [url] = requested
    assert url.path == "/photo/:/transcode"
    assert dict(url.params) == {
        "url": "/library/metadata/4000/thumb/1791000000", "width": "234", "height": "351",
        "saturation": "0", "minSize": "1", "upscale": "1", "format": "jpeg",
    }


def test_failed_poster_raises_plex_error():
    with pytest.raises(plex.PlexError, match="HTTP 404"):
        source(lambda request: httpx.Response(404)).poster("/missing", width=234, height=351)
