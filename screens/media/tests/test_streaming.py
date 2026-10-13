import importlib
from datetime import date, datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
section = importlib.import_module("trmnl_screens.media.collector.streaming")
radarr = importlib.import_module("trmnl_screens.media.collector.sources.radarr")
plex = importlib.import_module("trmnl_screens.media.collector.sources.plex")

EASTERN = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 13, 14, 30, tzinfo=EASTERN)
TODAY = date(2026, 10, 13)
DAY = timedelta(days=1)
YESTERDAY, TOMORROW = TODAY - DAY, TODAY + DAY


def movie(title="The Glass Orchard", *, digital=TODAY, cinemas=None, grabbed=False, monitored=True, runtime=97):
    return radarr.RadarrMovie(
        tmdb_id=700002, title=title, year=2026, in_cinemas=cinemas, digital_release=digital, grabbed=grabbed,
        monitored=monitored, runtime_min=runtime, poster_url=None,
    )


@pytest.mark.parametrize("digital, grabbed, monitored, expected", [
    (TODAY, False, True, True),
    (TODAY, True, True, False),
    (TODAY, False, False, False),
    (YESTERDAY, False, True, False),
    (TOMORROW, False, True, False),
    (None, False, True, False),
])
def test_streams_today(digital, grabbed, monitored, expected):
    assert section.streams_today(movie(digital=digital, grabbed=grabbed, monitored=monitored), TODAY) is expected


def test_a_theatrical_release_today_is_not_streaming():
    assert section.streams_today(movie(digital=None, cinemas=TODAY), TODAY) is False


class FakeRadarr:
    def __init__(self, movies):
        self.movies, self.asked = movies, []

    def calendar(self, start, end):
        self.asked.append((start, end))
        return self.movies


class FakePosters:
    def poster(self, path, width, height):
        raise AssertionError("no poster URL, so no poster request")


def test_items_by_title_with_the_payload_contract():
    calendar = FakeRadarr([movie("Bravo"), movie("Alpha", runtime=None), movie("Grabbed", grabbed=True)])
    assert section.streaming(calendar, FakePosters(), NOW) == {"stale": False, "items": [
        {"title": "Alpha", "runtime_min": None, "poster": None},
        {"title": "Bravo", "runtime_min": 97, "poster": None},
    ]}
    assert calendar.asked == [(TODAY, TOMORROW)]


def test_nothing_streaming_means_no_section():
    assert section.streaming(FakeRadarr([movie(digital=YESTERDAY)]), FakePosters(), NOW) is None
