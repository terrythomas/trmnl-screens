"""Airing section: the airing window, season drops, milestones and payload mapping (spec: Airing)."""

from datetime import datetime, timedelta
from typing import Any, Protocol

from .posters import PosterSource, poster_uri
from .sources.sonarr import SonarrEpisode

WINDOW = timedelta(hours=12)


class Calendar(Protocol):
    def calendar(self, start: datetime, end: datetime) -> list[SonarrEpisode]: ...


def airing(calendar: Calendar, posters: PosterSource, now: datetime) -> dict[str, Any] | None:
    """The Airing section of the payload, or None when nothing is in the airing window."""
    start, end = now - WINDOW, now + WINDOW
    episodes = sorted(
        (e for e in calendar.calendar(start, end)
         if start <= e.air_time <= end and e.monitored and e.series_monitored),
        key=lambda e: e.air_time,
    )
    if not episodes:
        return None
    # A season dropping at once (same series, season and air time) becomes one row.
    drops: dict[tuple, list[SonarrEpisode]] = {}
    for e in episodes:
        drops.setdefault((e.series_id, e.season, e.air_time), []).append(e)
    rows = [sorted(group, key=lambda e: e.number) for group in drops.values()]
    return {"stale": False, "items": [_row(row, posters, now) for row in rows]}


def _row(row: list[SonarrEpisode], posters: PosterSource, now: datetime) -> dict[str, Any]:
    e, last = row[0], row[-1]
    return {
        "series": e.series,
        "season": e.season,
        "number": e.number,
        "number_end": last.number if len(row) > 1 else None,
        "title": e.title if len(row) == 1 else None,
        # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
        "air_time": e.air_time.astimezone(now.tzinfo).isoformat(timespec="seconds"),
        "aired": e.air_time <= now,
        "grabbed": all(episode.grabbed for episode in row),
        "runtime_min": e.runtime_min,
        "milestone": milestone(row),
        "poster": poster_uri(posters, e.poster_url) if e.poster_url else None,
    }


def milestone(row: list[SonarrEpisode]) -> str | None:
    """What the row opens or closes (CONTEXT.md: Milestone). row is sorted by episode number."""
    first = row[0]
    finales = [e.finale for e in row if e.finale]
    if len(row) > 1 and first.number == 1 and finales:
        return "entire_season"
    if finales:
        return f"{finales[-1]}_finale"
    if first.number == 1:
        return "series_premiere" if first.season == 1 else "season_premiere"
    return None
