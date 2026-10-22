import importlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")
games = importlib.import_module("trmnl_screens.game-time.collector.games").games
channels = importlib.import_module("trmnl_screens.game-time.collector.channels")

TZ = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=TZ)

# Invented channels; the national names stand in for any network in the channel map.
HOME_NET = ("Harbor Sports Net", "TV", "Home")
AWAY_NET = ("Lakeshore TV", "TV", "Away")
NATIONAL = ("FOX", "TV", "National")
STREAMING = ("Prime Video", "Streaming", "National")
PACKAGE = ("Arena Pass", "Subscription Package", "National")
RADIO = ("Harbor 101 FM", "Radio", "Home")


class FakeEspn:
    def __init__(self, league, game):
        self.league, self.game = league, game

    def scoreboard(self, league, day):
        return [self.game] if league == self.league and day == NOW.date() else []


def shown(*broadcasts, followed=("HBR",), league="nba", home="HBR", away="LKS"):
    team = lambda abbr, is_home: espn.EspnTeam(abbr, abbr.title(), None, 0, is_home)
    game = espn.EspnGame("1", NOW + timedelta(hours=7), "STATUS_SCHEDULED", "pre", "",
                         team(home, True), team(away, False), tuple(espn.EspnBroadcast(*b) for b in broadcasts))
    [mapped] = games(FakeEspn(league, game), {league: set(followed)}, NOW, TZ)
    return [c["name"] for c in mapped["channels"]]


def test_local_only():
    assert shown(HOME_NET) == ["Harbor Sports Net"]


def test_the_local_channel_is_the_followed_teams_side_even_when_away():
    assert shown(HOME_NET, AWAY_NET, home="LKS", away="HBR") == ["Lakeshore TV"]


def test_local_wins_over_national():
    assert shown(NATIONAL, HOME_NET) == ["Harbor Sports Net"]


def test_national_only():
    assert shown(NATIONAL, AWAY_NET) == ["FOX"]


def test_streaming_only():
    assert shown(STREAMING) == ["Prime Video"]


def test_streaming_follows_local_or_national():
    assert shown(STREAMING, HOME_NET) == ["Harbor Sports Net", "Prime Video"]
    assert shown(STREAMING, NATIONAL) == ["FOX", "Prime Video"]


def test_both_teams_followed_show_both_local_channels():
    assert shown(HOME_NET, NATIONAL, AWAY_NET, followed=("HBR", "LKS")) == ["Harbor Sports Net", "Lakeshore TV"]


def test_opponent_only_fallback():
    assert shown(AWAY_NET) == ["Lakeshore TV"]


def test_package_only_fallback():
    assert shown(PACKAGE) == ["Arena Pass"]


def test_opponent_and_packages_only_when_nothing_else():
    assert shown(PACKAGE, AWAY_NET) == ["Lakeshore TV", "Arena Pass"]
    assert shown(PACKAGE, AWAY_NET, STREAMING) == ["Prime Video"]


def test_named_packages_listed_as_streaming_are_packages():
    assert shown(("NBA League Pass", "Streaming", "National"), STREAMING) == ["Prime Video"]


def test_radio_is_dropped():
    assert shown(RADIO) == []
    assert shown(RADIO, HOME_NET) == ["Harbor Sports Net"]


@pytest.mark.parametrize("league, expected", [("nhl", ["Prime Video"]), ("nba", ["ESPN+", "Prime Video"])])
def test_espn_plus_is_a_package_for_the_nhl_only(league, expected):
    assert shown(("ESPN+", "Streaming", "National"), STREAMING, league=league) == expected


def test_spellings_are_normalised_and_deduplicated():
    assert shown(("Amazon Prime Video", "Streaming", "National"), ("prime video", "Streaming", "National")) == ["Prime Video"]
    assert shown((" fox ", "TV", "National")) == ["FOX"]


def test_every_spelling_and_package_points_into_the_map():
    names = set(channels.SPELLINGS.values()) | channels.PACKAGES | {name for _, name in channels.LEAGUE_PACKAGES}
    assert names <= channels.CHANNELS.keys()


def game(league, *names):
    return {"league": league, "channels": [{"name": n, "icon": False} for n in names]}


def read(path):
    return json.loads(path.read_text())


def test_records_an_unknown_channel_once(tmp_path):
    path = tmp_path / "game-time" / "unknown-channels.json"
    first, later = NOW, NOW + timedelta(hours=1)
    channels.record_unknown(path, [game("nba", "Harbor Sports Net", "FOX"), game("nba", "Harbor Sports Net")], first)
    channels.record_unknown(path, [game("nba", "Harbor Sports Net")], later)
    assert read(path) == [{
        "name": "Harbor Sports Net", "league": "nba",
        "first_seen": first.isoformat(timespec="seconds"), "last_seen": later.isoformat(timespec="seconds"),
        "times_seen": 2,
    }]


def test_a_channel_added_to_the_map_leaves_the_file(tmp_path, monkeypatch):
    path = tmp_path / "unknown-channels.json"
    channels.record_unknown(path, [game("nhl", "Harbor Sports Net", "Lakeshore TV")], NOW)
    monkeypatch.setitem(channels.CHANNELS, "Harbor Sports Net", {})
    channels.record_unknown(path, [], NOW)
    assert [e["name"] for e in read(path)] == ["Lakeshore TV"]


def test_text_only_channels_are_never_recorded(tmp_path):
    assert channels.CHANNELS["Peacock"] == {"text_only": True}
    path = tmp_path / "unknown-channels.json"
    channels.record_unknown(path, [game("nfl", "Peacock")], NOW)
    assert read(path) == []


def test_an_unreadable_file_starts_fresh(tmp_path):
    path = tmp_path / "unknown-channels.json"
    path.write_text("{not json")
    channels.record_unknown(path, [game("mlb", "Harbor Sports Net")], NOW)
    assert [e["times_seen"] for e in read(path)] == [1]
