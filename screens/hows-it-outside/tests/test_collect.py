import importlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent
screen = discover_screens()["hows-it-outside"]
hio = importlib.import_module("trmnl_screens.hows-it-outside.collector")
sources = importlib.import_module("trmnl_screens.hows-it-outside.collector.sources")

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 31, 9, 15, tzinfo=NY)  # Day outlook to 10pm
CONTRACT = {"updated_at", "now", "verdicts", "alerts", "more_alerts", "outlook", "pollen", "air", "sun", "stale",
            "errors"}


@pytest.fixture(autouse=True)
def new_york(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    monkeypatch.setenv("TZ", "America/New_York")
    monkeypatch.delenv("GOOGLE_POLLEN_API_KEY", raising=False)
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def forecast(day=datetime(2026, 10, 31)):
    rows = []
    for i in range(48):
        t = day + timedelta(hours=i)
        rows.append({"time": t.strftime("%Y-%m-%dT%H:%M"), "temp": 50 + i % 24 // 2, "feels": 46 + i % 24 // 2,
                     "precip": 70 if t.hour == 10 else 0, "code": 61 if t.hour == 10 else 3, "uv": 1,
                     "wind": 18, "is_day": int(7 <= t.hour < 18)})
    days = [{"date": (day + timedelta(days=n)).strftime("%Y-%m-%d"), "high": 61, "low": 41,
             "sunrise": (day + timedelta(days=n, hours=7, minutes=27)).strftime("%Y-%m-%dT%H:%M"),
             "sunset": (day + timedelta(days=n, hours=17, minutes=52)).strftime("%Y-%m-%dT%H:%M")} for n in (0, 1)]
    return {"current": {"temp": 48.2, "feels": 43.1, "code": 61, "wind": 18.3, "is_day": 1}, "hours": rows, "days": days}


class FakeMeteo:
    def __init__(self, fail_forecast=False, aqi=42):
        self.fail_forecast, self.aqi = fail_forecast, aqi

    def forecast(self):
        if self.fail_forecast:
            raise sources.SourceError("Open-Meteo returned HTTP 500")
        return forecast()

    def air(self):
        return {"aqi": self.aqi}


class FakeNws:
    def __init__(self, alerts=()):
        self._alerts = list(alerts)

    def alerts(self):
        return self._alerts


class FakePollen:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def today(self):
        self.calls += 1
        if self.fail:
            raise sources.SourceError("Google Pollen returned HTTP 500")
        return {"pollenTypeInfo": [{"code": "TREE", "displayName": "Tree", "indexInfo": {"value": 4}}],
                "plantInfo": [{"code": "OAK", "displayName": "Oak", "indexInfo": {"value": 4}}]}


def run(now=NOW, meteo=None, nws=None, pollen=None):
    return hio.collect(now, meteo or FakeMeteo(), nws or FakeNws(), pollen or FakePollen())


def test_interval_is_15_minutes():
    assert screen.interval_minutes == 15


def test_payload_matches_the_contract():
    payload = run()
    assert set(payload) == {"updated_at", "now", "verdicts", "alerts", "outlook", "pollen", "air", "sun", "errors"}
    assert payload["updated_at"] == "2026-10-31T09:15:00-04:00"
    assert payload["now"] == {"temp": 48, "feels": 43, "conditions": "Light rain", "icon": "rain", "high": 61,
                              "low": 41, "wind": 18}
    assert payload["verdicts"] == {"jacket": "light", "jacket_why": "Feels 51° at 10am", "umbrella": "rain",
                                   "umbrella_why": "70% at 10am", "sunscreen": False, "uv": "UV 1 now"}
    assert payload["outlook"]["kind"] == "day"
    assert payload["outlook"]["hours"][0] == {"time": "10am", "icon": "rain", "temp": 55, "precip": 70}
    assert payload["alerts"] == []
    assert payload["pollen"] == [{"type": "Tree", "level": "High", "plant": "Oak"}]
    assert payload["air"] == {"aqi": 42}
    assert payload["sun"] == [{"kind": "set", "at": "5:52pm"}, {"kind": "rise", "at": "7:27am"}]
    assert payload["errors"] == []


def test_alerts_beyond_three_are_counted():
    onset, ends = NOW - timedelta(hours=1), NOW + timedelta(hours=2)
    nws = FakeNws([{"event": f"Advisory {n}", "severity": "Minor", "onset": onset.isoformat(),
                    "ends": (ends + timedelta(minutes=n)).isoformat()} for n in range(5)])
    payload = run(nws=nws)
    assert [a["event"] for a in payload["alerts"]] == ["Advisory 0", "Advisory 1", "Advisory 2"]
    assert payload["more_alerts"] == 2


def test_pollen_is_fetched_once_a_day():
    pollen = FakePollen()
    run(pollen=pollen)
    run(NOW + timedelta(hours=8), pollen=pollen)
    assert pollen.calls == 1
    run(NOW + timedelta(days=1), pollen=pollen)
    assert pollen.calls == 2


def test_yesterdays_pollen_is_not_shown_when_today_fails():
    run()
    payload = run(NOW + timedelta(days=1), pollen=FakePollen(fail=True))
    assert "pollen" not in payload
    assert [e["source"] for e in payload["errors"]] == ["google-pollen"]


def test_a_missing_pollen_key_is_reported_apart():
    payload = hio.collect(NOW, FakeMeteo(), FakeNws())
    assert [e["source"] for e in payload["errors"]] == ["google-pollen-key"]
    assert "pollen" not in payload and payload["now"]["temp"] == 48


def test_a_failing_forecast_under_3_hours_is_worked_out_again_from_its_hours():
    run()
    payload = run(NOW + timedelta(hours=2, minutes=59), FakeMeteo(fail_forecast=True))
    assert payload["now"]["temp"] == 56  # the stored 12pm hour, no longer the 9:15 reading
    assert payload["outlook"]["kind"] == "rolling" and payload["outlook"]["hours"][0]["time"] == "1pm"
    assert payload["stale"] == ["forecast"]
    assert payload["errors"] == [{"source": "open-meteo", "since": "2026-10-31T12:14:00-04:00"}]


def test_a_forecast_failing_for_3_hours_says_since_when():
    run()
    failing = FakeMeteo(fail_forecast=True)
    run(NOW + timedelta(minutes=15), failing)
    payload = run(NOW + timedelta(hours=3, minutes=15), failing)
    assert payload["now"] == {"missing_since": "9:30am"}
    assert not {"verdicts", "outlook", "sun"} & set(payload)
    assert payload["air"] == {"aqi": 42}


def test_no_forecast_ever_says_since_when():
    payload = run(meteo=FakeMeteo(fail_forecast=True))
    assert payload["now"] == {"missing_since": "9:15am"}


@pytest.mark.parametrize("fixture", sorted((SCREEN / "fixtures").glob("*.json")), ids=lambda p: p.stem)
def test_every_fixture_matches_the_contract(fixture):
    payload = json.loads(fixture.read_text())
    assert set(payload) <= CONTRACT | {"preview_now"}
    assert {e["source"] for e in payload["errors"]} <= {"open-meteo", "open-meteo-air", "nws", "google-pollen",
                                                        "google-pollen-key"}
    assert len(payload.get("alerts", [])) <= 3
    assert ("verdicts" in payload) == ("missing_since" not in payload["now"])
