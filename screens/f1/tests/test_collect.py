import importlib
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent
RECORDINGS = SCREEN / "tests" / "recordings"
SEASON = json.loads((RECORDINGS / "jolpica_current.json").read_text())
EMPTY = json.loads((RECORDINGS / "jolpica_empty_season.json").read_text())


def next_season():
    """The recording's first two Grands Prix moved a year on, standing in for a published 2027 season."""
    body = json.loads(json.dumps(SEASON))
    table = body["MRData"]["RaceTable"]
    table["season"], table["Races"] = "2027", table["Races"][:2]
    for race in table["Races"]:
        race["season"] = "2027"
        for entry in [race, *(v for v in race.values() if isinstance(v, dict) and "date" in v)]:
            entry["date"] = entry["date"].replace("2026", "2027")
    return body

screen = discover_screens()["f1"]
f1 = importlib.import_module("trmnl_screens.f1.collector")
jolpica = importlib.import_module("trmnl_screens.f1.collector.sources.jolpica")
outlines = importlib.import_module("trmnl_screens.f1.collector.outlines")
fit = importlib.import_module("trmnl_screens.f1.collector.fit")

NY = ZoneInfo("America/New_York")
MONDAY = datetime(2026, 10, 26, 9, 0, tzinfo=NY)


