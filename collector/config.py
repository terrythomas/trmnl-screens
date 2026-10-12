"""Runner configuration, read from environment variables."""

import os
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Config:
    larapaper_url: str
    interval_minutes: int = 15
    webhook_uuids: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        env = os.environ if env is None else env
        # Each screen's webhook lives in <SCREEN>_WEBHOOK_UUID, e.g. MEDIA_WEBHOOK_UUID.
        suffix = "_WEBHOOK_UUID"
        webhooks = {
            key[: -len(suffix)].lower(): value
            for key, value in env.items()
            if key.endswith(suffix) and value
        }
        return cls(
            larapaper_url=env["LARAPAPER_URL"].rstrip("/"),
            interval_minutes=int(env.get("INTERVAL_MINUTES") or 15),
            webhook_uuids=webhooks,
        )

    def webhook_url(self, screen: str) -> str | None:
        uuid = self.webhook_uuids.get(screen)
        return f"{self.larapaper_url}/api/custom_plugins/{uuid}" if uuid else None
