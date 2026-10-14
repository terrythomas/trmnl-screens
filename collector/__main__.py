"""python -m collector [--once] [--screen NAME]"""

import argparse
import logging

from dotenv import load_dotenv

from collector.config import Config
from collector.discovery import find_screens, load_screen
from collector.push import push
from collector.runner import enabled_screens, run_forever, run_tick


def main() -> int:
    parser = argparse.ArgumentParser(prog="collector")
    parser.add_argument("--once", action="store_true", help="run one tick and exit")
    parser.add_argument("--screen", help="only run this screen")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs full request URLs, and webhook URLs carry secret UUIDs (ADR-0003).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_dotenv()  # a local .env, if present; real environment variables win
    config = Config.from_env()
    found = enabled_screens(find_screens(), config)
    if args.screen:
        if args.screen not in found:
            parser.error(f"screen {args.screen} is not enabled or does not exist")
        found = {args.screen: found[args.screen]}
    if not found:
        # Fail loudly: a collector that runs but pushes nothing is easy to miss.
        parser.error("no screens enabled: set at least one <SCREEN>_WEBHOOK_UUID")
    screens = {}
    for name, init in found.items():
        try:
            screens[name] = load_screen(name, init)
        except ModuleNotFoundError as e:
            # A missing module of the project's own is a bug, not a missing extra.
            if (e.name or "").split(".")[0] in ("trmnl_screens", "collector"):
                raise
            parser.error(f"screen {name} needs {e.name}: install it with pip install '.[{name}]'")

    def tick(names):
        return run_tick(
            {name: screens[name].collect for name in names}, config, push,
            {name: screens[name].merge_strategy for name in names},
        )

    if args.once:
        return 0 if all(tick(list(screens)).values()) else 1
    intervals = {}
    for name, screen in screens.items():
        minutes = config.interval_minutes_for(name, screen.interval_minutes)
        logging.info("screen %s: every %d minutes", name, minutes)
        intervals[name] = minutes * 60
    run_forever(intervals, tick)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
