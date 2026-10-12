"""PROTOTYPE: fixture variants for the Media screen layout (issue #5). Invented titles; posters from poster-cache/."""
import base64
import copy
from pathlib import Path

CACHE = Path(__file__).parent / "poster-cache"


def poster(n, size):
    path = CACHE / f"{(n % 14) + 1:02d}-{size}.jpg"
    if not path.exists():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


NOW = "2026-10-12T19:30:00-04:00"
CW = [  # neglect order: least recently watched first; the first item has never been touched
    ("episode", "The Lighthouse Keepers", (4, 1, "Low Tide"), None, None),
    ("movie", "A Quiet Orbit", None, 42, "2026-05-02"),
    ("episode", "Copper Valley", (2, 6, "The Long Way Round"), 12, "2026-06-29"),
    ("episode", "Night Market", (1, 4, "Paper Lanterns"), None, "2026-07-18"),
    ("movie", "Salt and Iron", None, 77, "2026-08-14"),
    ("episode", "Field Notes", (3, 2, "Migration"), None, "2026-09-03"),
    ("episode", "The Understudy", (1, 9, "Second Act"), 55, "2026-09-30"),
    ("episode", "Harbour Lights", (5, 11, "Fog Warning"), None, "2026-10-09"),
]


def cw_item(i, kind, title, ep, progress, last):
    return {
        "kind": kind, "title": title,
        "episode": {"season": ep[0], "number": ep[1], "title": ep[2]} if ep else None,
        "progress": progress, "last_viewed": last,
        "poster": poster(i, "hero" if i == 0 else "thumb"),
    }


AIRING = [
    ("Night Market", 2, 7, "Lanterns", "2026-10-12T09:00:00-04:00", True, True),
    ("Field Notes", 1, 3, "Into the Marsh", "2026-10-12T13:00:00-04:00", True, False),
    ("Copper Valley", 3, 1, "Homecoming", "2026-10-12T21:00:00-04:00", False, False),
    ("The Understudy", 2, 4, "Opening Night", "2026-10-12T22:30:00-04:00", False, False),
]
RELEASING = [
    ("Paper Boats", 2026, "theatrical", False),
    ("The Glass Orchard", 2025, "digital", False),
]


def full(cw_count=8, total=8):
    return {
        "updated_at": NOW,
        "errors": [],
        "continue_watching": {"stale": False, "total": total,
                              "items": [cw_item(i, *CW[i]) for i in range(min(cw_count, len(CW)))]},
        "airing": {"stale": False, "items": [
            dict(zip(["series", "season", "number", "title", "air_time", "aired", "grabbed"], a)) for a in AIRING]},
        "releasing_today": {"stale": False, "items": [
            {"title": t, "year": y, "kind": k, "grabbed": g, "poster": poster(10 + i, "thumb")}
            for i, (t, y, k, g) in enumerate(RELEASING)]},
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
    v["cw-many"] = full(cw_count=8, total=14)
    return v
