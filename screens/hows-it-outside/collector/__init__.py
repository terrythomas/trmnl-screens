"""How's It Outside? screen collector: builds the payload described in docs/specs/hows-it-outside-screen.md."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from collector.sections import Section, collect_sections

from . import rules
from .sources import SourceError
from .sources.nws import NwsSource
from .sources.openmeteo import OpenMeteoSource
from .sources.pollen import PollenKeyError, PollenSource

# Default minutes between runs; Open-Meteo's "current" moves in 15-minute steps. HOWS_IT_OUTSIDE_INTERVAL_MINUTES overrides it.
INTERVAL_MINUTES = 15

# How long a failing forecast is still worked out from its stored hours before the screen says it's gone.
STALE_FOR = timedelta(hours=3)


def collect(now: datetime | None = None, meteo=None, nws=None, pollen=None) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    state_dir = Path(os.environ.get("STATE_DIR") or "state") / "hows-it-outside"

    def alerts():
        found = (nws or NwsSource(*_location())).alerts()
        return {"alerts": found} if found else None

    sections = {
        "forecast": Section("open-meteo", lambda: (meteo or _meteo()).forecast()),
        "air": Section("open-meteo-air", lambda: (meteo or _meteo()).air()),
        "alerts": Section("nws", alerts),
        "pollen": Section("google-pollen", lambda: _pollen(pollen, state_dir / "pollen.json", now)),
    }
    payload = collect_sections(sections, state_dir / "sections.json", now)

    result: dict[str, Any] = {"updated_at": now.isoformat(timespec="seconds")}
    result |= _weather(payload.get("forecast"), payload["errors"], now)
    cards, more = rules.alerts(payload.get("alerts", {}).get("alerts", []), now)
    result["alerts"] = cards
    if more:
        result["more_alerts"] = more
    day = payload.get("pollen", {})
    if day.get("date") == now.date().isoformat() and day.get("pollen"):
        result["pollen"] = day["pollen"]
    if "air" in payload:
        result["air"] = {"aqi": payload["air"]["aqi"]}
    stale = [name for name in sections if payload.get(name, {}).get("stale")]
    if stale:
        result["stale"] = stale
    result["errors"] = payload["errors"]
    return result


def _weather(forecast, errors, now):
    """Current conditions, verdicts, outlook and sun, worked out again for `now` from the stored hours."""
    since = next((datetime.fromisoformat(e["since"]) for e in errors if e["source"] == "open-meteo"), now)
    this_hour = now.replace(tzinfo=None, minute=0, second=0, microsecond=0).isoformat(timespec="minutes")
    hour = forecast and next((h for h in forecast["hours"] if h["time"] == this_hour), None)
    day = forecast and next((d for d in forecast["days"] if d["date"] == now.date().isoformat()), None)
    if not (hour and day) or (forecast.get("stale") and now - since >= STALE_FOR):
        return {"now": {"missing_since": rules.clock(since)}}
    # A stale "current" reading is hours old; the stored hour for now is closer.
    current = hour if forecast.get("stale") else forecast["current"]
    kind, window = rules.outlook(forecast["hours"], now)
    return {"now": rules.conditions(current, day), "verdicts": rules.verdicts(forecast["hours"], now),
            "outlook": {"kind": kind, "hours": rules.timeline(window, forecast["days"])},
            "sun": rules.sun(forecast["days"], now)}


def _location():
    try:
        return os.environ["HOWS_IT_OUTSIDE_LATITUDE"], os.environ["HOWS_IT_OUTSIDE_LONGITUDE"]
    except KeyError as e:
        raise SourceError(f"{e.args[0]} is not set") from None


def _meteo():
    return OpenMeteoSource(*_location(), os.environ.get("TZ") or "auto")


def _pollen(source, path, now):
    """Today's pollen, fetched at most once a day (Google bills past 5,000 requests a month)."""
    today = now.date().isoformat()
    try:
        cached = json.loads(path.read_text())
        if cached["date"] == today:
            return cached
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        pass
    if source is None:
        key = os.environ.get("GOOGLE_POLLEN_API_KEY")
        if not key:
            raise PollenKeyError("No Google Pollen API key is set")
        source = PollenSource(key, *_location())
    day = {"date": today, "pollen": rules.pollen(source.today())}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(day))
    return day
