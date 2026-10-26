"""F1 screen collector: builds the payload described in docs/specs/f1-screen.md."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from collector.sections import Section, collect_sections

from .outlines import OutlineStore
from .sources.jolpica import JolpicaSource

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
    sections = {"schedule": Section("schedule", lambda: _schedule(JolpicaSource(), now.year))}
    payload = collect_sections(sections, state_dir / "schedule.json", now)
    # A stale schedule is filtered by today too, so it moves on to later Grands Prix.
    season = payload.get("schedule", {}).get("grands_prix", [])
    today = now.date().isoformat()
    shown = [gp for gp in season if gp["sessions"][-1]["local_date"] >= today][:SHOWN]
    store = OutlineStore(state_dir / "outlines")
    drawn = {gp["circuit"]: store.outline(gp["circuit"], gp["lat"], gp["lon"], now.year, now) for gp in shown}
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "grands_prix": [{k: v for k, v in gp.items() if k not in ("lat", "lon")} for gp in shown],
        "outlines": {circuit: uri for circuit, uri in drawn.items() if uri},
        "errors": payload["errors"],
    }


def _schedule(source, year):
    """The whole season, kept with each circuit's coordinates for finding its outline."""
    return {"grands_prix": [
        {"round": gp.round, "name": gp.name, "location": gp.location, "circuit": gp.circuit,
         "lat": gp.lat, "lon": gp.lon, "sessions": [_session(kind, start) for kind, start in gp.sessions]}
        for gp in source.season(year)
    ]}


def _session(kind, start):
    start = start.astimezone()  # TZ, with each session's own UTC offset
    end = start + timedelta(hours=2 if kind == "race" else 1)
    return {"kind": kind, "name": NAMES[kind], "start": start.isoformat(), "end": end.isoformat(),
            "local_date": start.date().isoformat()}
