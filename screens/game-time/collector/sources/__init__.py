"""Source adapters: the only modules that know about HTTP or API shapes."""

from dataclasses import dataclass
from datetime import datetime

from .espn import EspnBroadcast


@dataclass(frozen=True)
class LeagueGame:
    """A game from a league source (ADR-0008), with the TV channels that replace ESPN's."""
    start: datetime  # exact, so same-day games between the same teams can be told apart
    home: str  # team names as ESPN's EspnTeam.name gives them
    away: str
    broadcasts: tuple[EspnBroadcast, ...]


class LeagueError(Exception):
    """A failed league source request. Each league source's error type subclasses it."""
