"""Media screen collector: builds the payload described in docs/specs/media-screen.md."""

import os
from datetime import datetime
from typing import Any

from .airing import airing
from .continue_watching import continue_watching
from .releasing_today import releasing_today
from .sources.plex import PlexSource
from .sources.radarr import RadarrSource
from .sources.sonarr import SonarrSource


def collect() -> dict[str, Any]:
    # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
    now = datetime.now().astimezone()
    payload: dict[str, Any] = {"updated_at": now.isoformat(timespec="seconds")}
    plex = PlexSource(os.environ["PLEX_URL"], os.environ["PLEX_TOKEN"])
    sonarr = SonarrSource(os.environ["SONARR_URL"], os.environ["SONARR_API_KEY"])
    radarr = RadarrSource(os.environ["RADARR_URL"], os.environ["RADARR_API_KEY"])
    sections = {
        "continue_watching": continue_watching(plex, now, new_after_days=int(os.environ.get("NEW_AFTER_DAYS") or 30)),
        # Plex's transcoder makes Sonarr's and Radarr's posters grayscale too.
        "airing": airing(sonarr, plex, now),
        "releasing_today": releasing_today(radarr, plex, now),
    }
    # An empty section is left out (spec: Empty and failure behaviour).
    payload.update({name: section for name, section in sections.items() if section})
    return payload
