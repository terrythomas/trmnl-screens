"""How's It Outside? source adapters, and the request handling they share."""

import httpx


class SourceError(Exception):
    """A failed request. The message never contains the URL, a key or the location (ADR-0003)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def get_json(client: httpx.Client, name: str, path: str, **kwargs):
    try:
        response = client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise SourceError(f"{name} returned HTTP {e.response.status_code}", e.response.status_code) from None
    except httpx.HTTPError as e:
        # httpx messages and chained causes can include the URL, and so the location.
        raise SourceError(f"{name} request failed: {type(e).__name__}") from None
    except ValueError:
        raise SourceError(f"{name} returned an unexpected response") from None
