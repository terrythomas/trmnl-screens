import importlib
from datetime import date, datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")
games_module = importlib.import_module("trmnl_screens.game-time.collector.games")
games, parse_teams = games_module.games, games_module.parse_teams

TZ = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 23, 20, 5, tzinfo=TZ)
YESTERDAY, TODAY, TOMORROW = date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24)


def team(abbr, home, score=0):
    return espn.EspnTeam(abbr, abbr.title(), f"https://logos.example/{abbr}.png", score, home)


def game(id, start, home="HBR", away="MSA", status="STATUS_SCHEDULED", state="pre", detail="", broadcasts=()):
    return espn.EspnGame(id, start, status, state, detail, team(home, True, 3), team(away, False, 1), broadcasts)


class FakeEspn:
    def __init__(self, boards):
        self.boards = boards  # {(league, day): [EspnGame]}
        self.asked = []

    def scoreboard(self, league, day):
        self.asked.append((league, day))
        return self.boards.get((league, day), [])


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ).astimezone(timezone.utc)


def run(boards, followed=None):
    return games(FakeEspn(boards), followed or {"nba": {"HBR"}}, NOW, TZ)


def test_parse_teams_groups_by_league_case_insensitively():
    assert parse_teams(" nba:bos, NFL:Chi,nba:nyk ,, ") == {"nba": {"BOS", "NYK"}, "nfl": {"CHI"}}


@pytest.mark.parametrize("value", ["nba", "cfl:abc", "nba:"])
def test_parse_teams_rejects_bad_entries(value):
    with pytest.raises(ValueError, match="GAME_TIME_TEAMS"):
        parse_teams(value)


def test_reads_yesterday_today_and_tomorrow_for_each_followed_league():
    fake = FakeEspn({})
    games(fake, {"nba": {"HBR"}, "nhl": {"PNE"}}, NOW, TZ)
    assert sorted(fake.asked) == sorted(
        (league, day) for league in ("nba", "nhl") for day in (YESTERDAY, TODAY, TOMORROW)
    )


def test_maps_a_scheduled_game_to_the_payload_contract():
    broadcasts = (espn.EspnBroadcast("Harbor Sports Net", "TV", "Home"), espn.EspnBroadcast("StreamCo", "Streaming", "National"))
    [mapped] = run({("nba", TODAY): [game("1", at(TODAY, 19), away="HBR", home="MSA", broadcasts=broadcasts)]})
    assert mapped == {
        "league": "nba",
        "start": "2026-10-23T19:00:00-04:00",
        "local_date": "2026-10-23",
        "state": "scheduled",
        "status": None,
        "followed": {"abbr": "HBR", "name": "Hbr", "logo": None, "score": None, "home": False},
        "opponent": {"abbr": "MSA", "name": "Msa", "logo": None, "score": None, "home": True},
        "channels": [{"name": "Harbor Sports Net", "icon": False}, {"name": "StreamCo", "icon": False}],
        "channels_incomplete": False,
        "stale": False,
        "featured": False,
    }


def test_keeps_only_games_with_a_followed_team():
    board = [game("1", at(TODAY, 19)), game("2", at(TODAY, 19), home="PNE", away="LKS")]
    assert [g["followed"]["abbr"] for g in run({("nba", TODAY): board})] == ["HBR"]


@pytest.mark.parametrize("status, state, detail, expected, status_text, scored", [
    ("STATUS_SCHEDULED", "pre", "10/23 - 7:00 PM", "scheduled", None, False),
    ("STATUS_IN_PROGRESS", "in", "5:12 - 3rd", "live", "5:12 - 3rd", True),
    ("STATUS_HALFTIME", "in", "Halftime", "live", "Halftime", True),
    ("STATUS_FINAL", "post", "Final", "final", None, True),
    ("STATUS_POSTPONED", "post", "Postponed", "postponed", None, False),
    ("STATUS_CANCELED", "post", "Canceled", "postponed", None, False),
    ("STATUS_SUSPENDED", "in", "Suspended", "postponed", None, False),
])
def test_maps_states(status, state, detail, expected, status_text, scored):
    [mapped] = run({("nba", TODAY): [game("1", at(TODAY, 12), status=status, state=state, detail=detail)]})
    assert (mapped["state"], mapped["status"]) == (expected, status_text)
    assert (mapped["followed"]["score"], mapped["opponent"]["score"]) == ((3, 1) if scored else (None, None))


def test_a_postponed_game_has_no_channels():
    tv = (espn.EspnBroadcast("National One", "TV", "National"),)
    [mapped] = run({("nba", TODAY): [game("1", at(TODAY, 19), status="STATUS_POSTPONED", state="post", broadcasts=tv)]})
    assert mapped["channels"] == []


def test_two_followed_teams_meeting_is_one_game_with_the_home_team_followed():
    meeting = game("1", at(TODAY, 19), home="PNE", away="HBR")
    [mapped] = run({("nba", TODAY): [meeting]}, {"nba": {"HBR", "PNE"}})
    assert (mapped["followed"]["abbr"], mapped["followed"]["home"]) == ("PNE", True)
    assert mapped["opponent"]["abbr"] == "HBR"


def test_a_game_on_two_scoreboards_is_one_game():
    # ESPN's dates are not local dates, so a late game can appear on two days' scoreboards.
    late = game("1", at(TODAY, 23))
    assert len(run({("nba", TODAY): [late], ("nba", TOMORROW): [late]})) == 1


def test_a_game_live_across_midnight_stays_and_belongs_to_the_day_it_started():
    started = at(YESTERDAY, 22, 30)
    live = game("1", started, status="STATUS_IN_PROGRESS", state="in", detail="Bot 11th")
    over = game("2", started, home="PNE", status="STATUS_FINAL", state="post")
    result = run({("nba", YESTERDAY): [live, over]}, {"nba": {"HBR", "PNE"}})
    assert [(g["local_date"], g["state"]) for g in result] == [("2026-10-22", "live")]


def test_games_outside_the_game_window_are_dropped():
    board = [game("1", at(TOMORROW + timedelta(days=1), 1)), game("2", at(YESTERDAY, 19))]
    assert run({("nba", TOMORROW): board[:1], ("nba", YESTERDAY): board[1:]}) == []


def test_games_are_sorted_by_start_across_leagues():
    boards = {
        ("nba", TOMORROW): [game("1", at(TOMORROW, 13))],
        ("nhl", TODAY): [game("2", at(TODAY, 19), home="PNE")],
        ("nba", TODAY): [game("3", at(TODAY, 12))],
    }
    result = run(boards, {"nba": {"HBR"}, "nhl": {"PNE"}})
    assert [g["start"] for g in result] == [
        "2026-10-23T12:00:00-04:00", "2026-10-23T19:00:00-04:00", "2026-10-24T13:00:00-04:00",
    ]
