import importlib
import json
from datetime import datetime
from pathlib import Path

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent

screen = discover_screens()["game-time"]
game_time = importlib.import_module("trmnl_screens.game-time.collector")


class EmptyEspn:
    def scoreboard(self, league, day):
        return []


def test_collect_builds_the_payload_from_the_followed_teams(monkeypatch):
    monkeypatch.setenv("GAME_TIME_TEAMS", "nba:hbr")
    monkeypatch.setattr(game_time, "EspnSource", EmptyEspn)
    payload = screen.collect()
    assert datetime.fromisoformat(payload["updated_at"]).utcoffset() is not None
    assert payload | {"updated_at": None} == {
        "updated_at": None, "games": [], "errors": [],
        "logos": {}, "logos1": {}, "logos1h": {}, "icons": {}, "icons1": {}, "icons1h": {},
    }


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
