import importlib
from datetime import datetime, timedelta, timezone

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")
sources = importlib.import_module("trmnl_screens.game-time.collector.sources")
games = importlib.import_module("trmnl_screens.game-time.collector.games").games

TZ = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=TZ)
START = datetime(2026, 10, 23, 19, 0, tzinfo=TZ)

ESPN_CHANNELS = (
    espn.EspnBroadcast("Mesa TV", "TV", "Away"),
    espn.EspnBroadcast("StreamCo", "Streaming", "National"),
)


def team(abbr, name, home):
    return espn.EspnTeam(abbr, name, None, 0, home)


def espn_game(id="1", start=START):
    return espn.EspnGame(id, start, "STATUS_SCHEDULED", "pre", "", team("HBR", "Gulls", True),
                         team("MSA", "Coyotes", False), ESPN_CHANNELS)


class FakeEspn:
    def __init__(self, *found):
        self.found = found

    def scoreboard(self, league, day):
        return [g for g in self.found if g.start.astimezone(TZ).date() == day]


def league_game(start=START, home="Gulls", away="Coyotes", channel="Harbor Sports Net"):
    return sources.LeagueGame(start, home, away, (espn.EspnBroadcast(channel, "TV", "Home"),))


class FakeLeague:
    def __init__(self, *season, error=None):
        self.found, self.error, self.asked = list(season), error, []

    def season(self, team):
        self.asked.append(team)
        if self.error:
            raise self.error
        return self.found


def run(league_source, *found):
    return games(FakeEspn(*found or [espn_game()]), {"nba": {"HBR"}}, NOW, TZ, sources={"nba": league_source})


def channels(game):
    return [c["name"] for c in game["channels"]], game["channels_incomplete"]


def test_the_league_source_replaces_espns_tv_channels():
    league = FakeLeague(league_game(start=START.astimezone(timezone.utc)))
    [game] = run(league)
    # ESPN's streaming stays; its TV channels give way to the league source's
    assert channels(game) == (["Harbor Sports Net", "StreamCo"], False)
    assert league.asked == ["HBR"]


def test_an_unmatched_game_falls_back_to_espn(caplog):
    [game] = run(FakeLeague(league_game(home="Pines")))
    assert channels(game) == (["StreamCo"], True)
    assert "no match" in caplog.text


def test_a_game_on_another_day_is_not_a_match():
    [game] = run(FakeLeague(league_game(start=START + timedelta(days=1))))
    assert channels(game) == (["StreamCo"], True)


def test_a_failed_source_falls_back_to_espn(caplog):
    [game] = run(FakeLeague(error=sources.LeagueError("nba.com returned HTTP 503")))
    assert channels(game) == (["StreamCo"], True)
    assert "nba.com returned HTTP 503" in caplog.text


def test_same_day_games_between_the_same_teams_match_by_start_time():
    league = FakeLeague(
        league_game(start=START - timedelta(hours=5), channel="Early Net"),
        league_game(start=START + timedelta(minutes=10), channel="Late Net"),
    )
    first, second = run(league, espn_game("1", START - timedelta(hours=5)), espn_game("2", START))
    assert channels(first) == (["Early Net", "StreamCo"], False)
    assert channels(second) == (["Late Net", "StreamCo"], False)


def test_leagues_without_a_source_keep_espns_channels():
    [game] = games(FakeEspn(espn_game()), {"nba": {"HBR"}}, NOW, TZ)
    assert channels(game) == (["StreamCo"], False)
