import importlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")

RECORDINGS = Path(__file__).parent / "recordings"
SCOREBOARD = json.loads((RECORDINGS / "espn_scoreboard.json").read_text())
TEAMS = json.loads((RECORDINGS / "espn_teams.json").read_text())


def source(handler):
    return espn.EspnSource(transport=httpx.MockTransport(handler))


def replay(body):
    return lambda request: httpx.Response(200, json=body)


def test_scoreboard_asks_for_the_league_and_day():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(200, json=SCOREBOARD)

    source(handler).scoreboard("mls", date(2026, 10, 3))

    [request] = requested
    assert request.url.host == "site.api.espn.com"
    assert request.url.path == "/apis/site/v2/sports/soccer/usa.1/scoreboard"
    assert dict(request.url.params) == {"dates": "20261003"}


def test_scoreboard_maps_games():
    games = source(replay(SCOREBOARD)).scoreboard("nba", date(2026, 10, 23))

    assert len(games) == 4
    assert games[0] == espn.EspnGame(
        id="1001",
        start=datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc),
        status="STATUS_SCHEDULED",
        state="pre",
        detail="10/23 - 7:00 PM EDT",
        home=espn.EspnTeam("HBR", "Gulls", "https://logos.example/hbr.png", 0, True),
        away=espn.EspnTeam("MSA", "Coyotes", "https://logos.example/msa.png", 0, False),
        broadcasts=(
            espn.EspnBroadcast("Harbor Sports Net", "TV", "Home"),
            espn.EspnBroadcast("National One", "TV", "National"),
            espn.EspnBroadcast("StreamCo", "Streaming", "National"),
            espn.EspnBroadcast("Harbor 101 FM", "Radio", "Home"),
        ),
    )
    live = games[1]
    assert (live.state, live.detail, live.home.score, live.away.score) == ("in", "5:12 - 3rd", 66, 71)
    assert games[2].broadcasts == ()


def test_teams_lists_the_league_abbreviations():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(200, json=TEAMS)

    assert source(handler).teams("nhl") == {"HBR", "MSA", "PNE", "LKS"}
    assert requested[0].url.path == "/apis/site/v2/sports/hockey/nhl/teams"


def fails_with(response=None, error=None):
    def handler(request):
        if error:
            raise error
        return response

    return handler


@pytest.mark.parametrize("handler, message", [
    (fails_with(httpx.Response(503)), "ESPN returned HTTP 503"),
    (fails_with(error=httpx.ConnectError("boom")), "ESPN request failed: ConnectError"),
    (fails_with(httpx.Response(200, json={"events": [{"id": "1"}]})), "ESPN returned an unexpected response"),
])
def test_failures_raise_one_error_type(handler, message):
    with pytest.raises(espn.EspnError, match=message):
        source(handler).scoreboard("nba", date(2026, 10, 23))
