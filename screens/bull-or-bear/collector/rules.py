"""Bull or Bear? rules: volatility, the big move, the lead, the row of changes and the chart (docs/specs/market-screens.md)."""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import pstdev

DAY_MULTIPLE = 1.5
THIRTY_MULTIPLE = 3.0
THIRTY = 21  # trading days in "30 days"
YEAR_SHARE = 640  # of the chart's 1000 units, the rest going to the last 30 days (the split time scale)
SOON = timedelta(days=7)  # how far ahead a dividend is shown

EARNINGS = {"bmo": "Earnings before open", "amc": "Earnings after close"}


def changes(closes: list[float], span: int = 1) -> list[float]:
    return [closes[i] / closes[i - span] - 1 for i in range(span, len(closes))]


def volatility(closes: list[float], span: int = 1) -> float:
    """The standard deviation of the stock's `span`-day changes over the closes given."""
    return pstdev(changes(closes, span))


def money(v: float) -> str:
    return f"${v:,.2f}"


def pct(p: float) -> str:
    return ("+" if p >= 0 else "−") + f"{abs(p) * 100:.1f}%"


@dataclass(frozen=True)
class Moves:
    day: float  # today's regular-session price against the previous close
    after: float | None  # the after-hours price against today's price, after the close
    thirty: float
    year: float
    big_day: bool
    big_after: bool
    big_thirty: bool


def moves(history: list[float], price: float, after: float | None,
          day_multiple: float = DAY_MULTIPLE, thirty_multiple: float = THIRTY_MULTIPLE) -> Moves:
    """`history` is daily closes, oldest first, ending with the previous close; `price` is today's."""
    shown = after or price
    series = history + [price]
    # Each yardstick stops before the move it judges, so a big move can't widen its own measure of "typical".
    daily, monthly = volatility(history), volatility(history[:-THIRTY], THIRTY)
    day = price / history[-1] - 1
    late = after / price - 1 if after else None
    thirty = shown / series[-THIRTY - 1] - 1
    return Moves(day, late, thirty, shown / series[0] - 1,
                 abs(day) > day_multiple * daily,
                 late is not None and abs(late) > day_multiple * daily,
                 abs(thirty) > thirty_multiple * monthly)


def earnings_label(earnings: list[dict], today: date) -> str | None:
    """The badge for today's earnings report, if the stock reports today."""
    for e in earnings:
        if e["date"] == today.isoformat():
            return EARNINGS.get(e.get("hour") or "", "Earnings today")
    return None


def dividend_line(dividends: list[dict], today: date) -> tuple[bool, str | None]:
    """(paid today, the line to show) for the soonest dividend paid today or within a week."""
    for d in sorted(dividends, key=lambda d: d["pay"]):
        pay = date.fromisoformat(d["pay"])
        if pay == today:
            return True, f"Paid {money(d['amount'])} a share today"
        if today < pay <= today + SOON:
            return False, f"Pays {money(d['amount'])} · {pay:%b} {pay.day}"
    return False, None


def lead(m: Moves, earnings: str | None, paid_today: bool) -> dict | None:
    """What leads the screen, in the spec's order of preference; None when nothing shows the stock."""
    for big, kind, label, value in ((m.big_after, "after_hours", "After hours", m.after),
                                    (m.big_day, "day", "Today", m.day),
                                    (m.big_thirty, "thirty", "30 days", m.thirty)):
        if big:
            return {"kind": kind, "label": label, "value": pct(value), "dir": "down" if value < 0 else "up"}
    if earnings:
        return {"kind": "badge", "label": earnings}
    if paid_today:
        return {"kind": "badge", "label": "Dividend paid today"}
    return None


def change_row(m: Moves, history: list[float], price: float, lead_kind: str | None) -> list[dict]:
    """Previous close, today, 30 days and 1 year, leaving out what the lead or the close line already shows."""
    series = history + [price]
    row = [{"label": "Prev close", "value": money(history[-1])},
           {"label": "Today", "value": pct(m.day)},
           {"label": "30 days", "value": pct(m.thirty), "sub": "from " + money(series[-THIRTY - 1])},
           {"label": "1 year", "value": pct(m.year), "sub": "from " + money(series[0])}]
    shown = {"day": "Today", "after_hours": "Today", "thirty": "30 days"}.get(lead_kind or "")
    return [c for c in row if c["label"] != shown]


def chart(days: list[date], closes: list[float]) -> dict:
    """One year of closes on the split time scale, in a 1000x300 box; high, low and the 30-day start marked."""
    lo, hi = min(closes), max(closes)
    pad = (hi - lo) * 0.08 or 1
    top, bottom = hi + pad, lo - pad
    n, start = len(closes), len(closes) - THIRTY - 1

    def x(i):
        return round(i * YEAR_SHARE / start if i <= start else YEAR_SHARE + (i - start) * (1000 - YEAR_SHARE) / (n - 1 - start), 1)

    pts = [(x(i), round((top - c) * 300 / (top - bottom), 1)) for i, c in enumerate(closes)]

    def mark(i, word):
        return {"x": pts[i][0] / 10, "y": round(pts[i][1] / 3, 1), "label": f"{word} {money(closes[i])} · {days[i]:%b} {days[i].day}"}

    return {"line": " ".join(f"{a},{b}" for a, b in pts),
            "recent": " ".join(f"{a},{b}" for a, b in pts[start:]),
            "start_y": round(pts[start][1] / 3, 1),
            "high": mark(closes.index(hi), "High"),
            "low": mark(closes.index(lo), "Low")}
