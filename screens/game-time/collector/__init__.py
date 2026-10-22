"""Game Time screen collector: builds the payload described in docs/specs/game-time-screen.md."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .channels import record_unknown
from .games import games, parse_teams
from .sources.espn import EspnSource

# Default minutes between runs; GAME_TIME_INTERVAL_MINUTES or INTERVAL_MINUTES override it.
INTERVAL_MINUTES = 60


def collect() -> dict[str, Any]:
    # The team list lives in its own file next to .env; real environment variables win.
    load_dotenv("game-time.env")
    now = datetime.now().astimezone()
    followed = parse_teams(os.environ["GAME_TIME_TEAMS"])
    found = games(EspnSource(), followed, now)
    record_unknown(Path(os.environ.get("STATE_DIR") or "state") / "game-time" / "unknown-channels.json", found, now)
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "games": found,
        "logos": {}, "logos1": {}, "logos1h": {},
        "icons": {}, "icons1": {}, "icons1h": {},
        "errors": [],
    }


def next_run_minutes(payload: dict[str, Any]) -> int | None:
    """5 while any game is live or starts within 5 minutes (spec: Schedule), else the interval."""
    soon = datetime.fromisoformat(payload["updated_at"]) + timedelta(minutes=5)
    for game in payload["games"]:
        # A scheduled game past its start, such as a delayed one, counts as starting soon.
        if game["state"] == "live" or game["state"] == "scheduled" and datetime.fromisoformat(game["start"]) <= soon:
            return 5
    return None
