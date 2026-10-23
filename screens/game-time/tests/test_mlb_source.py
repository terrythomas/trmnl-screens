import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")
sources = importlib.import_module("trmnl_screens.game-time.collector.sources")
mlb = importlib.import_module("trmnl_screens.game-time.collector.sources.mlb")

SCHEDULE = json.loads((Path(__file__).parent / "recordings" / "mlb_schedule.json").read_text())
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone(timedelta(hours=-4)))


@pytest.fixture(autouse=True)
def invented_team(monkeypatch):
    monkeypatch.setitem(mlb.TEAM_IDS, "HBR", 901)


def source(handler):
    return mlb.MlbSource(NOW, transport=httpx.MockTransport(handler))


def replay(body):
    return lambda request: httpx.Response(200, json=body)


def test_season_asks_for_the_teams_games_around_now():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(200, json=SCHEDULE)

    source(handler).season("HBR")

    [request] = requested
    assert request.url.host == "statsapi.mlb.com"
    assert request.url.path == "/api/v1/schedule"
    assert dict(request.url.params) == {
        "sportId": "1", "teamId": "901", "startDate": "2026-09-10", "endDate": "2026-09-14",
        "hydrate": "broadcasts(all),team",
    }


def test_season_maps_games_and_broadcasts():
    games = source(replay(SCHEDULE)).season("HBR")

    assert games == [
        sources.LeagueGame(
            start=datetime(2026, 9, 12, 23, 5, tzinfo=timezone.utc),
            home="Gulls",
            away="Coyotes",
            broadcasts=(
                espn.EspnBroadcast("Harbor Sports Net", "TV", "Home"),
                espn.EspnBroadcast("Mesa Channel 9", "TV", "Away"),
                # National games are listed once per side; isNational wins over homeAway.
                espn.EspnBroadcast("National One", "TV", "National"),
                espn.EspnBroadcast("National One", "TV", "National"),
                espn.EspnBroadcast("Harbor 101 FM", "Radio", "Home"),
                espn.EspnBroadcast("Mesa 1400 AM", "Radio", "Away"),
            ),
        ),
        sources.LeagueGame(
            start=datetime(2026, 9, 13, 0, 15, tzinfo=timezone.utc),
            home="Larks",
            away="Pines",
            # A streaming exclusive is a national TV broadcast in this API.
            broadcasts=(espn.EspnBroadcast("StreamCo", "TV", "National"),) * 2,
        ),
        sources.LeagueGame(datetime(2026, 9, 13, 17, 35, tzinfo=timezone.utc), "Pines", "Gulls", ()),
    ]


def test_team_names_are_espns():
    body = {"dates": [{"games": [{
        "gameDate": "2026-09-12T23:05:00Z",
        "teams": {"away": {"team": {"teamName": "D-backs"}}, "home": {"team": {"teamName": "Gulls"}}},
    }]}]}

    [game] = source(replay(body)).season("HBR")

    assert (game.home, game.away) == ("Gulls", "Diamondbacks")


def test_each_team_is_asked_for_once_per_run_even_when_it_fails():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(503)

    mlb_source = source(handler)
    for _ in range(2):
        with pytest.raises(mlb.MlbError):
            mlb_source.season("HBR")
    assert len(requested) == 1


def test_a_team_without_an_mlb_id_fails():
    with pytest.raises(mlb.MlbError, match="no MLB team id for XYZ"):
        source(replay(SCHEDULE)).season("XYZ")


def fails_with(response=None, error=None):
    def handler(request):
        if error:
            raise error
        return response

    return handler


@pytest.mark.parametrize("handler, message", [
    (fails_with(httpx.Response(503)), "MLB Stats API returned HTTP 503"),
    (fails_with(error=httpx.ConnectError("boom")), "MLB Stats API request failed: ConnectError"),
    (fails_with(httpx.Response(200, json={"dates": [{"games": [{"gameDate": "x"}]}]})),
     "MLB Stats API returned an unexpected response"),
])
def test_failures_raise_one_league_error_type(handler, message):
    with pytest.raises(mlb.MlbError, match=message) as raised:
        source(handler).season("HBR")
    assert isinstance(raised.value, sources.LeagueError)
