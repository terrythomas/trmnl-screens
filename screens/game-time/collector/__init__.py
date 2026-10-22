"""Game Time screen collector: builds the payload described in docs/specs/game-time-screen.md."""

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from .games import games, parse_teams
from .sources.espn import EspnSource

# Default minutes between runs; GAME_TIME_INTERVAL_MINUTES or INTERVAL_MINUTES override it.
INTERVAL_MINUTES = 60


def collect() -> dict[str, Any]:
    # The team list lives in its own file next to .env; real environment variables win.
    load_dotenv("game-time.env")
    now = datetime.now().astimezone()
    followed = parse_teams(os.environ["GAME_TIME_TEAMS"])
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "games": games(EspnSource(), followed, now),
        "logos": {}, "logos1": {}, "logos1h": {},
        "icons": {}, "icons1": {}, "icons1h": {},
        "errors": [],
    }
