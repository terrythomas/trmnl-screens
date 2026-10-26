"""F1 screen collector: builds the payload described in docs/specs/f1-screen.md."""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from collector.sections import Section, collect_sections

from .outlines import OutlineStore
from .sources.jolpica import JolpicaError, JolpicaSource

log = logging.getLogger(__name__)

# Default minutes between runs; F1_INTERVAL_MINUTES or INTERVAL_MINUTES override it.
INTERVAL_MINUTES = 60

# The Grands Prix pushed, so a stopped collector still covers a triple-header (spec: Payload contract).
SHOWN = 3

NAMES = {
    "practice_1": "Practice 1", "practice_2": "Practice 2", "practice_3": "Practice 3",
    "sprint_qualifying": "Sprint Qualifying", "sprint": "Sprint", "qualifying": "Qualifying", "race": "Race",
}


def collect(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    state_dir = Path(os.environ.get("STATE_DIR") or "state") / "f1"
    today = now.date().isoformat()
    sections = {"schedule": Section("schedule", lambda: _schedule(JolpicaSource(), today))}
    payload = collect_sections(sections, state_dir / "schedule.json", now)
    # A stale schedule is filtered by today too, so it moves on to later Grands Prix.
    shown = _upcoming(payload.get("schedule", {}).get("grands_prix", []), today)[:SHOWN]
    store = OutlineStore(state_dir / "outlines")
    drawn = {gp["circuit"]: store.outline(gp["circuit"], gp["lat"], gp["lon"], gp["season"], now) for gp in shown}
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "grands_prix": [{k: v for k, v in gp.items() if k not in ("season", "lat", "lon")} for gp in shown],
        "outlines": {circuit: uri for circuit, uri in drawn.items() if uri},
        "errors": payload["errors"],
    }


def _schedule(source, today):
    """Jolpica's current season, and the next one when fewer than SHOWN Grands Prix are left.
    Each is kept with its season and coordinates for finding its outline."""
    season, found = source.season()
    grands_prix = [_grand_prix(gp) for gp in found]
    if len(_upcoming(grands_prix, today)) < SHOWN:
        try:
            grands_prix += [_grand_prix(gp) for gp in source.season(season + 1)[1]]
        except JolpicaError as e:
            # Only fills in the last weeks of a season, so it never marks the schedule stale.
            log.warning("next season skipped: %s", e)
    return {"grands_prix": grands_prix}


def _upcoming(grands_prix, today):
    return [gp for gp in grands_prix if gp["sessions"][-1]["local_date"] >= today]


def _grand_prix(gp):
    return {"season": gp.season, "round": gp.round, "name": gp.name, "location": gp.location, "circuit": gp.circuit,
            "lat": gp.lat, "lon": gp.lon, "sessions": [_session(kind, start) for kind, start in gp.sessions]}


def _session(kind, start):
    start = start.astimezone()  # TZ, with each session's own UTC offset
    end = start + timedelta(hours=2 if kind == "race" else 1)
    return {"kind": kind, "name": NAMES[kind], "start": start.isoformat(), "end": end.isoformat(),
            "local_date": start.date().isoformat()}
