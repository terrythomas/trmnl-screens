"""Streaming section: the digital release rule and payload mapping (spec: Streaming)."""

from datetime import date, datetime, timedelta
from typing import Any, Protocol

from .posters import PosterSource, poster_uri
from .sources.radarr import RadarrMovie


class Calendar(Protocol):
    def calendar(self, start: date, end: date) -> list[RadarrMovie]: ...


def streaming(calendar: Calendar, posters: PosterSource, now: datetime) -> dict[str, Any] | None:
    """The Streaming section of the payload, or None when nothing is released digitally today."""
    today = now.date()  # now is local time, so this is the local calendar day
    movies = sorted(
        (m for m in calendar.calendar(today, today + timedelta(days=1)) if streams_today(m, today)),
        key=lambda m: m.title,
    )
    if not movies:
        return None
    return {"stale": False, "items": [_item(m, posters) for m in movies]}


def _item(m: RadarrMovie, posters: PosterSource) -> dict[str, Any]:
    return {
        "title": m.title,
        "runtime_min": m.runtime_min,
        "poster": poster_uri(posters, m.poster_url) if m.poster_url else None,
    }


def streams_today(movie: RadarrMovie, today: date) -> bool:
    """A monitored movie with its digital release today, not yet grabbed (CONTEXT.md: Streaming)."""
    return movie.monitored and movie.digital_release == today and not movie.grabbed
