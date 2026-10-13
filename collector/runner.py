"""Runs every screen's collector and pushes the result to its webhook."""

import logging
import time
from typing import Callable, TypeVar

from collector.config import Config
from collector.discovery import Collect
from collector.push import Push

log = logging.getLogger(__name__)

T = TypeVar("T")


def enabled_screens(screens: dict[str, T], config: Config) -> dict[str, T]:
    """Keep the screens that have a webhook. A screen is opt-in: no webhook UUID means off."""
    enabled = {}
    for name, screen in screens.items():
        if config.webhook_url(name) is None:
            log.info("screen %s: off (set %s_WEBHOOK_UUID to enable it)", name, name.upper())
        else:
            enabled[name] = screen
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
    intervals: dict[str, float],
    run: Callable[[list[str]], object],
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Run every screen now, then each one again its own interval (in seconds) after its run ends.

    Screens that fall due together run in one call, one after another. Fixed delay:
    start times drift by the run's duration, which doesn't matter for data this
    slow-moving. Unexpected errors are not caught: run_tick already contains
    per-screen failures, so anything reaching here is a bug, and the process
    should exit and let the container restart it.
    """
    start = clock()
    next_due = {name: start for name in intervals}
    while True:
        now = clock()
        due = [name for name, at in next_due.items() if at <= now]
        if due:
            run(due)
            ended = clock()
            for name in due:
                next_due[name] = ended + intervals[name]
        sleep(max(0.0, min(next_due.values()) - clock()))
