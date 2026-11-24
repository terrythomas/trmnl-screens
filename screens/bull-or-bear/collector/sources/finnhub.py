"""Finnhub earnings-calendar source: the date and time of day of a stock's next earnings reports."""

from datetime import date, timedelta

import httpx

from . import SourceError, get_json


class FinnhubKeyError(SourceError):
    """Finnhub refused the API key, or there is none."""

    source = "finnhub-key"


class FinnhubSource:
    def __init__(self, api_key: str | None, transport: httpx.BaseTransport | None = None):
        self._key = api_key
        self._client = httpx.Client(base_url="https://finnhub.io/api/v1", timeout=30, transport=transport)

    def earnings(self, symbol: str, today: date) -> list[dict]:
        """[{date, hour}] for the next 90 days; hour is "bmo" (before open), "amc" (after close) or ""."""
        if not self._key:
            raise FinnhubKeyError("FINNHUB_API_KEY is not set")
        params = {"symbol": symbol, "from": today.isoformat(), "to": (today + timedelta(days=90)).isoformat(), "token": self._key}
        try:
            body = get_json(self._client, "Finnhub", "/calendar/earnings", params=params)
        except SourceError as e:
            if e.status in (401, 403):
                raise FinnhubKeyError("Finnhub rejected the API key") from None
            raise
        try:
            return [{"date": e["date"], "hour": e.get("hour") or ""} for e in body.get("earningsCalendar") or []]
        except (KeyError, TypeError, AttributeError):
            raise SourceError("Finnhub returned an unexpected response") from None
