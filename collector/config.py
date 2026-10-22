"""Runner configuration, read from environment variables."""

import os
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Config:
    larapaper_url: str
    webhook_uuids: Mapping[str, str] = field(default_factory=dict)
    # INTERVAL_MINUTES, for every screen; None when unset.
    interval_minutes: int | None = None
    # <SCREEN>_INTERVAL_MINUTES, e.g. MEDIA_INTERVAL_MINUTES.
    screen_intervals: Mapping[str, int] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        env = os.environ if env is None else env
        global_interval = env.get("INTERVAL_MINUTES")
        return cls(
            larapaper_url=env["LARAPAPER_URL"].rstrip("/"),
            # Each screen's webhook lives in <SCREEN>_WEBHOOK_UUID, e.g. MEDIA_WEBHOOK_UUID.
            webhook_uuids=_per_screen(env, "_WEBHOOK_UUID"),
            interval_minutes=int(global_interval) if global_interval else None,
            screen_intervals={
                screen: int(value) for screen, value in _per_screen(env, "_INTERVAL_MINUTES").items()
            },
        )

    def webhook_url(self, screen: str) -> str | None:
        uuid = self.webhook_uuids.get(_key(screen))
        return f"{self.larapaper_url}/api/custom_plugins/{uuid}" if uuid else None

    def interval_minutes_for(self, screen: str, default: int | None) -> int:
        """The screen's own setting, then the global one, then the screen's default, then 15."""
        for minutes in (self.screen_intervals.get(_key(screen)), self.interval_minutes, default):
            if minutes is not None:
                return minutes
        return 15


def _per_screen(env: Mapping[str, str], suffix: str) -> dict[str, str]:
    """Collect <SCREEN><suffix> variables into {screen: value}, skipping empty ones."""
    return {
        key[: -len(suffix)].lower(): value
        for key, value in env.items()
        if key.endswith(suffix) and value
    }


def _key(screen: str) -> str:
    # Variable names can't hold "-", so the game-time screen reads GAME_TIME_*.
    return screen.replace("-", "_")
