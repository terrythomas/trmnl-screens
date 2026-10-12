"""PROTOTYPE: fixture variants for the Media screen layout (issue #5). Invented titles; posters from poster-cache/."""
import base64
import os
import copy
from pathlib import Path

# PROTOTYPE_POSTERS=standin renders with generated stand-in art (safe to publish); default is the local Plex cache.
CACHE = Path(__file__).parent / ("standin-posters" if os.environ.get("PROTOTYPE_POSTERS") == "standin" else "poster-cache")


def poster(n, size):
    path = CACHE / f"{(n % 14) + 1:02d}-{size}.jpg"
    if not path.exists():
        path = path.with_suffix(".png")
    if not path.exists():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


NOW = "2026-10-12T19:30:00-04:00"
# kind, title, (season, number, episode title), progress, last_viewed, duration, state
# state is decided by the collector: "new" (unstarted episode 1, first appearance of a show, or unstarted movie),
# "in_progress" (has a view offset), "next" (next unwatched episode mid-season).
CW = [
    ("episode", "The Lighthouse Keepers", (4, 1, "Low Tide"), None, None, 52, "new"),
    ("movie", "A Quiet Orbit", None, 42, "2026-05-02", 118, "in_progress"),
    ("episode", "Copper Valley", (2, 6, "The Long Way Round"), 12, "2026-06-29", 44, "in_progress"),
    ("episode", "Night Market", (1, 4, "Paper Lanterns"), None, "2026-07-18", 30, "next"),
    ("movie", "Salt and Iron", None, 77, "2026-08-14", 131, "in_progress"),
    ("episode", "Field Notes", (3, 2, "Migration"), None, "2026-09-03", 58, "next"),
    ("episode", "The Understudy", (1, 9, "Second Act"), 55, "2026-09-30", 26, "in_progress"),
    ("episode", "Harbour Lights", (5, 11, "Fog Warning"), None, "2026-10-09", 47, "next"),
    ("movie", "Low Orbit Lullaby", None, None, None, 96, "new"),
    ("episode", "Tin Roof", (2, 2, "Downpour"), None, "2026-10-10", 22, "next"),
    ("episode", "Quiz Night", (26, 1, "Opening Round"), None, None, 47, "new"),
    ("episode", "Glasshouse", (1, 5, "Panes"), None, "2026-10-11", 41, "next"),
]
STATE_ORDER = {"new": 0, "in_progress": 1, "next": 2}


def cw_item(i, kind, title, ep, progress, last, duration, state):
    return {
        "kind": kind, "title": title, "state": state,
        "episode": {"season": ep[0], "number": ep[1], "title": ep[2]} if ep else None,
        "progress": progress, "last_viewed": last,
        "duration_min": duration,
        "remaining_min": round(duration * (100 - progress) / 100) if progress else None,
        "poster": poster(i, "thumb"),
    }


def cw_items(n):
    # NEW, then in progress, then NEXT; neglect order (least recently watched first) within each group.
    picked = [cw_item(i, *CW[i]) for i in range(n)]
    return sorted(picked, key=lambda it: (STATE_ORDER[it["state"]], it["last_viewed"] or ""))


# series, season, number, number_end, title, air_time, aired, grabbed, runtime, milestone
# milestone (from the collector): series_premiere | season_premiere | midseason_finale | season_finale | series_finale | None
AIRING = [
    ("Night Market", 2, 7, None, "Lanterns", "2026-10-12T09:00:00-04:00", True, True, 30, "season_finale"),
    ("Field Notes", 1, 3, None, "Into the Marsh", "2026-10-12T13:00:00-04:00", True, False, 58, None),
    ("Copper Valley", 3, 1, None, "Homecoming", "2026-10-12T21:00:00-04:00", False, False, 44, "season_premiere"),
    ("The Understudy", 2, 4, None, "Opening Night", "2026-10-12T22:30:00-04:00", False, False, 26, None),
]
AIRING_EXTRA = [  # pushes Airing past four rows, including a whole-season drop
    ("Glasshouse", 1, 1, 10, "Full season", "2026-10-12T03:00:00-04:00", True, True, 41, "series_premiere"),
    ("Harbour Lights", 6, 2, None, "Slack Water", "2026-10-12T20:00:00-04:00", False, False, 47, None),
    ("Tin Roof", 3, 5, None, "Gutters", "2026-10-12T23:00:00-04:00", False, False, 22, "series_finale"),
]
RELEASING = [  # title, year, kind, grabbed, runtime
    ("Paper Boats", 2026, "theatrical", False, 112),
    ("The Glass Orchard", 2025, "digital", False, 97),
]
AIR_KEYS = ["series", "season", "number", "number_end", "title", "air_time", "aired", "grabbed", "runtime_min", "milestone"]


def full(cw_count=6, total=6, airing=AIRING):
    return {
        "updated_at": NOW,
        "errors": [],
        "continue_watching": {"stale": False, "total": total, "items": cw_items(min(cw_count, len(CW)))},
        "airing": {"stale": False, "items": [dict(zip(AIR_KEYS, a), poster=poster(3 + i, "thumb")) for i, a in enumerate(airing)]},
        "releasing_today": {"stale": False, "items": [
            {"title": t, "year": y, "kind": k, "grabbed": g, "runtime_min": r, "poster": poster(10 + i, "thumb")}
            for i, (t, y, k, g, r) in enumerate(RELEASING)]},
    }


def variants():
    v = {"full": full()}
    for section in ("continue_watching", "airing", "releasing_today"):
        d = full()
        del d[section]  # absent key == empty section
        v[f"no-{section.replace('_', '-')}"] = d
    v["all-empty"] = {"updated_at": NOW, "errors": []}
    d = full()
    d["airing"]["stale"] = True
    d["errors"] = [{"source": "sonarr", "since": "2026-10-12T17:45:00-04:00"}]
    v["stale-error"] = d
    d = full()
    d["continue_watching"]["items"][0].update(title="The Extraordinarily Long-Running Chronicles of the Lighthouse Keepers")
    d["continue_watching"]["items"][0]["episode"]["title"] = "An Unreasonably Long Episode Title That Keeps Going"
    d["continue_watching"]["items"][2]["title"] = "Copper Valley: The Untold Story of Everyone Who Ever Lived There"
    d["airing"]["items"][0].update(series="Night Market Confidential: Behind the Stalls", title="A Very Long Episode Name Indeed")
    d["releasing_today"]["items"][0]["title"] = "Paper Boats and the Impossible Voyage Across the Northern Sea"
    v["long-titles"] = d
    v["cw-one"] = full(cw_count=1, total=1)
    v["cw-many"] = full(cw_count=12, total=14)
    for n in (4, 6, 8, 10, 12):
        v[f"cw-{n:02d}"] = full(cw_count=n, total=n)
    v["airing-many"] = full(airing=sorted(AIRING + AIRING_EXTRA, key=lambda a: a[5]))
    return v