@pytest.fixture(autouse=True)
def new_york(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def serve(monkeypatch, current, following=None):
    """Answer /current.json with `current` and /2027.json with `following`; return the paths asked for."""
    asked = []

    def handler(request):
        asked.append(request.url.path)
        return current if request.url.path.endswith("/current.json") else following

    monkeypatch.setattr(f1, "JolpicaSource", lambda: jolpica.JolpicaSource(transport=httpx.MockTransport(handler)))
    return asked


@pytest.fixture
def drawn(monkeypatch):
    """Outlines drawn from an invented line (ADR-0010), except Interlagos's, which fails to download.
    Returns the (circuit, season) pairs asked for."""
    asked = []

    def outline(self, circuit, lat, lon, year, name, location, now=None):
        asked.append((circuit, year))
        if circuit == "interlagos":
            return None
        return {"d": circuit, "name": name, "location": location}

    monkeypatch.setattr(outlines.OutlineStore, "outline", outline)
    return asked


def test_collect_builds_the_payload_from_the_season(monkeypatch, drawn):
    serve(monkeypatch, httpx.Response(200, json=SEASON))
    payload = screen.collect(MONDAY)

    assert payload["updated_at"] == "2026-10-26T09:00:00-04:00"
    assert payload["errors"] == []
    mexico = payload["grands_prix"][0]
    assert mexico == {
        "round": 19, "name": "Mexico City Grand Prix", "location": "Mexico City, Mexico", "circuit": "rodriguez",
        "sessions": [
            {"kind": "practice_1", "name": "Practice 1", "start": "2026-10-30T14:30:00-04:00",
             "end": "2026-10-30T15:30:00-04:00", "local_date": "2026-10-30"},
            {"kind": "practice_2", "name": "Practice 2", "start": "2026-10-30T18:00:00-04:00",
             "end": "2026-10-30T19:00:00-04:00", "local_date": "2026-10-30"},
            {"kind": "practice_3", "name": "Practice 3", "start": "2026-10-31T13:30:00-04:00",
             "end": "2026-10-31T14:30:00-04:00", "local_date": "2026-10-31"},
            {"kind": "qualifying", "name": "Qualifying", "start": "2026-10-31T17:00:00-04:00",
             "end": "2026-10-31T18:00:00-04:00", "local_date": "2026-10-31"},
            # Clocks go back on November 1.
            {"kind": "race", "name": "Race", "start": "2026-11-01T15:00:00-05:00",
             "end": "2026-11-01T17:00:00-05:00", "local_date": "2026-11-01"},
        ],
    }


def test_at_most_three_grands_prix_from_the_one_with_a_session_today_or_later(monkeypatch, drawn):
    serve(monkeypatch, httpx.Response(200, json=SEASON))
    rounds = lambda now: [gp["round"] for gp in screen.collect(now)["grands_prix"]]
    # The US Grand Prix's race is on the evening of the 25th, so it stays until that day ends.
    assert rounds(datetime(2026, 10, 25, 23, 59, tzinfo=NY)) == [18, 19, 20]
    assert rounds(MONDAY) == [19, 20, 21]


def test_three_left_in_the_season_needs_no_next_season(monkeypatch, drawn):
    asked = serve(monkeypatch, httpx.Response(200, json=SEASON))
    screen.collect(MONDAY)
    assert asked == ["/ergast/f1/current.json"]


def test_the_next_season_fills_in_when_fewer_than_three_are_left(monkeypatch, drawn):
    asked = serve(monkeypatch, httpx.Response(200, json=SEASON), httpx.Response(200, json=next_season()))
    payload = screen.collect(datetime(2026, 11, 10, 9, 0, tzinfo=NY))

    assert asked == ["/ergast/f1/current.json", "/ergast/f1/2027.json"]
    assert [(gp["round"], gp["sessions"][-1]["local_date"]) for gp in payload["grands_prix"]] == [
        (21, "2026-11-21"), (17, "2027-10-11"), (18, "2027-10-25")]
    # Each outline is looked up in its own Grand Prix's season.
    assert drawn == [("vegas", 2026), ("marina_bay", 2027), ("americas", 2027)]


def test_an_unpublished_next_season_is_not_an_error(monkeypatch, drawn):
    serve(monkeypatch, httpx.Response(200, json=SEASON), httpx.Response(200, json=EMPTY))
    payload = screen.collect(datetime(2026, 11, 10, 9, 0, tzinfo=NY))
    assert [gp["round"] for gp in payload["grands_prix"]] == [21]
    assert payload["errors"] == []


def test_a_failed_next_season_only_logs(monkeypatch, drawn, caplog):
    serve(monkeypatch, httpx.Response(200, json=SEASON), httpx.Response(503))
    payload = screen.collect(datetime(2026, 11, 10, 9, 0, tzinfo=NY))
    assert [gp["round"] for gp in payload["grands_prix"]] == [21]
    assert payload["errors"] == []
    assert "next season skipped: Jolpica returned HTTP 503" in caplog.text


def test_a_session_belongs_to_the_local_day_it_starts_on(monkeypatch, drawn):
    serve(monkeypatch, httpx.Response(200, json=SEASON))
    vegas = screen.collect(MONDAY)["grands_prix"][2]
    first = vegas["sessions"][0]
    assert (first["start"], first["local_date"]) == ("2026-11-19T19:30:00-05:00", "2026-11-19")


def test_outlines_hold_only_the_shown_circuits_that_were_drawn(monkeypatch, drawn):
    serve(monkeypatch, httpx.Response(200, json=SEASON))
    payload = screen.collect(MONDAY)
    # Each is laid out for its own Grand Prix's name and location.
    assert payload["outlines"] == {
        "rodriguez": {"d": "rodriguez", "name": "Mexico City Grand Prix", "location": "Mexico City, Mexico"},
        "vegas": {"d": "vegas", "name": "Las Vegas Grand Prix", "location": "Las Vegas, USA"}}
    assert payload["errors"] == []  # a missing outline never raises the banner


def test_a_failing_schedule_keeps_the_last_good_one_with_the_banner(monkeypatch, drawn):
    serve(monkeypatch, httpx.Response(200, json=SEASON))
    fresh = screen.collect(MONDAY)

    serve(monkeypatch, httpx.Response(503))
    first = screen.collect(datetime(2026, 10, 26, 10, 0, tzinfo=NY))
    second = screen.collect(datetime(2026, 11, 2, 10, 0, tzinfo=NY))

    assert first["grands_prix"] == fresh["grands_prix"]
    # The last good schedule is still filtered by the day, so a long outage moves on to later Grands Prix.
    assert [gp["round"] for gp in second["grands_prix"]] == [20, 21]
    assert second["errors"] == first["errors"] == [{"source": "schedule", "since": "2026-10-26T10:00:00-04:00"}]


def test_runs_hourly_by_default():
    assert screen.interval_minutes == 60


def test_fixtures_match_the_payload_contract():
    for fixture in (SCREEN / "fixtures").glob("*.json"):
        payload = json.loads(fixture.read_text())
        assert {"updated_at", "grands_prix", "outlines", "errors"} <= payload.keys(), fixture.name
        for gp in payload["grands_prix"]:
            assert gp.keys() == {"round", "name", "location", "circuit", "sessions"}, fixture.name
            for s in gp["sessions"]:
                assert s.keys() == {"kind", "name", "start", "end", "local_date"}, fixture.name
                assert s["kind"] in jolpica.SESSIONS.values() or s["kind"] == "race", fixture.name
        assert set(payload["outlines"]) <= {gp["circuit"] for gp in payload["grands_prix"]}, fixture.name
        for outline in payload["outlines"].values():
            assert outline.keys() == {"d", "w", "h", "angle", "x", "og"}, fixture.name
            assert -fit.MAX_TURN <= outline["angle"] <= fit.MAX_TURN, fixture.name
            for dev in ("x", "og"):
                assert outline[dev].keys() == {"width", "north"}, fixture.name
