import base64
import importlib
from datetime import datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
section = importlib.import_module("trmnl_screens.media.collector.continue_watching")
plex = importlib.import_module("trmnl_screens.media.collector.sources.plex")

EASTERN = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 12, 14, 30, tzinfo=EASTERN)


def days_ago(days):
    return NOW - timedelta(days=days)


def episode(show, season=1, number=2, *, offset=None, viewed=days_ago(3), title="An Episode", minutes=44):
    return plex.PlexItem(
        kind="episode", title=show, season=season, number=number, episode_title=title,
        duration_ms=minutes * 60_000, view_offset_ms=offset, last_viewed_at=viewed,
        show_key=f"key-{show}", poster_path=f"/thumb/{show}",
    )


def movie(title, *, offset=None, viewed=days_ago(3), minutes=118):
    return plex.PlexItem(
        kind="movie", title=title, season=None, number=None, episode_title=None,
        duration_ms=minutes * 60_000, view_offset_ms=offset, last_viewed_at=viewed,
        show_key=None, poster_path=f"/thumb/{title}",
    )


class FakeSource:
    """Stands in for PlexSource. Shows default to watched recently, so their episodes are Next."""

    def __init__(self, items, shows=None):
        self.items, self.shows, self.looked_up, self.posters = items, shows or {}, [], []

    def continue_watching(self):
        return self.items

    def show_history(self, show_key):
        self.looked_up.append(show_key)
        return self.shows.get(show_key, plex.ShowHistory(last_viewed_at=days_ago(2)))

    def poster(self, path, width, height):
        self.posters.append(path)
        return f"{path}@{width}x{height}".encode()


def build(items, shows=None, **kwargs):
    return section.continue_watching(FakeSource(items, shows), NOW, **kwargs)


def poster_uri(path):
    return "data:image/jpeg;base64," + base64.b64encode(f"{path}@234x351".encode()).decode()


def test_in_progress_movie_and_episode_map_to_the_payload_contract():
    result = build([
        movie("A Quiet Orbit", offset=50 * 60_000, minutes=118, viewed=datetime(2026, 8, 14, 2, 0, tzinfo=timezone.utc)),
        episode("Copper Valley", 2, 6, title="The Long Way Round", minutes=44, offset=5 * 60_000,
                viewed=datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)),
    ])

    assert result["total"] == 2
    assert result["items"] == [
        {
            "kind": "movie", "state": "in_progress", "title": "A Quiet Orbit", "episode": None,
            "duration_min": 118, "progress": 42, "remaining_min": 68,
            "last_viewed": "2026-08-13",  # local date: 02:00 UTC is still the 13th in UTC-4
            "poster": poster_uri("/thumb/A Quiet Orbit"),
        },
        {
            "kind": "episode", "state": "in_progress", "title": "Copper Valley",
            "episode": {"season": 2, "number": 6, "title": "The Long Way Round"},
            "duration_min": 44, "progress": 11, "remaining_min": 39,
            "last_viewed": "2026-09-30",
            "poster": poster_uri("/thumb/Copper Valley"),
        },
    ]


def watched(days):
    return plex.ShowHistory(last_viewed_at=days_ago(days))


NEVER_WATCHED = plex.ShowHistory(last_viewed_at=None)


@pytest.mark.parametrize("item, show, expected", [
    pytest.param(episode("S", offset=60_000), NEVER_WATCHED, "in_progress", id="started episode, even of a new show"),
    pytest.param(movie("M", offset=60_000), None, "in_progress", id="started movie"),
    pytest.param(movie("M"), None, "new", id="unstarted movie"),
    pytest.param(episode("S", 1, 1), NEVER_WATCHED, "new", id="show never watched"),
    pytest.param(episode("S", 3, 5), NEVER_WATCHED, "new", id="show never watched, mid-season"),
    pytest.param(episode("S", 2, 1), watched(30), "new", id="season premiere, show untouched exactly 30 days"),
    pytest.param(episode("S", 2, 1), watched(31), "new", id="season premiere, show untouched 31 days"),
    pytest.param(episode("S", 2, 1), watched(29.9), "next", id="season premiere while binge-watching"),
    pytest.param(episode("S", 2, 2), watched(90), "next", id="mid-season episode of a long-untouched show"),
    pytest.param(episode("S", 2, 5), watched(1), "next", id="next episode"),
])
def test_item_state(item, show, expected):
    shows = {item.show_key: show} if show else {}
    assert build([item], shows)["items"][0]["state"] == expected


def test_new_after_days_is_configurable():
    shows = {"key-S": watched(10)}
    assert build([episode("S", 2, 1)], shows, new_after_days=7)["items"][0]["state"] == "new"
    assert build([episode("S", 2, 1)], shows, new_after_days=14)["items"][0]["state"] == "next"


def test_show_is_looked_up_once_and_only_for_unstarted_episodes():
    source = FakeSource([
        episode("S", 1, 2), episode("S", 1, 3), episode("T", offset=60_000), movie("M"),
    ])
    section.continue_watching(source, NOW)
    assert source.looked_up == ["key-S"]


def titles(result):
    return [item["title"] for item in result["items"]]


def test_order_is_new_then_in_progress_then_next_each_in_neglect_order():
    result = build([
        episode("Next recent", viewed=days_ago(1)),
        movie("Started recent", offset=60_000, viewed=days_ago(2)),
        movie("New recent", viewed=days_ago(1)),
        episode("Next stalled", viewed=days_ago(40)),
        movie("Started stalled", offset=60_000, viewed=days_ago(60)),
        movie("New stalled", viewed=days_ago(9)),
    ])
    assert titles(result) == [
        "New stalled", "New recent",
        "Started stalled", "Started recent",
        "Next stalled", "Next recent",
    ]


def test_never_viewed_items_lead_their_state_and_ties_keep_plex_order():
    result = build([
        episode("A", viewed=days_ago(5)),
        episode("B", viewed=None),
        episode("C", viewed=days_ago(5)),
        episode("D", viewed=None),
    ])
    assert titles(result) == ["B", "D", "A", "C"]


def test_sends_at_most_twelve_items_by_default_and_counts_them_all():
    items = [episode(f"Show {n:02d}", viewed=days_ago(n)) for n in range(1, 16)]
    source = FakeSource(items)

    result = section.continue_watching(source, NOW)

    assert result["total"] == 15
    assert titles(result) == [f"Show {n:02d}" for n in range(15, 3, -1)]
    assert len(source.posters) == 12


def test_limit_is_configurable():
    result = build([movie(f"M{n}") for n in range(5)], limit=3)
    assert (result["total"], len(result["items"])) == (5, 3)


def test_nothing_to_continue_means_no_section():
    assert build([]) is None
