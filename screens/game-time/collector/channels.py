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

# Normalised name → entry. {} is a known channel; {"text_only": True} is one deliberately shown by name.
# Each entry gains its icon source with the logo store (#60).
CHANNELS: dict[str, dict[str, Any]] = {
    "ABC": {},
    "CBS": {},
    "ESPN": {},
    "ESPN2": {},
    "ESPNU": {},
    "FOX": {},
    "FS1": {},
    "NBC": {},
    "TNT": {},
    "TBS": {},
    "truTV": {},
    "NBA TV": {},
    "NFL Network": {},
    "MLB Network": {},
    "NHL Network": {},
    "ESPN+": {},
    "Prime Video": {},
    "Apple TV": {},
    "Paramount+": {},
    "Max": {},
    "YouTube TV": {},
    "Peacock": {"text_only": True},
    "MLB.TV": {},
    "NBA League Pass": {},
    "NFL Sunday Ticket": {},
    "NHL Center Ice": {},
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
