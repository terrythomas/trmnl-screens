"""Runs every screen's collector and pushes the result to its webhook."""

import logging
import time
from typing import Callable, TypeVar

from collector.config import Config
from collector.discovery import Collect, NextRun
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


def run_tick(
    screens: dict[str, Collect],
    config: Config,
    push: Push,
    merge_strategies: dict[str, str | None] | None = None,
    next_runs: dict[str, NextRun | None] | None = None,
    sooner: dict[str, float] | None = None,
) -> dict[str, bool]:
    """Run each screen once. A failing screen is logged and never blocks the others.

    A screen with a next_runs entry is asked, after a successful push, when it wants to
    run next; an answer in minutes goes into sooner, in seconds, for run_forever.
    """
    merge_strategies = merge_strategies or {}
    next_runs = next_runs or {}
    results = {}
    for name, collect in screens.items():
        url = config.webhook_url(name)
        if url is None:
            log.warning("screen %s: no %s_WEBHOOK_UUID set, skipping", name, name.upper())
            results[name] = False
            continue
        try:
            payload = collect()
            push(url, payload, merge_strategies.get(name))
            minutes = next_runs[name](payload) if next_runs.get(name) else None
        except Exception:
            # A failed push is retried on the next tick (spec: empty and failure behaviour).
            log.exception("screen %s: collect or push failed", name)
            results[name] = False
        else:
            log.info("screen %s: pushed", name)
            results[name] = True
            if minutes is not None and sooner is not None:
                sooner[name] = minutes * 60
    return results


def run_forever(
    intervals: dict[str, float],
    run: Callable[[list[str]], dict[str, float] | None],
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Run every screen now, then each one again its own interval (in seconds) after its run ends.

    run may return, per screen, seconds until that screen's next run; it is used when
    sooner than the interval and ignored when later.

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
            asked = run(due) or {}
            ended = clock()
            for name in due:
                next_due[name] = ended + min(intervals[name], asked.get(name, intervals[name]))
        sleep(max(0.0, min(next_due.values()) - clock()))
