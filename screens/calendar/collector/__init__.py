"""Calendar screen collector: keeps the screen re-rendering between calendar syncs (ADR-0007).

The phone pushes the events; this only sends an empty deep merge, which leaves them
untouched but tells LaraPaper the data changed, so the template re-renders against the clock.
"""

from typing import Any

# Default minutes between runs; CALENDAR_INTERVAL_MINUTES or INTERVAL_MINUTES override it.
INTERVAL_MINUTES = 15
MERGE_STRATEGY = "deep_merge"


def collect() -> dict[str, Any]:
    return {}
