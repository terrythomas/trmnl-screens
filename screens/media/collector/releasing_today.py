"""Releasing Today section: the release rule and payload mapping (spec: Releasing Today)."""

from datetime import date, datetime
from typing import Any, Literal, Protocol

from .posters import PosterSource, poster_uri
from .sources.radarr import RadarrMovie

Kind = Literal["theatrical", "digital"]
KIND_ORDER = {"theatrical": 0, "digital": 1}


class Calendar(Protocol):
    def calendar(self, day: date) -> list[RadarrMovie]: ...


def releasing_today(calendar: Calendar, posters: PosterSource, now: datetime) -> dict[str, Any] | None:
    """The Releasing Today section of the payload, or None when nothing releases today."""
    today = now.date()  # now is local time, so this is the local calendar day
    releases = [(m, kind) for m in calendar.calendar(today) if m.monitored and (kind := release_kind(m, today))]
    if not releases:
        return None
    releases.sort(key=lambda release: (KIND_ORDER[release[1]], release[0].title))
    return {"stale": False, "items": [_item(m, kind, posters) for m, kind in releases]}


def _item(m: RadarrMovie, kind: Kind, posters: PosterSource) -> dict[str, Any]:
    return {
        "title": m.title,
        "year": m.year,
        "kind": kind,
        "grabbed": m.grabbed,
        "runtime_min": m.runtime_min,
        "poster": poster_uri(posters, m.poster_url) if m.poster_url else None,
    }


def release_kind(movie: RadarrMovie, today: date) -> Kind | None:
    """How movie releases today: "theatrical", "digital", or None if it doesn't (CONTEXT.md: Releasing Today).

    - A theatrical release today always counts.
    - A digital release today counts only while the movie isn't grabbed.
    - A movie that qualifies both ways is "theatrical".
    """
    if movie.in_cinemas == today:
        return "theatrical"
    if movie.digital_release == today and not movie.grabbed:
        return "digital"
    return None
