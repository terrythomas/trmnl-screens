"""MLB Stats API source adapter: a team's games with their broadcasts marked home, away or national (ADR-0008)."""

from datetime import date, datetime, timedelta

import httpx

from . import LeagueError, LeagueGame
from .espn import EspnBroadcast

# ESPN abbreviation → MLB team id.
TEAM_IDS = {
    "ARI": 109, "ATH": 133, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112, "CHW": 145, "CIN": 113,
    "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC": 118, "LAA": 108, "LAD": 119, "MIA": 146,
    "MIL": 158, "MIN": 142, "NYM": 121, "NYY": 147, "PHI": 143, "PIT": 134, "SD": 135, "SEA": 136,
    "SF": 137, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141, "WSH": 120,
}

# MLB team names that differ from ESPN's, which the matcher compares.
ESPN_NAMES = {"D-backs": "Diamondbacks"}

# Days either side of today, so the game window is covered whatever the time zone of the venue's official date.
WINDOW = timedelta(days=2)


class MlbError(LeagueError):
    """A failed MLB Stats API request. The message never contains the URL (ADR-0003)."""


class MlbSource:
    """Read fresh on every run: one small request per followed team, since channels can change on game day."""

    def __init__(self, now: datetime, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url="https://statsapi.mlb.com/api/v1", timeout=30, transport=transport)
        self._today: date = now.date()
        self._asked: dict[str, list[LeagueGame] | MlbError] = {}  # this run's answers, failures included

    def season(self, team: str) -> list[LeagueGame]:
        """The games around today of the team with ESPN abbreviation `team`."""
        if team not in self._asked:
            try:
                self._asked[team] = self._schedule(team)
            except MlbError as e:
                self._asked[team] = e
        found = self._asked[team]
        if isinstance(found, MlbError):
            raise found
        return found

    def _schedule(self, team):
        if team not in TEAM_IDS:
            raise MlbError(f"no MLB team id for {team}")
        params = {"sportId": 1, "teamId": TEAM_IDS[team], "startDate": (self._today - WINDOW).isoformat(),
                  "endDate": (self._today + WINDOW).isoformat(), "hydrate": "broadcasts(all),team"}
        try:
            response = self._client.get("/schedule", params=params)
            response.raise_for_status()
            return [_game(g) for d in response.json()["dates"] for g in d["games"]]
        except httpx.HTTPStatusError as e:
            raise MlbError(f"MLB Stats API returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise MlbError(f"MLB Stats API request failed: {type(e).__name__}") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise MlbError("MLB Stats API returned an unexpected response") from None


def _game(g: dict) -> LeagueGame:
    name = {side: g["teams"][side]["team"]["teamName"] for side in ("home", "away")}
    return LeagueGame(
        start=datetime.fromisoformat(g["gameDate"]),
        home=ESPN_NAMES.get(name["home"], name["home"]),
        away=ESPN_NAMES.get(name["away"], name["away"]),
        broadcasts=tuple(_broadcast(b) for b in g.get("broadcasts", [])),
    )


def _broadcast(b: dict) -> EspnBroadcast:
    # National games are listed once per side, so isNational is checked before homeAway.
    market = "National" if b["isNational"] else b["homeAway"].capitalize()
    # Streaming exclusives come as national "TV"; AM and FM are radio.
    return EspnBroadcast(b["name"], "Radio" if b["type"] in ("AM", "FM") else b["type"], market)
