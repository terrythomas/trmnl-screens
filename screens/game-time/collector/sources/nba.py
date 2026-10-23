"""nba.com source adapter: each team's season and TV channels, from its schedule page (ADR-0008)."""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from . import LeagueError, LeagueGame
from .espn import EspnBroadcast

log = logging.getLogger(__name__)

# ESPN abbreviation → nba.com team id, which names the team's page.
TEAM_IDS = {
    "ATL": 1610612737, "BKN": 1610612751, "BOS": 1610612738, "CHA": 1610612766, "CHI": 1610612741,
    "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765, "GS": 1610612744,
    "HOU": 1610612745, "IND": 1610612754, "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763,
    "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750, "NO": 1610612740, "NY": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756, "POR": 1610612757,
    "SA": 1610612759, "SAC": 1610612758, "TOR": 1610612761, "UTAH": 1610612762, "WSH": 1610612764,
}

# The page's TV lists → ESPN's market names. Radio and the teams' own apps (OTT) are left out.
MARKETS = {"nationalBroadcasters": "National", "homeTvBroadcasters": "Home", "awayTvBroadcasters": "Away"}

# nba.com answers a descriptive User-Agent with HTTP 403.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


class NbaError(LeagueError):
    """A failed nba.com request. The message never contains the URL (ADR-0003)."""


class NbaSource:
    """Seasons cached in `path` and read again once a day, since a page carries the whole season."""

    def __init__(self, path: Path, now: datetime, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url="https://www.nba.com", timeout=30, transport=transport, headers={"User-Agent": USER_AGENT},
        )
        self._path, self._now = path, now
        self._asked: dict[str, list[LeagueGame] | NbaError] = {}  # this run's answers, failures included

    def season(self, team: str) -> list[LeagueGame]:
        """The season of the team with ESPN abbreviation `team`."""
        if team not in self._asked:
            try:
                self._asked[team] = self._season(team)
            except NbaError as e:
                self._asked[team] = e
        found = self._asked[team]
        if isinstance(found, NbaError):
            raise found
        return found

    def _season(self, team):
        cached = self._load()
        entry = cached.get(team)
        if entry and self._now - datetime.fromisoformat(entry["fetched"]) < timedelta(days=1):
            return [_from_json(g) for g in entry["games"]]
        if team not in TEAM_IDS:
            raise NbaError(f"no nba.com page for {team}")
        found = self._get(f"/team/{TEAM_IDS[team]}/schedule")
        cached[team] = {"fetched": self._now.isoformat(timespec="seconds"), "games": [_to_json(g) for g in found]}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(cached))
        return found

    def _load(self):
        try:
            return json.loads(self._path.read_text())
        except FileNotFoundError:
            return {}
        except ValueError:
            log.warning("nba.com cache %s is unreadable, starting fresh", self._path.name)
            return {}

    def _get(self, path):
        try:
            response = self._client.get(path)
            response.raise_for_status()
            return _parse(response.text)
        except httpx.HTTPStatusError as e:
            raise NbaError(f"nba.com returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise NbaError(f"nba.com request failed: {type(e).__name__}") from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise NbaError("nba.com returned an unexpected page") from None


def _parse(page: str) -> list[LeagueGame]:
    # The page embeds the team's season as Next.js page data.
    schedule = json.loads(_NEXT_DATA.search(page).group(1))["props"]["pageProps"]["team"]["schedule"]
    return [
        LeagueGame(
            start=datetime.fromisoformat(g["gameDateTimeUTC"]),
            home=g["homeTeam"]["teamName"],
            away=g["awayTeam"]["teamName"],
            broadcasts=tuple(
                EspnBroadcast(b["broadcasterDisplay"], "TV", market)
                for key, market in MARKETS.items() for b in g["broadcasters"][key]
            ),
        )
        for g in schedule
    ]


def _to_json(g: LeagueGame) -> dict:
    return {"start": g.start.isoformat(), "home": g.home, "away": g.away,
            "broadcasts": [[b.name, b.type, b.market] for b in g.broadcasts]}


def _from_json(g: dict) -> LeagueGame:
    return LeagueGame(datetime.fromisoformat(g["start"]), g["home"], g["away"],
                      tuple(EspnBroadcast(*b) for b in g["broadcasts"]))
