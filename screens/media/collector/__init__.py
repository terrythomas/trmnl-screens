"""Media screen collector: builds the payload described in docs/specs/media-screen.md."""

import os
from datetime import datetime
from typing import Any

from .continue_watching import continue_watching
from .sources.plex import PlexSource


def collect() -> dict[str, Any]:
    # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
    now = datetime.now().astimezone()
    payload: dict[str, Any] = {"updated_at": now.isoformat(timespec="seconds")}
    plex = PlexSource(os.environ["PLEX_URL"], os.environ["PLEX_TOKEN"])
    section = continue_watching(plex, now, new_after_days=int(os.environ.get("NEW_AFTER_DAYS") or 30))
    if section:  # an empty section is left out (spec: Empty and failure behaviour)
        payload["continue_watching"] = section
    return payload
