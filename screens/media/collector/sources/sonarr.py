"""Sonarr source adapter for Airing."""

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class SonarrEpisode:
    series: str
    series_id: int
    season: int
    number: int
    title: str | None
    air_time: datetime
    runtime_min: int | None  # None when Sonarr does not know it yet
    grabbed: bool
    monitored: bool
    series_monitored: bool
    finale: str | None  # Sonarr's finaleType: "series", "season" or "midseason"
    poster_url: str | None  # public artwork URL, never a Sonarr address


class SonarrError(Exception):
    """A failed Sonarr request. The message never contains the URL or API key (ADR-0003)."""


class SonarrSource:
    def __init__(self, url: str, api_key: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"X-Api-Key": api_key},
            timeout=30,
            transport=transport,
        )

    def calendar(self, start: datetime, end: datetime) -> list[SonarrEpisode]:
        try:
            response = self._client.get("/api/v3/calendar", params={
                "start": _utc(start), "end": _utc(end), "includeSeries": "true",
            })
            response.raise_for_status()
            return [_episode(e) for e in response.json()]
        except httpx.HTTPStatusError as e:
            raise SonarrError(f"Sonarr returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise SonarrError(f"Sonarr request failed: {type(e).__name__}") from None
        except (ValueError, KeyError, TypeError):
            raise SonarrError("Sonarr returned an unexpected response") from None


def _episode(e: dict) -> SonarrEpisode:
    series = e["series"]
    return SonarrEpisode(
        series=series["title"],
        series_id=e["seriesId"],
        season=e["seasonNumber"],
        number=e["episodeNumber"],
        title=e.get("title"),
        air_time=datetime.fromisoformat(e["airDateUtc"]),
        runtime_min=e.get("runtime") or series.get("runtime") or None,
        grabbed=e["hasFile"],
        monitored=e["monitored"],
        series_monitored=series["monitored"],
        finale=e.get("finaleType"),
        poster_url=next((i.get("remoteUrl") for i in series.get("images", []) if i.get("coverType") == "poster"), None),
    )


def _utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
