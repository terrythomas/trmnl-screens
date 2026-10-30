import importlib
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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


# From stored records to the payload. NOW is a Friday.
NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 30, 9, 41, tzinfo=NY)


def rec(status="on_the_way", code=None, **fields):
    codes = {"stuck": 1, "out_for_delivery": 4, "delivered": 0, "ready_for_pickup": 3, "on_the_way": 2, "not_shipped": 8}
    base = {"status": status, "code": codes[status] if code is None else code, "description": "Item", "carrier": "UPS",
            "tracking": "TN1", "event": None, "location": None, "expected": None, "expected_end": None, "by": None,
            "last_event_at": None}
    return {**base, **fields}


def at(*args):
    return datetime(*args, tzinfo=NY).isoformat()


def when(record):
    [d] = rules.shown([record], NOW)
    return d["when"]


def test_day_words():
    assert when(rec(expected="2026-10-30")) == "Today"
    assert when(rec(expected="2026-10-31")) == "Tomorrow"
    assert when(rec(expected="2026-11-04")) == "Wed"
    assert when(rec(expected="2026-11-05")) == "Thu"
    assert when(rec(expected="2026-11-06")) == "Nov 6"


@pytest.mark.parametrize("record, expected", [
    (rec("stuck", 1, last_event_at=at(2026, 10, 24, 14, 10)), "No update since Oct 24"),
    (rec("stuck", 6, last_event_at=at(2026, 10, 30, 7, 50)), "Missed delivery · Today"),
    (rec("stuck", 6, last_event_at=at(2026, 10, 29, 16, 0)), "Missed delivery · Yesterday"),
    (rec("stuck", 7, last_event_at=at(2026, 10, 27, 16, 20)), "Carrier problem · Tue"),
    (rec("stuck", 7, last_event_at=at(2026, 10, 20, 16, 20)), "Carrier problem · Oct 20"),
    (rec("stuck", 1), "No updates yet"),
    (rec("delivered", last_event_at=at(2026, 10, 30, 8, 12)), "8:12 AM"),
    (rec("delivered", last_event_at=at(2026, 10, 29, 18, 30)), "Yesterday 6:30 PM"),
    (rec("delivered", last_event_at=at(2026, 10, 28, 22, 0)), "Wed 10:00 PM"),
    (rec("out_for_delivery", by=at(2026, 10, 30, 20, 0)), "Today by 8 PM"),
    (rec("out_for_delivery", by=at(2026, 10, 30, 20, 30)), "Today by 8:30 PM"),
    (rec("out_for_delivery"), "Today"),
    (rec("ready_for_pickup", expected_end="2026-11-06"), "Pick up by Nov 6"),
    (rec("ready_for_pickup"), "Waiting for you"),
    (rec("on_the_way", expected="2026-11-12"), "Nov 12"),
    (rec("on_the_way"), "No estimate yet"),
    (rec("not_shipped"), "No estimate yet"),
])
def test_when_by_status(record, expected):
    assert when(record) == expected


def test_late():
    [d] = rules.shown([rec(expected="2026-10-28")], NOW)
    assert (d["when"], d["late"]) == ("Late · was Wed", True)
    assert when(rec(expected="2026-10-20")) == "Late · was Oct 20"
    [d] = rules.shown([rec("out_for_delivery", by=at(2026, 10, 29, 20, 0))], NOW)
    assert (d["when"], d["late"]) == ("Late · was Thu", True)
    assert when(rec("out_for_delivery", last_event_at=at(2026, 10, 29, 7, 40))) == "Late · was Thu"
    [d] = rules.shown([rec(expected="2026-11-12")], NOW)
    assert "late" not in d


def test_delivered_stays_until_deleted_in_parcel():
    [d] = rules.shown([rec("delivered", last_event_at=at(2026, 10, 20, 8, 12))], NOW)
    assert d["when"] == "Oct 20"  # older than 6 days: the date, as everywhere else
    assert when(rec("delivered", last_event_at=at(2026, 10, 24, 8, 12))) == "Sat 8:12 AM"
    assert when(rec("delivered")) == "Delivered"


def test_action_order():
    records = [rec("not_shipped"), rec("on_the_way"), rec("ready_for_pickup"), rec("delivered"),
               rec("out_for_delivery"), rec("stuck")]
    assert [d["status"] for d in rules.shown(records, NOW)] == list(rules.ORDER)

    coming = [rec(description="no estimate"), rec(description="Nov 12", expected="2026-11-12"),
              rec(description="today", expected="2026-10-30"), rec(description="Nov 4", expected="2026-11-04"),
              rec(description="late", expected="2026-10-28")]
    assert [d["description"] for d in rules.shown(coming, NOW)] == ["late", "today", "Nov 4", "Nov 12", "no estimate"]

    delivered = [rec("delivered", description="older", last_event_at=at(2026, 10, 29, 18, 0)),
                 rec("delivered", description="newer", last_event_at=at(2026, 10, 30, 8, 0))]
    assert [d["description"] for d in rules.shown(delivered, NOW)] == ["newer", "older"]


def test_sub_line_fields():
    stuck, moving = rules.shown([rec("stuck", 1, event="Label created", location="Dayton, OH"),
                                 rec(event="Departed facility", location=None)], NOW)
    assert stuck == {"status": "stuck", "description": "Item", "carrier": "UPS", "when": "No updates yet", "tracking": "TN1"}
    assert moving == {"status": "on_the_way", "description": "Item", "carrier": "UPS", "when": "No estimate yet",
                      "event": "Departed facility"}


def test_headline():
    def d(*statuses):
        return [{"status": s} for s in statuses]
    assert rules.headline(d("out_for_delivery", "delivered", "on_the_way")) == "1 out for delivery · 1 delivered · 1 coming"
    assert rules.headline(d("on_the_way", "not_shipped")) == "2 coming"
    assert rules.headline(d("ready_for_pickup")) == "1 to pick up"
    busy = d("stuck", *["out_for_delivery"] * 3, "delivered", "ready_for_pickup", *["on_the_way"] * 3, *["not_shipped"] * 2)
    assert rules.headline(busy) == "1 stuck · 3 out for delivery · 1 delivered · 1 to pick up · 5 coming"
    assert rules.headline([]) == ""


def test_record_survives_null_fields():
    r = rules.record({"status_code": 2, "tracking_number": "TN1", "description": None, "carrier_code": None,
                      "events": None, "date_expected": None, "timestamp_expected_end": None}, CARRIERS)
    assert (r["description"], r["carrier"], r["event"], r["expected"], r["by"]) == ("TN1", "", None, None, None)
