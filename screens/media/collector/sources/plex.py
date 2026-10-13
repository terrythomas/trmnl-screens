"""Plex source adapter for Continue Watching."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx


@dataclass(frozen=True)
class PlexItem:
    kind: Literal["episode", "movie"]
    title: str  # the show's title for an episode
    season: int | None
    number: int | None
    episode_title: str | None
    duration_ms: int
    view_offset_ms: int | None
    last_viewed_at: datetime | None
    show_key: str | None
    poster_path: str  # the show's poster for an episode


@dataclass(frozen=True)
class ShowHistory:
    # None when no episode of the show was ever watched. Plex's viewedLeafCount can't tell us
    # that: it only counts episodes still in the library, and watched ones are often deleted.
    last_viewed_at: datetime | None


class PlexError(Exception):
    """A failed Plex request. The message never contains the URL or token (ADR-0003)."""


class PlexSource:
    def __init__(self, url: str, token: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"X-Plex-Token": token, "Accept": "application/json"},
            timeout=30,
            transport=transport,
        )

    def continue_watching(self) -> list[PlexItem]:
        container = self._get("/hubs/continueWatching/items")
        try:
            return [_item(m) for m in container.get("Metadata", [])]
        except (KeyError, TypeError) as e:
            raise PlexError(f"unexpected Continue Watching item: missing {e}") from None

    def show_history(self, show_key: str) -> ShowHistory:
        try:
            show = self._get(f"/library/metadata/{show_key}")["Metadata"][0]
        except (KeyError, IndexError):
            raise PlexError("Plex returned no show for an episode") from None
        return ShowHistory(last_viewed_at=_time(show.get("lastViewedAt")))

    def poster(self, path: str, width: int, height: int) -> bytes:
        """A grayscale JPEG of the image at path, resized by Plex's transcoder."""
        return self._request("/photo/:/transcode", params={
            "url": path, "width": width, "height": height,
            "saturation": 0, "minSize": 1, "upscale": 1, "format": "jpeg",
        }).content

    def _get(self, path: str) -> dict:
        try:
            return self._request(path).json()["MediaContainer"]
        except (ValueError, KeyError, TypeError):
            raise PlexError("Plex returned an unexpected response") from None

    def _request(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            raise PlexError(f"Plex returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL, and Plex URLs can carry the token.
            raise PlexError(f"Plex request failed: {type(e).__name__}") from None


def _item(m: dict) -> PlexItem:
    episode = m["type"] == "episode"
    return PlexItem(
        kind=m["type"],
        title=m["grandparentTitle"] if episode else m["title"],
        season=m.get("parentIndex") if episode else None,
        number=m.get("index") if episode else None,
        episode_title=m["title"] if episode else None,
        duration_ms=m["duration"],
        view_offset_ms=m.get("viewOffset"),
        last_viewed_at=_time(m.get("lastViewedAt")),
        show_key=m["grandparentRatingKey"] if episode else None,
        poster_path=m["grandparentThumb"] if episode else m["thumb"],
    )


def _time(epoch: int | None) -> datetime | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc)
