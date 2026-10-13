"""Media screen collector: builds the payload described in docs/specs/media-screen.md."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from collector.sections import Section, collect_sections

from .airing import airing
from .continue_watching import continue_watching
from .in_theaters import in_theaters
from .sources.plex import PlexSource
from .sources.radarr import RadarrSource
from .sources.sonarr import SonarrSource
from .sources.tmdb import TmdbSource
from .streaming import streaming


def collect() -> dict[str, Any]:
    # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
    now = datetime.now().astimezone()
    plex = PlexSource(os.environ["PLEX_URL"], os.environ["PLEX_TOKEN"])
    sonarr = SonarrSource(os.environ["SONARR_URL"], os.environ["SONARR_API_KEY"])
    radarr = RadarrSource(os.environ["RADARR_URL"], os.environ["RADARR_API_KEY"])
    new_after_days = int(os.environ.get("NEW_AFTER_DAYS") or 30)
    state_dir = Path(os.environ.get("STATE_DIR") or "state")
    tmdb = TmdbSource(os.environ.get("RELEASE_COUNTRY") or "US", state_dir / "tmdb-releases.json")
    # Plex's transcoder makes Sonarr's and Radarr's posters grayscale too; if it is down,
    # those rows go without posters rather than the sections going stale.
    sections = {
        "continue_watching": Section("plex", lambda: continue_watching(plex, now, new_after_days=new_after_days)),
        "airing": Section("sonarr", lambda: airing(sonarr, plex, now)),
        # Radarr picks the candidates and TMDB dates them; a TMDB failure reports as "tmdb".
        "in_theaters": Section("radarr", lambda: in_theaters(radarr, tmdb, plex, now)),
        "streaming": Section("radarr", lambda: streaming(radarr, plex, now)),
    }
    payload = collect_sections(sections, state_dir / "media.json", now)
    return {"updated_at": now.isoformat(timespec="seconds"), **payload}
