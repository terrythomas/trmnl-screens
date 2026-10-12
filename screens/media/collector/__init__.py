"""Media screen collector: builds the payload described in docs/specs/media-screen.md."""

from datetime import datetime
from typing import Any


def collect() -> dict[str, Any]:
    # Local time with offset; the template formats it as-is (LaraPaper can't convert zones).
    return {"updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
