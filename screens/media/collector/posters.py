"""Posters for every section: grayscale through Plex's transcoder, inlined as data: URIs (ADR-0002)."""

import base64
from typing import Protocol

# Device pixels for the posters approved in the layout prototype (#5).
POSTER_SIZE = (234, 351)


class PosterSource(Protocol):
    def poster(self, path: str, width: int, height: int) -> bytes: ...


def poster_uri(posters: PosterSource, path: str) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(posters.poster(path, *POSTER_SIZE)).decode()
