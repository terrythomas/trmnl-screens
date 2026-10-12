"""python -m collector [--once] [--screen NAME]"""

import argparse
import logging

from dotenv import load_dotenv

from collector.config import Config
from collector.discovery import discover_screens
from collector.push import push
from collector.runner import run_forever, run_tick


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
    screens = discover_screens()
    if args.screen:
        screens = {args.screen: screens[args.screen]}

    def tick():
        return run_tick(screens, config, push)

    if args.once:
        return 0 if all(tick().values()) else 1
    run_forever(tick, config.interval_minutes * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
