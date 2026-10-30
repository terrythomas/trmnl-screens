import importlib
import time

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
rules = importlib.import_module("trmnl_screens.wheres-my-stuff.collector.rules")

CARRIERS = {"ups": "UPS", "usps": "USPS"}


@pytest.fixture(autouse=True)
def new_york(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def raw(**fields):
    return {"status_code": 2, "tracking_number": "TN1", **fields}


def test_status_codes():
    expected = {0: "delivered", 1: "stuck", 6: "stuck", 7: "stuck", 2: "on_the_way", 3: "ready_for_pickup",
                4: "out_for_delivery", 5: "not_shipped", 8: "not_shipped", 42: "on_the_way"}
    for code, status in expected.items():
        r = rules.record(raw(status_code=code), CARRIERS)
        assert (r["status"], r["code"]) == (status, code)


def test_record_reads_dates():
    r = rules.record(raw(date_expected="2026-11-04 12:00:00", date_expected_end="2026-11-06 18:00:00",
                         timestamp_expected_end=1793404800,  # 2026-10-30 20:00 in New York
                         events=[{"event": "Arrived", "date": "October 30, 2026 08:12"},
                                 {"event": "Departed", "date": "October 29, 2026 22:00"}]), CARRIERS)
    assert r["expected"] == "2026-11-04"
    assert r["expected_end"] == "2026-11-06"
    assert r["by"] == "2026-10-30T20:00:00-04:00"
    assert r["last_event_at"] == "2026-10-30T08:12:00-04:00"


def test_record_carrier_name_or_code():
    assert rules.record(raw(carrier_code="ups"), CARRIERS)["carrier"] == "UPS"
    assert rules.record(raw(carrier_code="zz"), CARRIERS)["carrier"] == "ZZ"


def test_record_minimal_delivery():
    r = rules.record({"status_code": 2, "tracking_number": "TN1"}, CARRIERS)
    assert r["description"] == "TN1"
    assert r["carrier"] == ""
    assert r["tracking"] == "TN1"
    for key in ("event", "location", "expected", "expected_end", "by", "last_event_at"):
        assert r[key] is None


def test_record_strips_emoji():
    assert rules.record(raw(description="Socks 🧦 & sandals"), CARRIERS)["description"] == "Socks & sandals"
    assert rules.record(raw(description="🧦"), CARRIERS)["description"] == "TN1"


def test_record_unparseable_event_date():
    r = rules.record(raw(events=[{"event": "Departed facility", "date": "30 Oct 2026 22:27"}]), CARRIERS)
    assert r["last_event_at"] is None
    assert r["event"] == "Departed facility"


@pytest.mark.parametrize("code, event, kept", [
    (0, "Delivered, front door", "front door"),
    (4, "Out for delivery", None),
    (0, "DELIVERED - mailbox", "mailbox"),
    (2, "Departed facility", "Departed facility"),
])
def test_event_repeating_status_is_trimmed(code, event, kept):
    r = rules.record(raw(status_code=code, events=[{"event": event, "date": "October 30, 2026 08:12", "location": "Dayton, OH"}]), CARRIERS)
    assert r["event"] == kept
    assert r["location"] == "Dayton, OH"
