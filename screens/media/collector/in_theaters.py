"""In Theaters section: the theater run rule and payload mapping (spec: In Theaters)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal, Protocol

from .posters import PosterSource, poster_uri
from .sources.radarr import RadarrMovie
from .sources.tmdb import Release

# Radarr's inCinemas is the earliest theatrical date in any country; the configured
# country's release can come this long after it.
LOOKBACK = timedelta(days=90)
# A limited run counts only when the wide release follows within this many days.
LIMITED_LEAD = timedelta(days=7)

Stage = Literal["limited", "wide"]


class Calendar(Protocol):
    def calendar(self, start: date, end: date) -> list[RadarrMovie]: ...


class ReleaseDates(Protocol):
    def releases(self, tmdb_id: int, today: date) -> list[Release]: ...


@dataclass(frozen=True)
class Run:
    stage: Stage
    since: date  # the date the current stage started: the limited date, then the wide date
    note: str | None  # the limited run's TMDB note, e.g. "IMAX"; None once wide


def in_theaters(calendar: Calendar, tmdb: ReleaseDates, posters: PosterSource, now: datetime) -> dict[str, Any] | None:
    """The In Theaters section of the payload, or None when nothing is in its run."""
    today = now.date()  # now is local time, so this is the local calendar day
    candidates = [
        m for m in calendar.calendar(today - LOOKBACK, today + timedelta(days=1))
        if m.monitored and not m.grabbed and m.in_cinemas and today - LOOKBACK <= m.in_cinemas <= today
    ]
    runs = [(m, run) for m in candidates if (run := theater_run(tmdb.releases(m.tmdb_id, today), today))]
    if not runs:
        return None
    runs.sort(key=lambda r: (-r[1].since.toordinal(), r[0].title))  # newest first
    return {"stale": False, "items": [_item(m, run, today, posters) for m, run in runs]}


def _item(m: RadarrMovie, run: Run, today: date, posters: PosterSource) -> dict[str, Any]:
    return {
        "title": m.title,
        "stage": run.stage,
        "note": run.note,
        "since": run.since.isoformat(),
        "days_ago": (today - run.since).days,
        "runtime_min": m.runtime_min,
        "poster": poster_uri(posters, m.poster_url) if m.poster_url else None,
    }


def theater_run(releases: list[Release], today: date) -> Run | None:
    """The movie's run on today, or None when it isn't in one (CONTEXT.md: In Theaters).

    - The run ends on the Sunday on or after the wide ("Theatrical") release.
    - It starts on the wide release, or earlier on a limited release that comes
      before the wide one by no more than LIMITED_LEAD.
    - No wide release means no run: premieres and limited-only releases don't count.
    """
    wide = min((r.date for r in releases if r.type == "Theatrical"), default=None)
    if wide is None:
        return None
    end = wide + timedelta(days=6 - wide.weekday())  # weekday(): Monday 0 .. Sunday 6
    if wide <= today <= end:
        return Run("wide", wide, None)
    limited = min(
        (r for r in releases if r.type == "Theatrical (limited)" and wide - LIMITED_LEAD <= r.date < wide),
        key=lambda r: r.date, default=None,
    )
    if limited and limited.date <= today < wide:
        return Run("limited", limited.date, limited.note)
    return None
