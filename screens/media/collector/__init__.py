"""Media screen collector: builds the payload described in docs/specs/media-screen.md."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from collector.sections import Section, collect_sections

from .airing import airing
from .continue_watching import continue_watching
from .releasing_today import releasing_today
from .sources.plex import PlexSource
from .sources.radarr import RadarrSource
from .sources.sonarr import SonarrSource


def collect() -> dict[str, Any]:
    # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
    now = datetime.now().astimezone()
    plex = PlexSource(os.environ["PLEX_URL"], os.environ["PLEX_TOKEN"])
    sonarr = SonarrSource(os.environ["SONARR_URL"], os.environ["SONARR_API_KEY"])
    radarr = RadarrSource(os.environ["RADARR_URL"], os.environ["RADARR_API_KEY"])
    new_after_days = int(os.environ.get("NEW_AFTER_DAYS") or 30)
    # Plex's transcoder makes Sonarr's and Radarr's posters grayscale too; if it is down,
    # those rows go without posters rather than the sections going stale.
    sections = {
        "continue_watching": Section("plex", lambda: continue_watching(plex, now, new_after_days=new_after_days)),
        "airing": Section("sonarr", lambda: airing(sonarr, plex, now)),
        "releasing_today": Section("radarr", lambda: releasing_today(radarr, plex, now)),
    }
    state_path = Path(os.environ.get("STATE_DIR") or "state") / "media.json"
    return {"updated_at": now.isoformat(timespec="seconds"), **collect_sections(sections, state_path, now)}
