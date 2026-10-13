import base64
import importlib
from datetime import date, datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
section = importlib.import_module("trmnl_screens.media.collector.releasing_today")
radarr = importlib.import_module("trmnl_screens.media.collector.sources.radarr")
plex = importlib.import_module("trmnl_screens.media.collector.sources.plex")

EASTERN = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 12, 14, 30, tzinfo=EASTERN)
TODAY = date(2026, 10, 12)
DAY = timedelta(days=1)
YESTERDAY, TOMORROW = TODAY - DAY, TODAY + DAY


def movie(title="Harbor Lights", *, cinemas=None, digital=None, grabbed=False, monitored=True, runtime=112,
          year=2026):
    return radarr.RadarrMovie(
        title=title, year=year, in_cinemas=cinemas, digital_release=digital, grabbed=grabbed,
        monitored=monitored, runtime_min=runtime, poster_url=f"https://images.example/{title}.jpg",
    )


# The release rule (spec: Releasing Today). Physical releases never reach it: the adapter drops them.
@pytest.mark.parametrize("cinemas, digital, grabbed, expected", [
    # theatrical only
    (TODAY, None, False, "theatrical"),
    (TODAY, None, True, "theatrical"),
    (YESTERDAY, None, False, None),
    (YESTERDAY, None, True, None),
    (TOMORROW, None, False, None),
    (TOMORROW, None, True, None),
    # digital only
    (None, TODAY, False, "digital"),
    (None, TODAY, True, None),
    (None, YESTERDAY, False, None),
    (None, YESTERDAY, True, None),
    (None, TOMORROW, False, None),
    (None, TOMORROW, True, None),
    # both on the same day
    (TODAY, TODAY, False, "theatrical"),
    (TODAY, TODAY, True, "theatrical"),
    (YESTERDAY, YESTERDAY, False, None),
    (TOMORROW, TOMORROW, True, None),
    # both, on different days
    (YESTERDAY, TODAY, False, "digital"),
    (YESTERDAY, TODAY, True, None),
    (TODAY, TOMORROW, False, "theatrical"),
    (TODAY, YESTERDAY, True, "theatrical"),
    # neither
    (None, None, False, None),
    (None, None, True, None),
])
def test_release_kind(cinemas, digital, grabbed, expected):
    assert section.release_kind(movie(cinemas=cinemas, digital=digital, grabbed=grabbed), TODAY) == expected


class FakeRadarr:
    def __init__(self, movies):
        self.movies, self.asked = movies, []

    def calendar(self, day):
        self.asked.append(day)
        return self.movies  # unfiltered: the section must apply the rule itself


class FakePosters:
    def poster(self, path, width, height):
        return f"{path}@{width}x{height}".encode()


def build(movies, now=NOW):
    return section.releasing_today(FakeRadarr(movies), FakePosters(), now)


def titles(result):
    return [item["title"] for item in result["items"]]


def poster_uri(url):
    return "data:image/jpeg;base64," + base64.b64encode(f"{url}@234x351".encode()).decode()


def test_item_maps_to_the_payload_contract():
    result = build([movie("Harbor Lights", cinemas=TODAY, runtime=112, year=2026)])
    assert result == {"stale": False, "items": [{
        "title": "Harbor Lights", "year": 2026, "kind": "theatrical", "grabbed": False, "runtime_min": 112,
        "poster": poster_uri("https://images.example/Harbor Lights.jpg"),
    }]}


def test_movie_without_a_poster_gets_none():
    bare = radarr.RadarrMovie(**{**movie(cinemas=TODAY).__dict__, "poster_url": None})
    assert build([bare])["items"][0]["poster"] is None


def test_only_monitored_movies():
    result = build([movie("Watched for", cinemas=TODAY), movie("Unmonitored", cinemas=TODAY, monitored=False)])
    assert titles(result) == ["Watched for"]


def test_theatrical_before_digital_then_by_title():
    result = build([
        movie("Bravo", digital=TODAY), movie("Delta", cinemas=TODAY),
        movie("Alpha", digital=TODAY), movie("Charlie", cinemas=TODAY),
    ])
    assert [(i["title"], i["kind"]) for i in result["items"]] == [
        ("Charlie", "theatrical"), ("Delta", "theatrical"), ("Alpha", "digital"), ("Bravo", "digital"),
    ]


def test_nothing_releasing_means_no_section():
    assert build([movie(cinemas=YESTERDAY), movie(digital=TODAY, grabbed=True)]) is None


@pytest.mark.parametrize("now, today", [
    pytest.param(datetime(2026, 10, 12, 23, 59, tzinfo=EASTERN), TODAY, id="a minute before local midnight"),
    pytest.param(datetime(2026, 10, 13, 0, 0, tzinfo=EASTERN), TOMORROW, id="local midnight"),
])
def test_today_is_the_local_calendar_day(now, today):
    # 23:59 Eastern is already the next day in UTC; Radarr must still be asked for the local day.
    calendar = FakeRadarr([movie("Opens today", cinemas=TODAY), movie("Opens tomorrow", cinemas=TOMORROW)])
    result = section.releasing_today(calendar, FakePosters(), now)
    assert calendar.asked == [today]
    assert titles(result) == ["Opens today" if today == TODAY else "Opens tomorrow"]


class DownPosters:
    def poster(self, path, width, height):
        raise plex.PlexError("Plex request failed: ConnectError")


def test_movies_lose_their_posters_when_plex_is_down():
    result = section.releasing_today(FakeRadarr([movie("Harbor Lights", cinemas=TODAY)]), DownPosters(), NOW)
    assert [(i["title"], i["poster"]) for i in result["items"]] == [("Harbor Lights", None)]
