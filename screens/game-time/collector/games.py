"""Followed teams and the games in the game window (spec: Followed teams, Games)."""

from datetime import datetime, timedelta, tzinfo
from typing import Any, Protocol

from .channels import select
from .sources.espn import SPORTS, EspnGame, EspnTeam

POSTPONED = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_SUSPENDED"}
STATES = {"pre": "scheduled", "in": "live", "post": "final"}


class Scoreboard(Protocol):
    def scoreboard(self, league: str, day) -> list[EspnGame]: ...


def parse_teams(value: str) -> dict[str, set[str]]:
    """GAME_TIME_TEAMS, e.g. "nba:bos, nfl:chi", as {league: {abbreviation}}."""
    followed: dict[str, set[str]] = {}
    for entry in filter(None, (e.strip() for e in value.split(","))):
        league, _, abbr = entry.lower().partition(":")
        if league not in SPORTS or not abbr:
            raise ValueError(f"GAME_TIME_TEAMS: {entry!r} is not league:team, with a league of {', '.join(SPORTS)}")
        followed.setdefault(league, set()).add(abbr.upper())
    return followed


def games(espn: Scoreboard, followed: dict[str, set[str]], now: datetime, tz: tzinfo | None = None) -> list[dict[str, Any]]:
    """The followed teams' games in the game window, sorted by start. tz None is the system's zone."""
    today = now.date()
    yesterday, tomorrow = today - timedelta(days=1), today + timedelta(days=1)
    found: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
    for league, teams in followed.items():
        for day in (yesterday, today, tomorrow):
            for g in espn.scoreboard(league, day):
                if g.home.abbr in teams or g.away.abbr in teams:
                    # Keyed by event, so a game on two days' scoreboards is one game.
                    found[league, g.id] = g.start, _game(league, g, teams, tz)
    window = {today.isoformat(), tomorrow.isoformat()}
    return [
        game for _, game in sorted(found.values(), key=lambda pair: pair[0])
        if game["local_date"] in window
        or game["local_date"] == yesterday.isoformat() and game["state"] == "live"
    ]


def _game(league: str, g: EspnGame, teams: set[str], tz: tzinfo | None) -> dict[str, Any]:
    # When both teams are followed, the home team is `followed`.
    followed, opponent = (g.home, g.away) if g.home.abbr in teams else (g.away, g.home)
    state = "postponed" if g.status in POSTPONED else STATES[g.state]
    scored = state in ("live", "final")
    # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
    start = g.start.astimezone(tz)
    return {
        "league": league,
        "start": start.isoformat(timespec="seconds"),
        "local_date": start.date().isoformat(),
        "state": state,
        "status": g.detail if state == "live" else None,
        "followed": _team(followed, scored),
        "opponent": _team(opponent, scored),
        "both_followed": g.home.abbr in teams and g.away.abbr in teams,
        "channels": [] if state == "postponed" else [
            {"name": name, "icon": False}  # the logo store sets icon (#60)
            for name in select(g.broadcasts, league, {"Home" if t.home else "Away" for t in (g.home, g.away) if t.abbr in teams})
        ],
        "channels_incomplete": False,
        "stale": False,
        "featured": False,
    }


def _team(team: EspnTeam, scored: bool) -> dict[str, Any]:
    return {
        "abbr": team.abbr,
        "name": team.name,
        "logo": None,  # the logo store fills this in (#60)
        "score": team.score if scored else None,
        "home": team.home,
    }
