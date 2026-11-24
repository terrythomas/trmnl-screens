"""Nasdaq dividend source: a stock's declared dividends with their pay dates. Unofficial; coverage has gaps."""

from datetime import datetime

import httpx

from . import SourceError, get_json

# Without a browser User-Agent the endpoint hangs until it times out (checked 2026-11-24).
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


class NasdaqSource:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url="https://api.nasdaq.com/api", headers=HEADERS, timeout=30, transport=transport)

    def dividends(self, symbol: str) -> list[dict]:
        """[{pay: iso date, amount}] for the cash dividends Nasdaq lists; [] when it has none for the stock."""
        body = get_json(self._client, "Nasdaq", f"/quote/{symbol}/dividends", params={"assetclass": "stocks"})
        rows = ((body or {}).get("data") or {}).get("dividends") or {}
        out = []
        for row in rows.get("rows") or []:
            try:
                pay = datetime.strptime(row["paymentDate"], "%m/%d/%Y").date().isoformat()
                amount = float(row["amount"].lstrip("$").replace(",", ""))
            except (KeyError, ValueError, AttributeError, TypeError):
                continue  # "N/A" dates and non-cash rows
            out.append({"pay": pay, "amount": amount})
        return out
