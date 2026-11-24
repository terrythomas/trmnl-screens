import importlib
from datetime import date, timedelta

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
rules = importlib.import_module("trmnl_screens.bull-or-bear.collector.rules")

TODAY = date(2026, 11, 24)


def zigzag(n=252, step=0.01, start=100.0):
    """Closes that alternate ±step a day: daily volatility is exactly `step`, and there is no trend."""
    closes = [start]
    for i in range(n - 1):
        closes.append(closes[-1] * (1 + (step if i % 2 == 0 else -step)))
    return closes


def test_volatility_is_the_spread_of_daily_changes():
    assert rules.volatility(zigzag(step=0.02)) == pytest.approx(0.02, rel=0.01)


@pytest.mark.parametrize("move,big", [(0.014, False), (0.016, True), (-0.016, True)])
def test_a_day_is_big_past_one_and_a_half_times_volatility(move, big):
    history = zigzag(step=0.01)
    m = rules.moves(history, history[-1] * (1 + move), None)
    assert m.big_day is big
    assert m.day == pytest.approx(move)


def test_the_multiples_can_be_changed_per_stock():
    history = zigzag(step=0.01)
    assert rules.moves(history, history[-1] * 1.016, None, day_multiple=2).big_day is False


def test_after_hours_is_measured_from_todays_price():
    history = zigzag(step=0.01)
    price = history[-1] * 1.005
    m = rules.moves(history, price, price * 0.98)
    assert (m.big_day, m.big_after) == (False, True)
    assert m.after == pytest.approx(-0.02)


def test_a_steady_slide_is_a_big_thirty_day_move():
    history = zigzag(step=0.01)[:-30] + [100 * 0.995 ** i for i in range(30)]
    m = rules.moves(history, history[-1] * 0.995, None)
    assert m.big_thirty and not m.big_day


def test_the_lead_prefers_after_hours_then_today_then_thirty_days():
    m = rules.Moves(0.05, -0.08, 0.3, 0.1, True, True, True)
    assert rules.lead(m, None, False)["kind"] == "after_hours"
    assert rules.lead(m.__class__(0.05, None, 0.3, 0.1, True, False, True), None, False) == {
        "kind": "day", "label": "Today", "value": "+5.0%", "dir": "up"}


def test_without_a_big_move_earnings_then_a_pay_date_lead_and_otherwise_nothing():
    quiet = rules.Moves(0.001, None, 0.01, 0.1, False, False, False)
    assert rules.lead(quiet, "Earnings after close", True)["label"] == "Earnings after close"
    assert rules.lead(quiet, None, True)["label"] == "Dividend paid today"
    assert rules.lead(quiet, None, False) is None


def test_earnings_labels_follow_the_time_of_day():
    assert rules.earnings_label([{"date": "2026-11-24", "hour": "amc"}], TODAY) == "Earnings after close"
    assert rules.earnings_label([{"date": "2026-11-24", "hour": "bmo"}], TODAY) == "Earnings before open"
    assert rules.earnings_label([{"date": "2026-11-24", "hour": ""}], TODAY) == "Earnings today"
    assert rules.earnings_label([{"date": "2026-11-25", "hour": "amc"}], TODAY) is None


def test_a_dividend_shows_on_its_pay_date_or_within_a_week():
    assert rules.dividend_line([{"pay": "2026-11-24", "amount": 0.27}], TODAY) == (True, "Paid $0.27 a share today")
    assert rules.dividend_line([{"pay": "2026-12-01", "amount": 0.27}], TODAY) == (False, "Pays $0.27 · Dec 1")
    assert rules.dividend_line([{"pay": "2026-12-02", "amount": 0.27}], TODAY) == (False, None)


def test_the_row_leaves_out_what_the_lead_shows():
    history = zigzag()
    m = rules.moves(history, history[-1], None)
    labels = lambda kind: [c["label"] for c in rules.change_row(m, history, history[-1], kind)]
    assert labels(None) == ["Prev close", "Today", "30 days", "1 year"]
    assert labels("day") == labels("after_hours") == ["Prev close", "30 days", "1 year"]
    assert labels("thirty") == ["Prev close", "Today", "1 year"]


def test_the_chart_gives_the_last_thirty_days_the_right_third():
    closes = zigzag()
    days = [TODAY - timedelta(days=len(closes) - 1 - i) for i in range(len(closes))]
    c = rules.chart(days, closes)
    xs = [float(p.split(",")[0]) for p in c["line"].split()]
    assert xs[0] == 0 and xs[-1] == 1000 and xs[-22] == rules.YEAR_SHARE
    assert len(c["recent"].split()) == 22
    assert c["high"]["label"].startswith("High $") and c["low"]["label"].startswith("Low $")


def test_formatting_uses_a_real_minus_sign():
    assert rules.pct(-0.0789) == "−7.9%"
    assert rules.pct(0.023) == "+2.3%"
    assert rules.money(1234.5) == "$1,234.50"
