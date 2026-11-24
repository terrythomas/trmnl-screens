"""Write the template's fixtures from an invented price series, through the collector's own screen().

    uv run python screens/bull-or-bear/fixtures/build.py
"""

import importlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.discovery import discover_screens

discover_screens()
pkg = importlib.import_module("trmnl_screens.bull-or-bear.collector")
market = importlib.import_module("trmnl_screens.bull-or-bear.collector.market")

HERE = Path(__file__).parent
NY = ZoneInfo("America/New_York")
TODAY = datetime(2026, 11, 24, tzinfo=NY).date()


def series(seed, n=252, drift=0.0, vol=0.025, start=150.0, slide=0.0):
    """An invented random walk; `slide` adds a steady daily fall over the last 21 days."""
    rng, closes = random.Random(seed), [start]
    for i in range(n - 1):
        closes.append(closes[-1] * (1 + rng.gauss(drift, vol) - (slide if i >= n - 22 else 0)))
    days, d = [], TODAY
    while len(days) < n:
        if market.window(d):
            days.append(d)
        d -= timedelta(days=1)
    return [[day.isoformat(), round(c, 2)] for day, c in zip(reversed(days), closes)]


def write(name, symbol, company, closes, now, move=0.0, after=None, earnings=(), dividends=(), stale=False):
    days = closes[:-1]
    price = days[-1][1] * (1 + move)
    quote = {"name": company, "days": days, "price": round(price, 2), "price_time": int(now.timestamp())}
    if after is not None:
        quote |= {"after": round(price * (1 + after), 2), "after_time": int(now.timestamp())}
    payload = pkg.screen(symbol, quote, now.astimezone(timezone.utc), market.window(TODAY), list(earnings), list(dividends), {})
    payload["as_of"] = f"{now:%-I:%M %p}"
    payload["preview_now"] = now.isoformat()  # the template compares the render time with visible_until
    payload["errors"] = []
    if stale:
        payload |= {"stale": True, "errors": [{"source": "yahoo", "since": "2026-11-24T13:15:00-05:00", "label": "Prices down since 1:15 PM"}]}
    (HERE / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return payload


def at(h, m=0):
    return datetime(2026, 11, 24, h, m, tzinfo=NY)


day = write("day", "EXMP", "Example Corp", series(1), at(14, 45), move=-0.079)
write("after", "EXMP", "Example Corp", series(1), at(18, 30), move=0.012, after=-0.114,
      earnings=[{"date": "2026-11-24", "hour": "amc"}])
write("thirty", "SLDE", "Slide Industries", series(2, slide=0.03), at(11, 5), move=0.004)
write("earnings", "EXMP", "Example Corp", series(1), at(9, 45), move=0.006, earnings=[{"date": "2026-11-24", "hour": "bmo"}])
write("paydate", "DIVY", "Dividend Yield Holdings Incorporated", series(3, vol=0.012), at(13, 20), move=-0.003,
      dividends=[{"pay": "2026-11-24", "amount": 0.27}])
write("stale", "EXMP", "Example Corp", series(1), at(13, 15), move=-0.06, stale=True)
(HERE / "sample.json").write_text((HERE / "day.json").read_text())
for f in sorted(HERE.glob("*.json")):
    p = json.loads(f.read_text())
    print(f.stem, p["show"], p["lead"].get("kind"), p["lead"].get("value") or p["lead"].get("label"))
