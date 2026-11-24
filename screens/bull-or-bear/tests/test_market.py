import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
market = importlib.import_module("trmnl_screens.bull-or-bear.collector.market")

NY = ZoneInfo("America/New_York")


def at(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=NY)


def test_the_window_runs_from_the_open_to_four_hours_after_the_close():
    w = market.window(at(11, 24, 12).date())
    assert (w.opens, w.closes, w.ends) == (at(11, 24, 9, 30), at(11, 24, 16), at(11, 24, 20))


def test_an_early_close_ends_after_hours_early_too():
    w = market.window(at(11, 27, 12).date())  # the day after Thanksgiving
    assert (w.closes, w.ends) == (at(11, 27, 13), at(11, 27, 17))


def test_weekends_and_holidays_have_no_window():
    assert market.window(at(11, 26, 12).date()) is None  # Thanksgiving
    assert market.window(at(11, 28, 12).date()) is None  # Saturday


def test_current_is_the_window_open_now():
    assert market.current(at(11, 24, 9, 29)) is None
    assert market.current(at(11, 24, 9, 30)).opens == at(11, 24, 9, 30)
    assert market.current(at(11, 24, 19, 59)) is not None
    assert market.current(at(11, 24, 20)) is None


def test_the_next_open_skips_holidays_and_weekends():
    assert market.next_open(at(11, 25, 21)) == at(11, 27, 9, 30)  # over Thanksgiving
    assert market.next_open(at(11, 27, 18)) == at(11, 30, 9, 30)  # over the weekend
    assert market.next_open(at(11, 24, 8)) == at(11, 24, 9, 30)
