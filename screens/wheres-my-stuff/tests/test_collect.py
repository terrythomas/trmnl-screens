import importlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent
screen = discover_screens()["wheres-my-stuff"]
wms = importlib.import_module("trmnl_screens.wheres-my-stuff.collector")
parcel = importlib.import_module("trmnl_screens.wheres-my-stuff.collector.sources.parcel")
rules = importlib.import_module("trmnl_screens.wheres-my-stuff.collector.rules")

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 30, 9, 41, tzinfo=NY)
CONTRACT = {"updated_at", "headline", "deliveries", "errors", "stale"}
TICKET = {"status", "description", "carrier", "when", "event", "location", "tracking", "late"}


@pytest.fixture(autouse=True)
def new_york(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    monkeypatch.setenv("TZ", "America/New_York")
    monkeypatch.delenv("PARCEL_API_KEY", raising=False)
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


class FakeParcel:
    def __init__(self, deliveries=(), carriers=None, fail=False):
        self._deliveries, self._carriers, self.fail = list(deliveries), carriers, fail
        self.carrier_calls = 0

    def deliveries(self):
        if self.fail:
            raise parcel.ParcelError("Parcel returned HTTP 500")
        return self._deliveries

    def carriers(self):
        self.carrier_calls += 1
        if self._carriers is None:
            raise parcel.ParcelError("Parcel returned HTTP 500")
        return self._carriers


def out_for_delivery(**fields):
    return {"carrier_code": "amzlus", "description": "Coffee beans", "status_code": 4, "tracking_number": "TBA1",
            "events": [{"event": "Out for delivery", "date": "October 30, 2026 07:40", "location": "Dayton, OH"}],
            "timestamp_expected_end": 1793404800, **fields}  # 2026-10-30 20:00 in New York


def test_interval_is_15_minutes():
    assert screen.interval_minutes == 15


def test_payload_matches_the_contract():
    payload = wms.collect(NOW, FakeParcel([out_for_delivery()], {"amzlus": "Amazon"}))
    assert set(payload) == {"updated_at", "headline", "deliveries", "errors"}
    assert payload["updated_at"] == "2026-10-30T09:41:00-04:00"
    assert payload["headline"] == "1 out for delivery"
    assert payload["errors"] == []
    [ticket] = payload["deliveries"]
    assert ticket == {"status": "out_for_delivery", "description": "Coffee beans", "carrier": "Amazon",
                      "when": "Today by 8 PM", "location": "Dayton, OH"}


@pytest.mark.parametrize("fixture", sorted((SCREEN / "fixtures").glob("*.json")), ids=lambda p: p.stem)
def test_every_fixture_matches_the_contract(fixture):
    payload = json.loads(fixture.read_text())
    assert set(payload) <= CONTRACT | {"preview_now"}
    statuses = [d["status"] for d in payload["deliveries"]]
    assert all(set(d) <= TICKET for d in payload["deliveries"])
    assert statuses == sorted(statuses, key=rules.ORDER.index)
    assert {e["source"] for e in payload["errors"]} <= {"parcel", "parcel-key"}
    assert payload["headline"] == rules.headline(payload["deliveries"])
    assert not payload.get("stale") or payload["deliveries"]


def test_parcel_failure_goes_stale_and_relabels():
    wms.collect(NOW, FakeParcel([out_for_delivery()], {"amzlus": "Amazon"}))
    tomorrow = NOW + timedelta(days=1)
    payload = wms.collect(tomorrow, FakeParcel(fail=True, carriers={"amzlus": "Amazon"}))
    assert payload["stale"] is True
    assert payload["errors"] == [{"source": "parcel", "since": "2026-10-31T09:41:00-04:00"}]
    [ticket] = payload["deliveries"]
    assert (ticket["when"], ticket["late"]) == ("Late · was Fri", True)


def test_no_deliveries():
    payload = wms.collect(NOW, FakeParcel([], {}))
    assert payload["deliveries"] == []
    assert payload["headline"] == ""
    assert "stale" not in payload


def test_carrier_list_cached_and_optional():
    source = FakeParcel([out_for_delivery()], {"amzlus": "Amazon"})
    wms.collect(NOW, source)
    wms.collect(NOW + timedelta(hours=1), source)
    assert source.carrier_calls == 1


def test_carrier_list_failure_shows_the_code():
    payload = wms.collect(NOW, FakeParcel([out_for_delivery()], carriers=None))
    assert payload["deliveries"][0]["carrier"] == "AMZLUS"
    assert payload["errors"] == []


def test_missing_key_is_an_error_not_a_crash():
    payload = wms.collect(NOW)
    assert payload["errors"][0]["source"] == "parcel-key"
    assert payload["deliveries"] == []


def test_unknown_status_code_is_logged_once_per_run(caplog):
    unknown = [out_for_delivery(status_code=42, tracking_number="A"), out_for_delivery(status_code=42, tracking_number="B")]
    with caplog.at_level("WARNING"):
        payload = wms.collect(NOW, FakeParcel(unknown, {}))
    assert [d["status"] for d in payload["deliveries"]] == ["on_the_way", "on_the_way"]
    assert [r.getMessage() for r in caplog.records if "status code" in r.getMessage()] == ["unknown Parcel status code 42, shown as On the way"]
