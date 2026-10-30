"""Where's My Stuff? screen collector: builds the payload described in docs/specs/wheres-my-stuff-screen.md."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from collector.sections import Section, collect_sections

from .rules import STATUS, headline, record, shown
from .sources.parcel import ParcelError, ParcelKeyError, ParcelSource

log = logging.getLogger(__name__)

# Default minutes between runs; Parcel allows 20 requests an hour. WHERES_MY_STUFF_INTERVAL_MINUTES overrides it.
INTERVAL_MINUTES = 15

CARRIERS_FOR = timedelta(hours=24)


def collect(now: datetime | None = None, source: ParcelSource | None = None) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    state_dir = Path(os.environ.get("STATE_DIR") or "state") / "wheres-my-stuff"

    def build():
        parcel = source or _source()
        raw = parcel.deliveries()
        if not raw:
            return None
        carriers = _carriers(parcel, state_dir / "carriers.json", now)
        for code in sorted({r["status_code"] for r in raw} - STATUS.keys(), key=str):
            log.warning("unknown Parcel status code %s, shown as On the way", code)
        return {"records": [record(r, carriers) for r in raw]}

    payload = collect_sections({"parcel": Section("parcel", build)}, state_dir / "deliveries.json", now)
    section = payload.get("parcel", {})
    # Stored records are labelled again for `now`, so a stale "Today" still turns Late.
    deliveries = shown(section.get("records", []), now)
    result = {"updated_at": now.isoformat(timespec="seconds"), "headline": headline(deliveries),
              "deliveries": deliveries, "errors": payload["errors"]}
    if section.get("stale"):
        result["stale"] = True
    return result


def _source():
    key = os.environ.get("PARCEL_API_KEY")
    if not key:
        raise ParcelKeyError("No Parcel API key is set")
    return ParcelSource(key)


def _carriers(parcel, path, now):
    """Carrier names, fetched at most daily. A failure keeps the last list, or none: carriers then show their codes."""
    try:
        cached = json.loads(path.read_text())
        if now - datetime.fromisoformat(cached["fetched_at"]) < CARRIERS_FOR:
            return cached["carriers"]
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        cached = {}
    try:
        carriers = parcel.carriers()
    except ParcelError as e:
        log.warning("carrier names skipped: %s", e)
        return cached.get("carriers", {})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "carriers": carriers}))
    return carriers
