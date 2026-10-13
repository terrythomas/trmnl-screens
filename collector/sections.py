"""Keeps a screen's sections on screen when their sources fail (spec: Empty and failure behaviour).

Each section's last good data lives in a small JSON state file. When a section's
build fails, its last good data is reused marked stale, and its source is reported
in errors[] with the time of the first consecutive failure.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Section:
    source: str  # the name reported in errors[], e.g. "sonarr"
    build: Callable[[], dict[str, Any] | None]  # None when the section has no items


def collect_sections(sections: dict[str, Section], state_path: Path, now: datetime) -> dict[str, Any]:
    """The payload's sections plus errors[]. A failing section never stops the others."""
    state = _load(state_path)
    last_good, failing_since = state["sections"], state["failing"]
    payload: dict[str, Any] = {}
    failed: set[str] = set()
    for name, section in sections.items():
        try:
            data = section.build()
        except Exception as e:
            # Sources raise errors whose messages hold no URL or secret (ADR-0003); no
            # traceback, because one failure would otherwise flood the log every tick.
            log.warning("section %s: %s failed: %s: %s", name, section.source, type(e).__name__, e)
            failed.add(section.source)
            if name in last_good:
                payload[name] = {**last_good[name], "stale": True}
            continue
        if data:
            payload[name] = last_good[name] = data
        else:
            last_good.pop(name, None)  # empty now, so a later failure can't bring old items back
    stamp = now.isoformat(timespec="seconds")
    state["failing"] = {source: failing_since.get(source, stamp) for source in sorted(failed)}
    _save(state_path, state)
    errors = [{"source": source, "since": since} for source, since in state["failing"].items()]
    return {"errors": errors, **payload}


def _load(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text())
        return {"sections": dict(state["sections"]), "failing": dict(state["failing"])}
    except FileNotFoundError:
        pass
    except (ValueError, KeyError, TypeError):
        log.warning("state file %s is unreadable, starting fresh", path.name)
    return {"sections": {}, "failing": {}}


def _save(path: Path, state: dict[str, Any]) -> None:
    # Write then rename, so a crash mid-write never leaves a half-written file.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    os.replace(temporary, path)
