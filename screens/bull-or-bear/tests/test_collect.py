import importlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from collector.discovery import discover_screens

screen = discover_screens()["bull-or-bear"]
pkg = importlib.import_module("trmnl_screens.bull-or-bear.collector")
SourceError = importlib.import_module("trmnl_screens.bull-or-bear.collector.sources").SourceError
FinnhubKeyError = importlib.import_module("trmnl_screens.bull-or-bear.collector.sources.finnhub").FinnhubKeyError

NY = ZoneInfo("America/New_York")
TUE = date(2026, 11, 24)


def at(hour, minute=0, day=24):
    return datetime(2026, 11, day, hour, minute, tzinfo=NY)


def zigzag(n=252, step=0.01):
    closes = [100.0]
    for i in range(n - 1):
        closes.append(closes[-1] * (1 + (step if i % 2 == 0 else -step)))
    return closes


class Yahoo:
    def __init__(self, move=0.0, after=None, fail=False):
        self.move, self.after, self.fail, self.calls = move, after, fail, 0

    def quote(self, symbol):
        self.calls += 1
        if self.fail:
            raise SourceError("Yahoo returned HTTP 429")
        closes = zigzag()
        days = [[(TUE - timedelta(days=len(closes) - i)).isoformat(), c] for i, c in enumerate(closes)]
        price = closes[-1] * (1 + self.move)
        q = {"name": "Example Corp", "days": days, "price": price, "price_time": int(at(14, 45).timestamp())}
        if self.after:
            q |= {"after": price * (1 + self.after), "after_time": int(at(18, 30).timestamp())}
        return q


class Finnhub:
    def __init__(self, earnings=(), fail=None):
        self.items, self.fail, self.calls = list(earnings), fail, 0

    def earnings(self, symbol, today):
        self.calls += 1
        if self.fail:
            raise self.fail
        return self.items


class Nasdaq:
    def __init__(self, dividends=()):
        self.items = list(dividends)

    def dividends(self, symbol):
        return self.items


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))


def run(now=None, yahoo=None, finnhub=None, nasdaq=None, instance="exmp"):
    return pkg.collect(instance, now or at(14, 45), yahoo or Yahoo(), finnhub or Finnhub(), nasdaq or Nasdaq())


def test_outside_the_market_window_nothing_is_fetched():
    yahoo = Yahoo()
    assert run(at(21), yahoo) == {"symbol": "EXMP", "show": False}
    assert run(at(12, day=26), yahoo)["show"] is False  # Thanksgiving
    assert yahoo.calls == 0


def test_a_quiet_day_stays_hidden():
    p = run()
    assert p["show"] is False and p["lead"] == {"kind": "none"}


def test_a_big_day_leads_with_todays_change():
    p = run(yahoo=Yahoo(move=-0.03))
    assert p["show"] and p["lead"] == {"kind": "day", "label": "Today", "value": "−3.0%", "dir": "down"}
    assert [c["label"] for c in p["changes"]] == ["Prev close", "30 days", "1 year"]
    assert p["as_of"] == "2:45 PM" and p["visible_until"] == int(at(20).timestamp())


def test_after_hours_on_an_earnings_night():
    p = run(at(18, 30), Yahoo(move=0.005, after=-0.05), Finnhub([{"date": "2026-11-24", "hour": "amc"}]))
    assert p["lead"]["kind"] == "after_hours" and p["badge"] == "Earnings after close"
    assert p["close_line"].startswith("Close $") and p["after_line"].endswith("(−5.0%)")
    assert p["as_of"] == "6:30 PM"


def test_earnings_day_without_a_move_leads_with_the_badge():
    p = run(finnhub=Finnhub([{"date": "2026-11-24", "hour": "bmo"}]))
    assert p["show"] and p["lead"] == {"kind": "badge", "label": "Earnings before open"}


def test_a_pay_date_shows_the_stock():
    p = run(nasdaq=Nasdaq([{"pay": "2026-11-24", "amount": 0.27}]))
    assert p["lead"]["label"] == "Dividend paid today" and p["dividend"] == "Paid $0.27 a share today"


def test_earnings_are_fetched_once_a_day():
    finnhub = Finnhub()
    run(finnhub=finnhub)
    run(at(15), finnhub=finnhub)
    assert finnhub.calls == 1


def test_a_missing_finnhub_key_is_named_but_never_marks_the_screen_stale():
    p = run(yahoo=Yahoo(move=-0.03), finnhub=Finnhub(fail=FinnhubKeyError("FINNHUB_API_KEY is not set")))
    assert p["show"] and "stale" not in p
    assert [e["label"] for e in p["errors"]] == ["Earnings off: Finnhub key missing or rejected"]


def test_when_yahoo_fails_the_last_quote_is_shown_stale():
    run(yahoo=Yahoo(move=-0.03))
    p = run(at(15), Yahoo(fail=True))
    assert p["stale"] and p["show"]
    assert p["errors"][0]["label"] == "Prices down since 3:00 PM"


def test_per_stock_multiples(monkeypatch):
    assert run(yahoo=Yahoo(move=-0.03))["lead"]["kind"] == "day"
    monkeypatch.setenv("BULL_OR_BEAR_EXMP_DAY_MULTIPLE", "4")
    monkeypatch.setenv("BULL_OR_BEAR_EXMP_THIRTY_MULTIPLE", "10")
    assert run(at(15), Yahoo(move=-0.03))["show"] is False


def test_the_screen_needs_an_instance():
    with pytest.raises(SourceError):
        pkg.collect(None, at(14, 45))


def test_it_asks_to_wake_for_the_next_open(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at(9, 20).astimezone(tz)

    monkeypatch.setattr(pkg, "datetime", Clock)
    assert pkg.next_run_minutes({}) == pytest.approx(10.5)
