"""Posters for every section: grayscale through Plex's transcoder, inlined as data: URIs (ADR-0002)."""

import base64
import logging
from typing import Protocol

from .sources.plex import PlexError

log = logging.getLogger(__name__)

# Device pixels for the posters approved in the layout prototype (#5).
POSTER_SIZE = (234, 351)


class PosterSource(Protocol):
    def poster(self, path: str, width: int, height: int) -> bytes: ...


def poster_uri(posters: PosterSource, path: str) -> str | None:
    """The poster as a data: URI, or None when Plex can't make it: a row without a poster beats no row."""
    try:
        return "data:image/jpeg;base64," + base64.b64encode(posters.poster(path, *POSTER_SIZE)).decode()
    except PlexError as e:
        log.warning("poster skipped: %s", e)
        return None
