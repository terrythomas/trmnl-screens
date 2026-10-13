"""Continue Watching section: item state, order, cap and payload mapping (spec: Continue Watching)."""

from datetime import datetime, timedelta
from typing import Any, Protocol

from .posters import poster_uri
from .sources.plex import PlexItem, ShowHistory

STATE_ORDER = {"new": 0, "in_progress": 1, "next": 2}


class Source(Protocol):
    def continue_watching(self) -> list[PlexItem]: ...
    def show_history(self, show_key: str) -> ShowHistory: ...
    def poster(self, path: str, width: int, height: int) -> bytes: ...


def continue_watching(source: Source, now: datetime, new_after_days: int = 30, limit: int = 12) -> dict[str, Any] | None:
    """The Continue Watching section of the payload, or None when there is nothing to show."""
    items = source.continue_watching()
    if not items:
        return None
    shows: dict[str, ShowHistory] = {}

    def show_of(item: PlexItem) -> ShowHistory | None:
        # Only unstarted episodes need their show's history, and each show is fetched once.
        if item.kind != "episode" or item.view_offset_ms is not None:
            return None
        if item.show_key not in shows:
            shows[item.show_key] = source.show_history(item.show_key)
        return shows[item.show_key]

    states = [item_state(item, show_of(item), now, timedelta(days=new_after_days)) for item in items]
    ordered = sorted(zip(items, states), key=_order)
    return {
        "stale": False,
        "total": len(items),
        "items": [_payload(item, state, source, now) for item, state in ordered[:limit]],
    }


def _order(entry: tuple[PlexItem, str]) -> tuple:
    """Item state, then neglect order (ADR-0004). Never-viewed items come first; sorted() keeps ties in Plex's order."""
    item, state = entry
    viewed = item.last_viewed_at
    return (STATE_ORDER[state], viewed is not None, viewed or datetime.min)


def item_state(item: PlexItem, show: ShowHistory | None, now: datetime, new_after: timedelta) -> str:
    """The item's state: "in_progress", "new" or "next" (CONTEXT.md: Item state).

    show is the episode's show history, given only for unstarted episodes (None otherwise).
    """
    if item.view_offset_ms is not None:
        return "in_progress"
    if item.kind == "movie" or show.last_viewed_at is None:
        return "new"
    if item.number == 1 and now - show.last_viewed_at >= new_after:
        return "new"
    return "next"


def _payload(item: PlexItem, state: str, source: Source, now: datetime) -> dict[str, Any]:
    in_progress = state == "in_progress"
    return {
        "kind": item.kind,
        "state": state,
        "title": item.title,
        "episode": (
            {"season": item.season, "number": item.number, "title": item.episode_title}
            if item.kind == "episode" else None
        ),
        "duration_min": round(item.duration_ms / 60_000),
        "progress": round(100 * item.view_offset_ms / item.duration_ms) if in_progress else None,
        "remaining_min": round((item.duration_ms - item.view_offset_ms) / 60_000) if in_progress else None,
        "last_viewed": item.last_viewed_at.astimezone(now.tzinfo).date().isoformat() if item.last_viewed_at else None,
        "poster": poster_uri(source, item.poster_path),
    }
