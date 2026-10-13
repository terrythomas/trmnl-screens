import importlib
import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
tmdb = importlib.import_module("trmnl_screens.media.collector.sources.tmdb")

RECORDING = Path(__file__).parent / "recordings" / "tmdb_releases.html"
TODAY = date(2026, 11, 4)
Release = tmdb.Release


def page(request=None):
    return httpx.Response(200, text=RECORDING.read_text())


def source(handler, tmp_path, country="US"):
    return tmdb.TmdbSource(country, tmp_path / "tmdb-releases.json", transport=httpx.MockTransport(handler))


def test_parses_the_countrys_rows():
    assert tmdb.parse_releases(RECORDING.read_text(), "US") == [
        Release(date(2026, 9, 26), "Premiere", "Harbor Film Festival"),
        Release(date(2026, 11, 3), "Theatrical (limited)", "IMAX"),
        Release(date(2026, 11, 6), "Theatrical", None),
        Release(date(2026, 12, 15), "Digital", None),
    ]


def test_country_codes_are_case_insensitive():
    assert tmdb.parse_releases(RECORDING.read_text(), "gb") == [Release(date(2026, 11, 4), "Theatrical", None)]


def test_a_country_without_releases_has_no_rows():
    assert tmdb.parse_releases(RECORDING.read_text(), "FR") == []


@pytest.mark.parametrize("html", [
    pytest.param("<html><body><h1>Release dates</h1></body></html>", id="no release tables: the page changed"),
    pytest.param(RECORDING.read_text().replace("11/06/2026", "06.11.2026"), id="a date in another format"),
])
def test_an_unrecognised_page_raises(html):
    with pytest.raises(tmdb.TmdbError):
        tmdb.parse_releases(html, "US")


def test_request_asks_for_the_english_release_page(tmp_path):
    requested = []

    def handler(request):
        requested.append(request)
        return page()

    source(handler, tmp_path).releases(700001, TODAY)

    [request] = requested
    assert str(request.url) == "https://www.themoviedb.org/movie/700001/releases"
    assert request.headers["Accept-Language"] == "en-US"
    assert request.headers["User-Agent"].startswith("trmnl-screens")


def test_each_movie_is_fetched_once_per_day(tmp_path):
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return page()

    first = source(handler, tmp_path)
    first.releases(700001, TODAY)
    first.releases(700001, TODAY)
    # A new source reads the cache file, as the next tick would.
    assert source(handler, tmp_path).releases(700001, TODAY)[1].note == "IMAX"
    assert requested == ["/movie/700001/releases"]

    source(handler, tmp_path).releases(700001, TODAY + timedelta(days=1))
    assert len(requested) == 2


def test_the_cache_keeps_only_todays_entries(tmp_path):
    source(page, tmp_path).releases(700001, TODAY)
    source(page, tmp_path).releases(700002, TODAY + timedelta(days=1))

    assert set(json.loads((tmp_path / "tmdb-releases.json").read_text())) == {"US/700002"}


def test_the_cache_is_per_country(tmp_path):
    source(page, tmp_path, "US").releases(700001, TODAY)
    assert source(page, tmp_path, "GB").releases(700001, TODAY) == [Release(date(2026, 11, 4), "Theatrical", None)]


def test_an_unreadable_cache_starts_fresh(tmp_path):
    (tmp_path / "tmdb-releases.json").write_text("{not json")
    assert len(source(page, tmp_path).releases(700001, TODAY)) == 4


def fails_with(response=None, error=None):
    def handler(request):
        if error:
            raise error
        return response
    return handler


@pytest.mark.parametrize("handler", [
    fails_with(response=httpx.Response(403)),
    fails_with(response=httpx.Response(200, text="<html>a redesigned page</html>")),
    fails_with(error=httpx.ConnectError("cannot reach https://www.themoviedb.org/movie/700001/releases")),
])
def test_failures_raise_tmdb_error_without_the_url(handler, tmp_path):
    with pytest.raises(tmdb.TmdbError) as raised:
        source(handler, tmp_path).releases(700001, TODAY)

    error = raised.value
    assert "themoviedb.org" not in str(error) and error.source == "tmdb"
    # No chained httpx error either: their messages can include the URL.
    assert error.__cause__ is None and (error.__context__ is None or error.__suppress_context__)
