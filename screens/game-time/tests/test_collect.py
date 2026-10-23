import importlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent

screen = discover_screens()["game-time"]
game_time = importlib.import_module("trmnl_screens.game-time.collector")
espn = importlib.import_module("trmnl_screens.game-time.collector.sources.espn")


class EmptyEspn:
    def scoreboard(self, league, day):
        return []

    def teams(self, league):
        return {"HBR", "MSA"}


@pytest.fixture(autouse=True)
def state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    return tmp_path


def test_collect_builds_the_payload_from_the_followed_teams(monkeypatch, tmp_path):
    monkeypatch.setenv("GAME_TIME_TEAMS", "nba:hbr")
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    monkeypatch.setattr(game_time, "EspnSource", EmptyEspn)
    payload = screen.collect()
    assert datetime.fromisoformat(payload["updated_at"]).utcoffset() is not None
    assert payload | {"updated_at": None} == {
        "updated_at": None, "games": [], "errors": [],
        "logos": {}, "logos1": {}, "logos1h": {}, "icons": {}, "icons1": {}, "icons1h": {},
    }
    assert json.loads((tmp_path / "game-time" / "unknown-channels.json").read_text()) == []


def test_runs_hourly_by_default():
    assert screen.interval_minutes == 60


def test_fixtures_match_the_payload_contract():
    sample = json.loads((SCREEN / "fixtures" / "sample.json").read_text())
    game_keys = set(sample["games"][0])
    for fixture in (SCREEN / "fixtures").glob("*.json"):
        payload = json.loads(fixture.read_text())
        assert {"updated_at", "games", "errors", "logos", "icons"} <= payload.keys(), fixture.name
        for g in payload["games"]:
            assert g.keys() == game_keys, fixture.name
            assert g["followed"].keys() == g["opponent"].keys() == {"abbr", "name", "logo", "score", "home"}
            # Fixtures are invented: no logos or icons, ever (ADR-0009).
            assert g["followed"]["logo"] is None and g["opponent"]["logo"] is None, fixture.name


NOW = "2026-10-23T19:00:00-04:00"


def payload(*games):
    return {"updated_at": NOW, "games": [{"start": start, "state": state} for start, state in games]}


def test_runs_every_5_minutes_from_5_minutes_before_a_start():
    assert screen.next_run_minutes(payload(("2026-10-23T19:05:00-04:00", "scheduled"))) == 5
    assert screen.next_run_minutes(payload(("2026-10-23T19:06:00-04:00", "scheduled"))) is None


def test_runs_every_5_minutes_while_a_game_is_live():
    assert screen.next_run_minutes(payload(("2026-10-23T18:00:00-04:00", "live"))) == 5


def test_keeps_the_interval_after_the_final():
    assert screen.next_run_minutes(payload(("2026-10-23T16:00:00-04:00", "final"))) is None


def test_keeps_the_interval_with_no_games():
    assert screen.next_run_minutes(payload()) is None


class TonightEspn(EmptyEspn):
    """One HBR game at the hour, on every day's scoreboard; down when `down` is set."""
    down = False

    def scoreboard(self, league, day):
        if self.down:
            raise espn.EspnError("ESPN returned HTTP 503")
        start = datetime.now().astimezone().replace(minute=0, second=0, microsecond=0)
        team = lambda abbr, home: espn.EspnTeam(abbr, abbr.title(), None, 0, home)
        return [espn.EspnGame("1", start, "STATUS_SCHEDULED", "pre", "", team("HBR", True), team("MSA", False), ())]


def test_a_failing_league_keeps_its_last_good_games_marked_stale(monkeypatch):
    monkeypatch.setenv("GAME_TIME_TEAMS", "nba:hbr")
    monkeypatch.setattr(game_time, "EspnSource", TonightEspn)
    fresh = screen.collect()
    assert [g["stale"] for g in fresh["games"]] == [False]

    monkeypatch.setattr(TonightEspn, "down", True)
    first, second = screen.collect(), screen.collect()

    assert [g["stale"] for g in second["games"]] == [True]
    assert second["games"][0] | {"stale": False} == fresh["games"][0]
    # since is the first failure, kept while the league stays down
    assert second["errors"] == first["errors"] == [{"source": "espn-nba", "since": first["updated_at"]}]


def test_a_recovered_league_clears_its_banner_entry(monkeypatch):
    monkeypatch.setenv("GAME_TIME_TEAMS", "nba:hbr")
    monkeypatch.setattr(game_time, "EspnSource", TonightEspn)
    monkeypatch.setattr(TonightEspn, "down", True)
    assert screen.collect()["errors"] != []

    monkeypatch.setattr(TonightEspn, "down", False)
    payload = screen.collect()

    assert payload["errors"] == []
    assert [g["stale"] for g in payload["games"]] == [False]


def test_an_unknown_team_is_reported_and_the_others_keep_working(monkeypatch):
    monkeypatch.setenv("GAME_TIME_TEAMS", "nba:hbr, NBA:Xyz")
    monkeypatch.setattr(game_time, "EspnSource", TonightEspn)
    payload = screen.collect()

    assert [g["followed"]["abbr"] for g in payload["games"]] == ["HBR"]
    assert payload["errors"] == [{"source": "unknown-team:nba:xyz", "since": payload["updated_at"]}]


class CountingEspn(TonightEspn):
    """Counts team-list requests; fails them when `teams_down` is set."""
    teams_asked = 0
    teams_down = False

    def teams(self, league):
        type(self).teams_asked += 1
        if self.teams_down:
            raise espn.EspnError("ESPN returned HTTP 503")
        return super().teams(league)


@pytest.fixture
def counting(monkeypatch):
    monkeypatch.setenv("GAME_TIME_TEAMS", "nba:hbr")
    monkeypatch.setattr(game_time, "EspnSource", CountingEspn)
    monkeypatch.setattr(CountingEspn, "teams_asked", 0)
    return CountingEspn


def cache_teams(state_dir, age, teams):
    fetched = (datetime.now().astimezone() - age).isoformat(timespec="seconds")
    path = state_dir / "game-time" / "teams.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"nba": {"fetched": fetched, "teams": teams}}))


def test_a_fresh_team_list_is_read_from_the_cache(counting):
    screen.collect()
    payload = screen.collect()
    assert counting.teams_asked == 1
    assert payload["errors"] == []


def test_an_expired_team_list_is_fetched_again(counting, state_dir):
    cache_teams(state_dir, timedelta(days=1, minutes=1), ["MSA"])
    payload = screen.collect()
    assert counting.teams_asked == 1
    assert payload["errors"] == []  # the new list has HBR
    assert sorted(json.loads((state_dir / "game-time" / "teams.json").read_text())["nba"]["teams"]) == ["HBR", "MSA"]


def test_a_failed_refresh_keeps_using_the_cached_team_list(counting, state_dir, monkeypatch):
    cache_teams(state_dir, timedelta(days=3), ["HBR"])
    monkeypatch.setattr(CountingEspn, "teams_down", True)
    payload = screen.collect()
    assert counting.teams_asked == 1
    assert payload["errors"] == []
    assert [g["stale"] for g in payload["games"]] == [False]


def test_a_failed_refresh_with_no_cache_reports_the_league_down(counting, monkeypatch):
    monkeypatch.setattr(CountingEspn, "teams_down", True)
    # ESPN being down doesn't make the team unknown
    assert [e["source"] for e in screen.collect()["errors"]] == ["espn-nba"]
