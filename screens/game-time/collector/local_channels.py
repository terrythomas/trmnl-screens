"""League sources' TV channels in place of ESPN's (spec: Channels, ADR-0008)."""

import logging
from dataclasses import replace
from datetime import timezone
from typing import Protocol

from .sources import LeagueError, LeagueGame
from .sources.espn import EspnGame

log = logging.getLogger(__name__)


class LeagueSource(Protocol):
    def season(self, team: str) -> list[LeagueGame]:
        """The games of the team with ESPN abbreviation `team`; raises a LeagueError."""
        ...


def local_channels(source: LeagueSource, league: str, g: EspnGame, teams: set[str]) -> tuple[EspnGame, bool]:
    """`g` with the source's TV channels instead of ESPN's, and whether it fell back to ESPN's (channels_incomplete)."""
    team = g.home if g.home.abbr in teams else g.away
    try:
        season = source.season(team.abbr)
    except LeagueError as e:
        log.warning("%s channels for %s: %s; using ESPN's", league, team.abbr, e)
        return g, True
    day = g.start.astimezone(timezone.utc).date()
    candidates = [
        s for s in season
        if (s.home, s.away) == (g.home.name, g.away.name) and s.start.astimezone(timezone.utc).date() == day
    ]
    if not candidates:
        log.warning("%s channels: no match for %s @ %s on %s; using ESPN's", league, g.away.abbr, g.home.abbr, day)
        return g, True
    # Same-day games between the same teams (doubleheaders): the closest start wins.
    match = min(candidates, key=lambda s: abs(s.start - g.start))
    # ESPN's streaming and packages stay; the source's channels come first, so they win a tie.
    return replace(g, broadcasts=match.broadcasts + tuple(b for b in g.broadcasts if b.type != "TV")), False
