"""Jolpica (Ergast successor) source adapter: the season's schedule, never results (spec: No spoilers)."""

from dataclasses import dataclass
from datetime import datetime

import httpx

# Jolpica's session keys → payload kinds. The race is the race's own date and time.
SESSIONS = {
    "FirstPractice": "practice_1",
    "SecondPractice": "practice_2",
    "ThirdPractice": "practice_3",
    "SprintQualifying": "sprint_qualifying",
    "Sprint": "sprint",
    "Qualifying": "qualifying",
}


@dataclass(frozen=True)
class GrandPrix:
    season: int
    round: int
    name: str
    location: str
    circuit: str  # Jolpica's circuitId
    lat: float
    lon: float
    sessions: tuple[tuple[str, datetime], ...]  # (kind, start in UTC), in start order


class JolpicaError(Exception):
    """A failed Jolpica request. The message never contains the URL (ADR-0003)."""


class JolpicaSource:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url="https://api.jolpi.ca/ergast/f1", timeout=30, transport=transport)

    def season(self, year: int | str = "current") -> tuple[int, list[GrandPrix]]:
        """The season's year, as Jolpica names it, and its Grands Prix; none for a season not yet published."""
        try:
            response = self._client.get(f"/{year}.json")
            response.raise_for_status()
            table = response.json()["MRData"]["RaceTable"]
            return int(table["season"]), [_grand_prix(r) for r in table["Races"]]
        except httpx.HTTPStatusError as e:
            raise JolpicaError(f"Jolpica returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise JolpicaError(f"Jolpica request failed: {type(e).__name__}") from None
        except (ValueError, KeyError, TypeError):
            raise JolpicaError("Jolpica returned an unexpected response") from None


def _grand_prix(r: dict) -> GrandPrix:
    circuit, place = r["Circuit"], r["Circuit"]["Location"]
    sessions = [(kind, _start(r[key])) for key, kind in SESSIONS.items() if key in r]
    sessions.append(("race", _start(r)))
    return GrandPrix(
        season=int(r["season"]),
        round=int(r["round"]),
        name=r["raceName"],
        location=f"{place['locality']}, {place['country']}",
        circuit=circuit["circuitId"],
        lat=float(place["lat"]),
        lon=float(place["long"]),
        sessions=tuple(sorted(sessions, key=lambda s: s[1])),
    )


def _start(entry: dict) -> datetime:
    return datetime.fromisoformat(f"{entry['date']}T{entry['time']}")
