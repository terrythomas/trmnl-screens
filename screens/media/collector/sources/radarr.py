"""Radarr source adapter for Releasing Today."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx


@dataclass(frozen=True)
class RadarrMovie:
    title: str
    year: int
    in_cinemas: date | None
    digital_release: date | None
    grabbed: bool
    monitored: bool
    runtime_min: int | None  # None when Radarr does not know it yet
    poster_url: str | None  # public artwork URL, never a Radarr address


class RadarrError(Exception):
    """A failed Radarr request. The message never contains the URL or API key (ADR-0003)."""


class RadarrSource:
    def __init__(self, url: str, api_key: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"X-Api-Key": api_key},
            timeout=30,
            transport=transport,
        )

    def calendar(self, day: date) -> list[RadarrMovie]:
        """Movies with any release date on day (Radarr may also return neighbours)."""
        try:
            # Explicit UTC midnights: Radarr reads a bare date in the server's own zone, which
            # would start the range after the midnight-UTC release dates and miss them.
            response = self._client.get("/api/v3/calendar", params={
                "start": f"{day.isoformat()}T00:00:00Z", "end": f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z",
            })
            response.raise_for_status()
            return [_movie(m) for m in response.json()]
        except httpx.HTTPStatusError as e:
            raise RadarrError(f"Radarr returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise RadarrError(f"Radarr request failed: {type(e).__name__}") from None
        except (ValueError, KeyError, TypeError):
            raise RadarrError("Radarr returned an unexpected response") from None


def _movie(m: dict) -> RadarrMovie:
    return RadarrMovie(
        title=m["title"],
        year=m["year"],
        in_cinemas=_date(m.get("inCinemas")),
        digital_release=_date(m.get("digitalRelease")),
        grabbed=m["hasFile"],
        monitored=m["monitored"],
        runtime_min=m.get("runtime") or None,
        poster_url=next((i.get("remoteUrl") for i in m.get("images", []) if i.get("coverType") == "poster"), None),
    )


def _date(value: str | None) -> date | None:
    # Radarr stores release dates as midnight UTC. Taking the date part keeps the calendar
    # day; converting to local time would move it to the evening before west of UTC.
    return None if value is None else datetime.fromisoformat(value).date()
