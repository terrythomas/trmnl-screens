"""Bull or Bear? screen collector: one stock per instance (BULL_OR_BEAR_INSTANCES=aapl,msft), docs/specs/market-screens.md."""

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from collector.sections import Section, collect_sections

from . import market, rules
from .sources import SourceError
from .sources.finnhub import FinnhubSource
from .sources.nasdaq import NasdaqSource
from .sources.yahoo import NY, SYMBOL, YahooSource

log = logging.getLogger(__name__)

# Minutes between runs inside the market window. BULL_OR_BEAR_<STOCK>_INTERVAL_MINUTES overrides it.
INTERVAL_MINUTES = 15


def collect(instance: str | None = None, now: datetime | None = None, yahoo=None, finnhub=None, nasdaq=None) -> dict[str, Any]:
    symbol = (instance or "").upper()
    if not SYMBOL.match(symbol):
        raise SourceError("Bull or Bear? runs once per stock: set BULL_OR_BEAR_INSTANCES, e.g. aapl,msft")
    now = now or datetime.now().astimezone()  # times on screen are printed in now's zone, as on the other screens
    window = market.current(now)
    if window is None:
        return {"symbol": symbol, "show": False}  # outside the market window nothing is fetched
    today = now.astimezone(NY).date()
    state_dir = Path(os.environ.get("STATE_DIR") or "state") / "bull-or-bear" / symbol.lower()

    sections = {"quote": Section("yahoo", lambda: (yahoo or YahooSource()).quote(symbol))}
    found = collect_sections(sections, state_dir / "sections.json", now)
    errors = found["errors"]
    earnings = _daily(state_dir / "earnings.json", today, errors,
                      lambda: (finnhub or FinnhubSource(os.environ.get("FINNHUB_API_KEY"))).earnings(symbol, today))
    dividends = _daily(state_dir / "dividends.json", today, errors, lambda: (nasdaq or NasdaqSource()).dividends(symbol))

    for e in errors:
        e["label"] = _banner(e, now)
    quote = found.get("quote")
    if not quote:
        return {"symbol": symbol, "show": False, "errors": errors}
    return {**screen(symbol, quote, now, window, earnings, dividends, _multiples(instance)),
            "errors": errors, **({"stale": True} if quote.get("stale") else {})}


def screen(symbol: str, quote: dict, now: datetime, window: market.Window, earnings: list, dividends: list,
           multiples: dict) -> dict[str, Any]:
    """The payload for one stock, from its quote and today's earnings and dividends."""
    today = now.astimezone(NY).date()
    days = [(date.fromisoformat(d), c) for d, c in quote["days"]]
    if days[-1][0] == today:  # today's bar is still moving; the quote's price is fresher
        days = days[:-1]
    history = [c for _, c in days]
    price = quote["price"]
    after = quote.get("after") if quote.get("after_time", 0) >= window.closes.timestamp() else None
    m = rules.moves(history, price, after, **multiples)
    earnings_label = rules.earnings_label(earnings, today)
    paid_today, dividend = rules.dividend_line(dividends, today)
    lead = rules.lead(m, earnings_label, paid_today)
    as_of = datetime.fromtimestamp(quote["after_time"] if after else quote["price_time"], timezone.utc)
    out = {
        "symbol": symbol,
        "name": quote["name"],
        "as_of": as_of.astimezone(now.tzinfo).strftime("%-I:%M %p"),
        "price": rules.money(after or price),
        "show": lead is not None,
        "visible_until": int(window.ends.timestamp()),
        "lead": lead or {"kind": "none"},
        "changes": rules.change_row(m, history, price, lead and lead["kind"]),
        "chart": rules.chart([d for d, _ in days] + [today], history + [after or price]),
    }
    if lead and lead["kind"] == "thirty":
        out["lead"]["sub"] = "from " + rules.money((history + [price])[-rules.THIRTY - 1])
    if earnings_label and lead and lead["kind"] != "badge":
        out["badge"] = earnings_label
    if after:
        out["close_line"] = f"Close {rules.money(price)} ({rules.pct(m.day)})"
        out["after_line"] = f"After hours {rules.money(after)} ({rules.pct(m.after)})"
    if dividend:
        out["dividend"] = dividend
    return out


def next_run_minutes(payload: dict) -> float | None:
    """Wake for the next market window's open; inside the window, keep the interval."""
    now = datetime.now(timezone.utc)
    if market.current(now):
        return None
    opens = market.next_open(now)
    return (opens - now).total_seconds() / 60 + 0.5 if opens else None


def _daily(path: Path, today: date, errors: list, fetch: Callable[[], list]) -> list:
    """A list fetched at most once a day. A failure keeps the last list and never marks the screen stale;
    a key problem is reported in errors[], since it won't fix itself."""
    try:
        cached = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        cached = {}
    if cached.get("date") == today.isoformat():
        return cached.get("items", [])
    try:
        items = fetch()
    except SourceError as e:
        log.warning("%s: %s", path.stem, e)
        if getattr(e, "source", None):
            errors.append({"source": e.source, "since": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        return cached.get("items", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": today.isoformat(), "items": items}))
    return items


def _banner(error: dict, now: datetime) -> str:
    if error["source"] == "finnhub-key":
        return "Earnings off: Finnhub key missing or rejected"
    since = datetime.fromisoformat(error["since"]).astimezone(now.tzinfo)
    return f"Prices down since {since:%-I:%M %p}"


def _multiples(instance: str) -> dict:
    """Per-stock multiples: BULL_OR_BEAR_<STOCK>_DAY_MULTIPLE and _THIRTY_MULTIPLE."""
    prefix = f"BULL_OR_BEAR_{instance.upper()}_"
    out = {}
    for key, arg in (("DAY_MULTIPLE", "day_multiple"), ("THIRTY_MULTIPLE", "thirty_multiple")):
        if os.environ.get(prefix + key):
            out[arg] = float(os.environ[prefix + key])
    return out
