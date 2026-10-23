import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")
nba = importlib.import_module("trmnl_screens.game-time.collector.sources.nba")
sources = importlib.import_module("trmnl_screens.game-time.collector.sources")

PAGE = (Path(__file__).parent / "recordings" / "nba_team_page.html").read_text()
NOW = datetime(2026, 10, 23, 20, 5, tzinfo=timezone(timedelta(hours=-4)))


@pytest.fixture(autouse=True)
def invented_teams(monkeypatch):
    monkeypatch.setitem(nba.TEAM_IDS, "HBR", 1)


class Page:
    """Serves `response` (the recorded page by default) and keeps the requests."""

    def __init__(self, response=None, error=None):
        self.response, self.error, self.requests = response, error, []

    def __call__(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response or httpx.Response(200, text=PAGE)


def source(tmp_path, handler, now=NOW):
    return nba.NbaSource(tmp_path / "nba.json", now, transport=httpx.MockTransport(handler))


def test_season_asks_for_the_team_page_as_a_browser(tmp_path):
    page = Page()
    source(tmp_path, page).season("HBR")

    [request] = page.requests
    assert request.url == "https://www.nba.com/team/1/schedule"
    # nba.com answers a descriptive User-Agent with HTTP 403
    assert request.headers["User-Agent"].startswith("Mozilla/5.0")


def test_season_maps_games_and_their_tv_channels(tmp_path):
    assert source(tmp_path, Page()).season("HBR") == [
        sources.LeagueGame(
            start=datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc), home="Gulls", away="Coyotes",
            broadcasts=(
                espn.EspnBroadcast("Harbor Sports Net", "TV", "Home"),
                espn.EspnBroadcast("Mesa TV", "TV", "Away"),
            ),
        ),
        sources.LeagueGame(
            start=datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc), home="Pines", away="Gulls",
            broadcasts=(espn.EspnBroadcast("National One", "TV", "National"),),
        ),
    ]


def test_a_page_is_read_once_a_day(tmp_path):
    page = Page()
    first = source(tmp_path, page).season("HBR")
    assert source(tmp_path, page, NOW + timedelta(hours=23)).season("HBR") == first
    assert len(page.requests) == 1

    source(tmp_path, page, NOW + timedelta(days=1, minutes=1)).season("HBR")
    assert len(page.requests) == 2


def test_a_failure_is_asked_once_per_run(tmp_path):
    page = Page(httpx.Response(503))
    nba_source = source(tmp_path, page)
    for _ in range(2):
        with pytest.raises(nba.NbaError):
            nba_source.season("HBR")
    assert len(page.requests) == 1


def test_a_team_without_a_page_fails_without_a_request(tmp_path):
    page = Page()
    with pytest.raises(nba.NbaError, match="no nba.com page for XYZ"):
        source(tmp_path, page).season("XYZ")
    assert page.requests == []


def test_an_unreadable_cache_is_fetched_again(tmp_path):
    (tmp_path / "nba.json").write_text("{not json")
    assert len(source(tmp_path, Page()).season("HBR")) == 2
    assert "HBR" in json.loads((tmp_path / "nba.json").read_text())


@pytest.mark.parametrize("page, message", [
    (Page(httpx.Response(403)), "nba.com returned HTTP 403"),
    (Page(error=httpx.ConnectError("boom")), "nba.com request failed: ConnectError"),
    (Page(httpx.Response(200, text="<html>redesigned</html>")), "nba.com returned an unexpected page"),
    (Page(httpx.Response(200, text=PAGE.replace('"gameDateTimeUTC"', '"renamed"'))),
     "nba.com returned an unexpected page"),
])
def test_failures_raise_one_error_type(tmp_path, page, message):
    with pytest.raises(nba.NbaError, match=message) as e:
        source(tmp_path, page).season("HBR")
    assert isinstance(e.value, sources.LeagueError)
