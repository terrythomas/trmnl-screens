"""Writes the Media screen's fixture variants to fixtures/variants/ for checking the template by eye.

    python screens/media/fixtures/variants.py
    scripts/preview-data media variants/full.json

Titles are invented and posters are abstract stand-ins, so renders are safe to publish.
"""

import base64
import copy
import json
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "variants"
NOW = "2026-10-12T19:30:00-04:00"


def _png(w: int, h: int, pixel) -> bytes:
    rows = b"".join(b"\0" + bytes(pixel(x, y) for x in range(w)) for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def poster(n: int) -> str:
    """An abstract grayscale stand-in poster: bands, rings, a horizon or a checker."""
    w, h, kind, shade = 117, 176, n % 4, 13 * (n // 4 % 4)

    def px(x, y):
        u, v = x / w, y / h
        if kind == 0:
            value = 40 if int((u + v) * 7) % 2 else 200
        elif kind == 1:
            value = 30 + int(200 * (0.5 + 0.5 * math.sin(math.hypot(u - .5, v - .4) * 40)))
        elif kind == 2:
            value = 235 if math.hypot(u - .5, v - .35) < .18 else (90 if v > .6 else 170)
        else:
            value = 60 if (int(u * 6) + int(v * 9)) % 2 else 190
        return max(0, min(255, value - shade))

    return "data:image/png;base64," + base64.b64encode(_png(w, h, px)).decode()


# kind, title, (season, number, episode title), progress, last viewed, runtime, state; already in collector order.
CW = [
    ("episode", "The Lighthouse Keepers", (4, 1, "Low Tide"), None, None, 52, "new"),
    ("movie", "Low Orbit Lullaby", None, None, None, 96, "new"),
    ("movie", "A Quiet Orbit", None, 42, "2026-05-02", 118, "in_progress"),
    ("episode", "Copper Valley", (2, 6, "The Long Way Round"), 12, "2026-06-29", 44, "in_progress"),
    ("movie", "Salt and Iron", None, 77, "2026-08-14", 131, "in_progress"),
    ("episode", "The Understudy", (1, 9, "Second Act"), 55, "2026-09-30", 26, "in_progress"),
    ("episode", "Night Market", (1, 4, "Paper Lanterns"), None, "2026-07-18", 30, "next"),
    ("episode", "Field Notes", (3, 2, "Migration"), None, "2026-09-03", 58, "next"),
    ("episode", "Harbour Lights", (5, 11, "Fog Warning"), None, "2026-10-09", 47, "next"),
    ("episode", "Tin Roof", (2, 2, "Downpour"), None, "2026-10-10", 22, "next"),
    ("episode", "Quiz Night", (26, 1, "Opening Round"), None, "2026-10-10", 47, "next"),
    ("episode", "Glasshouse", (1, 5, "Panes"), None, "2026-10-11", 41, "next"),
]

# series, season, number, number_end, title, air time, aired, grabbed, runtime, milestone
AIRING = [
    ("Night Market", 2, 7, None, "Lanterns", "2026-10-12T09:00:00-04:00", True, True, 30, "season_finale"),
    ("Field Notes", 1, 3, None, "Into the Marsh", "2026-10-12T19:05:00-04:00", True, False, 58, None),
    ("Copper Valley", 3, 1, None, "Homecoming", "2026-10-12T21:00:00-04:00", False, False, 44, "season_premiere"),
    ("The Understudy", 2, 4, None, "Opening Night", "2026-10-12T22:30:00-04:00", False, False, None, None),
]
AIRING_EXTRA = [  # pushes Airing past four rows, including a whole-season drop
    ("Glasshouse", 1, 1, 10, None, "2026-10-12T03:00:00-04:00", True, True, 41, "entire_season"),
    ("Harbour Lights", 6, 2, None, "Slack Water", "2026-10-12T20:00:00-04:00", False, False, 47, None),
    ("Tin Roof", 3, 5, None, "Gutters", "2026-10-12T23:00:00-04:00", False, False, 22, "series_finale"),
]
AIR_KEYS = ["series", "season", "number", "number_end", "title", "air_time", "aired", "grabbed", "runtime_min",
            "milestone"]

# title, stage, note, since, days ago, runtime
THEATERS = [
    ("Paper Boats", "wide", None, "2026-10-12", 0, 112),
    ("Harbour Wall", "limited", "IMAX", "2026-10-10", 2, 131),
]
THEATERS_EXTRA = [("Signal Fires", "wide", None, "2026-10-09", 3, 104)]
THEATERS_MORE = [("Northern Line", "wide", None, "2026-10-09", 3, 95)]
# title, runtime
STREAMING = [("The Glass Orchard", None)]
STREAMING_EXTRA = [("Lantern Season", 99), ("Small Hours", 88)]


def cw_item(n, kind, title, episode, progress, last_viewed, runtime, state):
    return {
        "kind": kind, "state": state, "title": title,
        "episode": {"season": episode[0], "number": episode[1], "title": episode[2]} if episode else None,
        "duration_min": runtime,
        "progress": progress,
        "remaining_min": round(runtime * (100 - progress) / 100) if progress else None,
        "last_viewed": last_viewed,
        "poster": poster(n),
    }


def full(cw_count=6, total=None, airing=AIRING, theaters=THEATERS, streaming=STREAMING):
    items = [cw_item(n, *row) for n, row in enumerate(CW[:cw_count])]
    return {
        "updated_at": NOW,
        "errors": [],
        "continue_watching": {"stale": False, "total": total or cw_count, "items": items},
        "airing": {"stale": False, "items": [
            dict(zip(AIR_KEYS, row), poster=poster(3 + n)) for n, row in enumerate(airing)]},
        "in_theaters": {"stale": False, "items": [
            {"title": t, "stage": st, "note": note, "since": since, "days_ago": ago, "runtime_min": r,
             "poster": poster(10 + n)}
            for n, (t, st, note, since, ago, r) in enumerate(theaters)]},
        "streaming": {"stale": False, "items": [
            {"title": t, "runtime_min": r, "poster": poster(14 + n)} for n, (t, r) in enumerate(streaming)]},
    }


def variants() -> dict[str, dict]:
    v = {"full": full()}
    for section in ("continue_watching", "airing", "in_theaters", "streaming"):
        absent, emptied = full(), full()
        del absent[section]
        emptied[section]["items"] = []  # must render exactly like the absent key
        v[f"no-{section.replace('_', '-')}"] = absent
        v[f"empty-{section.replace('_', '-')}"] = emptied
    v["all-empty"] = {"updated_at": NOW, "errors": []}

    d = full()
    d["airing"]["stale"] = True
    d["errors"] = [{"source": "sonarr", "since": "2026-10-12T17:45:00-04:00"}]
    v["stale-error"] = d
    d = full()
    d["continue_watching"]["stale"] = True
    d["errors"] = [{"source": "plex", "since": "2026-10-12T18:15:00-04:00"}]
    v["stale-plex"] = d
    d = full()
    del d["in_theaters"], d["streaming"]  # failed before they ever had data
    d["errors"] = [{"source": "radarr", "since": "2026-10-12T19:15:00-04:00"},
                   {"source": "sonarr", "since": "2026-10-12T17:45:00-04:00"}]
    d["airing"]["stale"] = True
    v["errors-no-data"] = d

    d = full()
    cw = d["continue_watching"]["items"]
    cw[0]["title"] = "The Extraordinarily Long-Running Chronicles of the Lighthouse Keepers"
    cw[3]["title"] = "Copper Valley: The Untold Story of Everyone Who Ever Lived There"
    d["airing"]["items"][0]["series"] = "Night Market Confidential: Behind the Stalls"
    d["in_theaters"]["items"][0]["title"] = "Paper Boats and the Impossible Voyage Across the Northern Sea"
    v["long-titles"] = d

    v["cw-one"] = full(cw_count=1)
    for n in (4, 8, 10, 12):
        v[f"cw-{n:02d}"] = full(cw_count=n)
    v["cw-many"] = full(cw_count=12, total=14)
    v["airing-many"] = full(airing=sorted(AIRING + AIRING_EXTRA, key=lambda a: a[5]))
    d = full()
    d["in_theaters"]["stale"] = True
    d["errors"] = [{"source": "tmdb", "since": "2026-10-12T06:00:00-04:00"}]
    v["stale-tmdb"] = d
    v["theaters-many"] = full(theaters=THEATERS + THEATERS_EXTRA, streaming=STREAMING + STREAMING_EXTRA)
    v["theaters-only-many"] = full(theaters=THEATERS + THEATERS_EXTRA + THEATERS_MORE, streaming=[])
    v["streaming-only"] = full(theaters=[], streaming=STREAMING + STREAMING_EXTRA)
    return copy.deepcopy(v)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, data in variants().items():
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {len(variants())} variants to {OUT}")
