"""Yahoo Finance chart source: a stock's year of daily closes, its price, and its after-hours price (ADR-0014)."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from . import SourceError, get_json

NY = ZoneInfo("America/New_York")
# Yahoo answers clients without a browser User-Agent with HTTP 429 (checked 2026-11-24).
HEADERS = {"User-Agent": "Mozilla/5.0"}
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class YahooSource:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url="https://query2.finance.yahoo.com", headers=HEADERS, timeout=30, transport=transport)

    def quote(self, symbol: str) -> dict:
        """{name, days: [[iso date, close]], price, price_time, after, after_time}; times are epoch seconds."""
        if not SYMBOL.match(symbol):
            raise SourceError(f"not a stock symbol: {symbol!r}")
        year = self._chart(symbol, range="1y", interval="1d")
        today = self._chart(symbol, range="1d", interval="5m", includePrePost="true")
        try:
            meta = year["meta"]
            closes = year["indicators"]["quote"][0]["close"]
            days = [[datetime.fromtimestamp(t, NY).date().isoformat(), c] for t, c in zip(year["timestamp"], closes) if c is not None]
            close_at = today["meta"]["currentTradingPeriod"]["regular"]["end"]
            late = [(t, c) for t, c in zip(today.get("timestamp") or [], today["indicators"]["quote"][0]["close"])
                    if c is not None and t >= close_at]
            out = {"name": meta.get("shortName") or meta.get("longName") or symbol, "days": days,
                   "price": meta["regularMarketPrice"], "price_time": meta["regularMarketTime"]}
        except (KeyError, IndexError, TypeError):
            raise SourceError("Yahoo returned an unexpected response") from None
        if not days:
            raise SourceError("Yahoo returned no daily closes")
        if late:
            out["after_time"], out["after"] = late[-1]
        return out

    def _chart(self, symbol: str, **params) -> dict:
        body = get_json(self._client, "Yahoo", f"/v8/finance/chart/{symbol}", params=params)
        try:
            return body["chart"]["result"][0]
        except (KeyError, IndexError, TypeError):
            raise SourceError("Yahoo returned an unexpected response") from None
