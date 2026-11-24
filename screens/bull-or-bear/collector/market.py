"""Trading days and the market window (CONTEXT.md), from the offline NYSE calendar in exchange_calendars."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cache

import exchange_calendars

AFTER_HOURS = timedelta(hours=4)


@dataclass(frozen=True)
class Window:
    opens: datetime
    closes: datetime  # the regular session's close, early on early-close days
    ends: datetime  # the end of after hours


@cache
def _nyse():
    return exchange_calendars.get_calendar("XNYS")


def window(day: date) -> Window | None:
    """The market window on a trading day; None on weekends and market holidays."""
    nyse = _nyse()
    if not nyse.is_session(day.isoformat()):
        return None
    opens = nyse.session_open(day.isoformat()).to_pydatetime()
    closes = nyse.session_close(day.isoformat()).to_pydatetime()
    return Window(opens, closes, closes + AFTER_HOURS)


def current(now: datetime) -> Window | None:
    """The market window `now` falls in, if any."""
    w = window(now.astimezone(_nyse().tz).date())
    return w if w and w.opens <= now < w.ends else None


def next_open(now: datetime) -> datetime | None:
    """When the next market window opens; None past the calendar's end."""
    day = now.astimezone(_nyse().tz).date()
    for _ in range(14):
        w = window(day)
        if w and w.opens > now:
            return w.opens
        day += timedelta(days=1)
    return None
