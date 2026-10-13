"""Runs every screen's collector and pushes the result to its webhook."""

import logging
import time
from typing import Callable

from collector.config import Config
from collector.discovery import Collect
from collector.push import Push

log = logging.getLogger(__name__)


def enabled_screens(screens: dict[str, Collect], config: Config) -> dict[str, Collect]:
    """Keep the screens that have a webhook. A screen is opt-in: no webhook UUID means off."""
    enabled = {}
    for name, collect in screens.items():
        if config.webhook_url(name) is None:
            log.info("screen %s: off (set %s_WEBHOOK_UUID to enable it)", name, name.upper())
        else:
            enabled[name] = collect
    return enabled


def run_tick(screens: dict[str, Collect], config: Config, push: Push) -> dict[str, bool]:
    """Run each screen once. A failing screen is logged and never blocks the others."""
    results = {}
    for name, collect in screens.items():
        url = config.webhook_url(name)
        if url is None:
            log.warning("screen %s: no %s_WEBHOOK_UUID set, skipping", name, name.upper())
            results[name] = False
            continue
        try:
            push(url, collect())
        except Exception:
            # A failed push is retried on the next tick (spec: empty and failure behaviour).
            log.exception("screen %s: collect or push failed", name)
            results[name] = False
        else:
            log.info("screen %s: pushed", name)
            results[name] = True
    return results


def run_forever(
    tick: Callable[[], object],
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Call tick() now, then again interval_seconds after each tick ends.

    Fixed delay: start times drift by the tick's duration, which doesn't matter
    for data this slow-moving. Unexpected errors are not caught: run_tick already
    contains per-screen failures, so anything reaching here is a bug, and the
    process should exit and let the container restart it.
    """
    while True:
        tick()
        sleep(interval_seconds)
