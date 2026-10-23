"""Game Time screen collector: builds the payload described in docs/specs/game-time-screen.md."""

import json
import logging
import os
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from collector.sections import Section, collect_sections

from .channels import record_unknown
from .games import games, parse_teams
from .sources.espn import EspnError, EspnSource

log = logging.getLogger(__name__)

# Default minutes between runs; GAME_TIME_INTERVAL_MINUTES or INTERVAL_MINUTES override it.
INTERVAL_MINUTES = 60


def collect() -> dict[str, Any]:
    # The team list lives in its own file next to .env; real environment variables win.
    load_dotenv("game-time.env")
    now = datetime.now().astimezone()
    followed = parse_teams(os.environ["GAME_TIME_TEAMS"])
    state_dir = Path(os.environ.get("STATE_DIR") or "state")
    espn = EspnSource()
    teams = _team_lists(espn, state_dir / "game-time" / "teams.json", now)
    # One section per league, so a failing league shows its last good games while the others stay fresh.
    sections = {
        league: Section(f"espn-{league}", lambda league=league, abbrs=abbrs: _league(espn, league, abbrs, now))
        for league, abbrs in followed.items()
    }
    # One per entry, so an unknown team gets a banner entry with a since, like a failing source.
    for league, abbrs in followed.items():
        for abbr in sorted(abbrs):
            sections[f"{league}:{abbr}"] = Section(
                f"unknown-team:{league}:{abbr.lower()}", lambda league=league, abbr=abbr: _check_team(teams, league, abbr),
            )
    payload = collect_sections(sections, state_dir / "game-time" / "games.json", now)
    found = [
        {**g, "stale": True} if payload[league].get("stale") else g
        for league in followed if league in payload for g in payload[league]["games"]
    ]
    found.sort(key=lambda g: datetime.fromisoformat(g["start"]))
    record_unknown(state_dir / "game-time" / "unknown-channels.json", found, now)
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "games": found,
        "logos": {}, "logos1": {}, "logos1h": {},
        "icons": {}, "icons1": {}, "icons1h": {},
        "errors": payload["errors"],
    }


def next_run_minutes(payload: dict[str, Any]) -> int | None:
    """5 while any game is live or starts within 5 minutes (spec: Schedule), else the interval."""
    soon = datetime.fromisoformat(payload["updated_at"]) + timedelta(minutes=5)
    for game in payload["games"]:
        # A scheduled game past its start, such as a delayed one, counts as starting soon.
        if game["state"] == "live" or game["state"] == "scheduled" and datetime.fromisoformat(game["start"]) <= soon:
            return 5
    return None


def _league(espn, league, abbrs, now):
    found = games(espn, {league: abbrs}, now)
    return {"games": found} if found else None


def _team_lists(espn, path, now):
    """Each league's ESPN team list, cached in `path` and fetched again once a day."""
    try:
        cached = json.loads(path.read_text())
    except FileNotFoundError:
        cached = {}
    except ValueError:
        log.warning("team list cache %s is unreadable, starting fresh", path.name)
        cached = {}

    @cache  # one lookup per league per run
    def teams(league):
        entry = cached.get(league)
        if entry and now - datetime.fromisoformat(entry["fetched"]) < timedelta(days=1):
            return set(entry["teams"])
        try:
            found = espn.teams(league)
        except EspnError as e:
            if not entry:
                raise
            # An old list still knows the followed teams; only no list at all counts as ESPN down.
            log.warning("%s team list: %s; using the cached list", league, e)
            return set(entry["teams"])
        cached[league] = {"fetched": now.isoformat(timespec="seconds"), "teams": sorted(found)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached))
        return found

    return teams


def _check_team(teams, league, abbr):
    try:
        known = teams(league)
    except EspnError as e:
        e.source = f"espn-{league}"  # ESPN being down doesn't make the team unknown
        raise
    if abbr not in known:
        raise LookupError(f"{league}:{abbr.lower()} matches no ESPN team")
