"""ESPN site API source adapter: scoreboards and team lists for every league."""

from dataclasses import dataclass
from datetime import date, datetime

import httpx

# The path of each league under ESPN's /sports.
SPORTS = {
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "mls": "soccer/usa.1",
}


@dataclass(frozen=True)
class EspnTeam:
    abbr: str
    name: str
    logo_url: str | None
    score: int | None  # ESPN sends 0 before the start; the collector decides when it counts
    home: bool


@dataclass(frozen=True)
class EspnBroadcast:
    name: str
    type: str  # "TV", "Streaming", "Radio" or "Subscription Package"
    market: str  # "National", "Home" or "Away"


@dataclass(frozen=True)
class EspnGame:
    id: str
    start: datetime
    status: str  # ESPN's status name, e.g. STATUS_IN_PROGRESS
    state: str  # ESPN's "pre", "in" or "post"
    detail: str  # ESPN's short detail, e.g. "5:12 - 3rd"
    home: EspnTeam
    away: EspnTeam
    broadcasts: tuple[EspnBroadcast, ...]


class EspnError(Exception):
    """A failed ESPN request. The message never contains the URL (ADR-0003)."""


class EspnSource:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url="https://site.api.espn.com/apis/site/v2/sports", timeout=30, transport=transport,
        )

    def scoreboard(self, league: str, day: date) -> list[EspnGame]:
        """The league's games on ESPN's date `day`, which is not necessarily the local date."""
        return self._get(f"/{SPORTS[league]}/scoreboard", {"dates": day.strftime("%Y%m%d")},
                         lambda body: [_game(e) for e in body["events"]])

    def teams(self, league: str) -> set[str]:
        """Every team abbreviation in the league."""
        return self._get(f"/{SPORTS[league]}/teams", {},
                         lambda body: {t["team"]["abbreviation"] for t in body["sports"][0]["leagues"][0]["teams"]})

    def _get(self, path, params, parse):
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            return parse(response.json())
        except httpx.HTTPStatusError as e:
            raise EspnError(f"ESPN returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise EspnError(f"ESPN request failed: {type(e).__name__}") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise EspnError("ESPN returned an unexpected response") from None


def _game(e: dict) -> EspnGame:
    competition = e["competitions"][0]
    teams = {c["homeAway"]: _team(c) for c in competition["competitors"]}
    status = e["status"]["type"]
    return EspnGame(
        id=e["id"],
        start=datetime.fromisoformat(e["date"]),
        status=status["name"],
        state=status["state"],
        detail=status.get("shortDetail", ""),
        home=teams["home"],
        away=teams["away"],
        broadcasts=tuple(
            EspnBroadcast(b["media"]["shortName"], b["type"]["shortName"], b["market"]["type"])
            for b in competition.get("geoBroadcasts", [])
        ),
    )


def _team(c: dict) -> EspnTeam:
    team = c["team"]
    return EspnTeam(
        abbr=team["abbreviation"],
        name=team["name"],
        logo_url=team.get("logo"),
        score=int(c["score"]) if c.get("score") not in (None, "") else None,
        home=c["homeAway"] == "home",
    )
