"""The channel map, and choosing and ordering a game's channels (spec: Channels, Unknown channels).

No artwork lives here (ADR-0009): an entry only says how a channel is shown.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .sources.espn import EspnBroadcast

log = logging.getLogger(__name__)

# Icon sources, pinned so a change upstream can't change the screen: Simple Icons where it has the
# mark, since it stays cleanest at 1-bit, else the tv-logos collection.
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/{}.svg"
TV_LOGOS = "https://cdn.jsdelivr.net/gh/tv-logo/tv-logos@d32e347bb7c4c640dceec23957802ad9182f58a6/countries/united-states/{}.png"

# Normalised name → entry: its icon's slug in "simple_icons" or "tv_logos", or {"text_only": True} for
# a channel deliberately shown by name. {} is a known channel with no icon source yet.
CHANNELS: dict[str, dict[str, Any]] = {
    "ABC": {"tv_logos": "abc-us"},
    "CBS": {"simple_icons": "cbs"},
    "ESPN": {"tv_logos": "espn-us"},
    "ESPN2": {"tv_logos": "espn-2-us"},
    "ESPNU": {"tv_logos": "espn-u-us"},
    "FOX": {"simple_icons": "fox"},
    "FS1": {"tv_logos": "fox-sports-1-us"},
    "NBC": {"simple_icons": "nbc"},
    "TNT": {"tv_logos": "tnt-us"},
    "TBS": {"tv_logos": "tbs-us"},
    "truTV": {"tv_logos": "tru-tv-us"},
    "NBA TV": {"tv_logos": "nba-tv-us"},
    "NFL Network": {"tv_logos": "nfl-network-us"},
    "MLB Network": {"tv_logos": "mlb-network-us"},
    "NHL Network": {"tv_logos": "nhl-network-us"},
    "ESPN+": {"tv_logos": "espn-plus-us"},
    "Prime Video": {"simple_icons": "primevideo"},
    "Apple TV": {"simple_icons": "appletv"},
    "Paramount+": {"simple_icons": "paramountplus"},
    "Max": {"simple_icons": "max"},
    "YouTube TV": {"simple_icons": "youtubetv"},
    "Peacock": {"text_only": True},
    "MLB.TV": {"text_only": True},
    "NBA League Pass": {"tv_logos": "nba-league-pass-us"},
    "NFL Sunday Ticket": {"text_only": True},
    "NHL Center Ice": {"tv_logos": "nhl-center-ice-us"},
}

# Other source spellings, matched case-insensitively, → the name in CHANNELS.
SPELLINGS = {
    "ESPN Plus": "ESPN+",
    "Amazon Prime Video": "Prime Video",
    "Prime": "Prime Video",
    "Apple TV+": "Apple TV",
    "Paramount Plus": "Paramount+",
    "HBO Max": "Max",
    "Fox Sports 1": "FS1",
    "MLB TV": "MLB.TV",
    "NBA LP": "NBA League Pass",
    "League Pass": "NBA League Pass",
    "Sunday Ticket": "NFL Sunday Ticket",
    "NHL CI": "NHL Center Ice",
}

# Out-of-market packages that ESPN labels as streaming.
PACKAGES = {"MLB.TV", "NBA League Pass", "NFL Sunday Ticket", "NHL Center Ice"}
# ESPN+ carries the NHL's out-of-market games; in other leagues it is plain streaming.
LEAGUE_PACKAGES = {("nhl", "ESPN+")}

_NAMES = {name.casefold(): name for name in CHANNELS} | {s.casefold(): name for s, name in SPELLINGS.items()}


def normalise(name: str) -> str:
    name = name.strip()
    return _NAMES.get(name.casefold(), name)


def icon_url(name: str) -> str | None:
    """Where a channel's icon comes from; None for a text-only or unknown channel."""
    entry = CHANNELS.get(name, {})
    if "simple_icons" in entry:
        return SIMPLE_ICONS.format(entry["simple_icons"])
    if "tv_logos" in entry:
        return TV_LOGOS.format(entry["tv_logos"])
    return None


def select(broadcasts: Iterable[EspnBroadcast], league: str, local_markets: set[str]) -> list[str]:
    """The channel names to show, in order. local_markets holds "Home", "Away" or both: the followed sides."""
    kinds: dict[str, list[str]] = {"local": [], "national": [], "streaming": [], "opponent": [], "package": []}
    for b in broadcasts:
        name = normalise(b.name)
        kind = _kind(b, name, league, local_markets)
        if kind and not any(name in names for names in kinds.values()):
            kinds[kind].append(name)
    shown = (kinds["local"] or kinds["national"]) + kinds["streaming"]
    return shown or kinds["opponent"] + kinds["package"]


def _kind(b: EspnBroadcast, name: str, league: str, local_markets: set[str]) -> str | None:
    if b.type == "Radio":
        return None
    if b.type == "Subscription Package" or name in PACKAGES or (league, name) in LEAGUE_PACKAGES:
        return "package"
    if b.type == "Streaming":
        return "streaming"
    if b.market == "National":
        return "national"
    return "local" if b.market in local_markets else "opponent"


def record_unknown(path: Path, games: list[dict[str, Any]], now: datetime) -> None:
    """Keep one entry per unknown channel and league; a channel now in the map loses its entry."""
    entries = {key: e for key, e in _load(path).items() if e["name"] not in CHANNELS}
    stamp = now.isoformat(timespec="seconds")
    # A set, so a channel on several games counts as seen once per run.
    for name, league in {(c["name"], g["league"]) for g in games for c in g["channels"]}:
        if name in CHANNELS:
            continue
        entry = entries.setdefault((name, league), {
            "name": name, "league": league, "first_seen": stamp, "last_seen": stamp, "times_seen": 0,
        })
        entry["last_seen"] = stamp
        entry["times_seen"] += 1
    # Write then rename, so a crash mid-write never leaves a half-written file.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(entries.values(), key=lambda e: (e["name"], e["league"])), indent=2))
    os.replace(temporary, path)


def _load(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    try:
        return {(e["name"], e["league"]): dict(e) for e in json.loads(path.read_text())}
    except FileNotFoundError:
        pass
    except (ValueError, KeyError, TypeError):
        log.warning("state file %s is unreadable, starting fresh", path.name)
    return {}
