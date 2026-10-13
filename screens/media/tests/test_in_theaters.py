import base64
import importlib
from datetime import date, datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
section = importlib.import_module("trmnl_screens.media.collector.in_theaters")
radarr = importlib.import_module("trmnl_screens.media.collector.sources.radarr")
tmdb = importlib.import_module("trmnl_screens.media.collector.sources.tmdb")
plex = importlib.import_module("trmnl_screens.media.collector.sources.plex")

EASTERN = timezone(timedelta(hours=-5))
Release = tmdb.Release
Run = section.Run

# A Friday wide release, with a limited IMAX run three days before it.
LIMITED, WIDE, SUNDAY = date(2026, 11, 3), date(2026, 11, 6), date(2026, 11, 8)
RELEASES = [
    Release(date(2026, 9, 26), "Premiere", "Harbor Film Festival"),
    Release(LIMITED, "Theatrical (limited)", "IMAX"),
    Release(WIDE, "Theatrical", None),
    Release(date(2026, 12, 15), "Digital", None),
]


def day(d, offset=0):
    return d + timedelta(days=offset)


def wide(on, *extra):
    return [Release(on, "Theatrical", None), *extra]


def limited(on, note=None):
    return Release(on, "Theatrical (limited)", note)


@pytest.mark.parametrize("releases, today, expected", [
    # A Friday wide release runs Friday through Sunday.
    (wide(WIDE), day(WIDE, -1), None),
    (wide(WIDE), WIDE, Run("wide", WIDE, None)),
    (wide(WIDE), SUNDAY, Run("wide", WIDE, None)),
    (wide(WIDE), day(SUNDAY, 1), None),
    # A Wednesday release runs Wednesday through Sunday; a Sunday one for that day only.
    (wide(date(2026, 11, 25)), date(2026, 11, 25), Run("wide", date(2026, 11, 25), None)),
    (wide(date(2026, 11, 25)), date(2026, 11, 29), Run("wide", date(2026, 11, 25), None)),
    (wide(date(2026, 11, 25)), date(2026, 11, 30), None),
    (wide(SUNDAY), SUNDAY, Run("wide", SUNDAY, None)),
    (wide(SUNDAY), day(SUNDAY, 1), None),
    # A limited run up to seven days before the wide release starts the run early.
    (RELEASES, day(LIMITED, -1), None),
    (RELEASES, LIMITED, Run("limited", LIMITED, "IMAX")),
    (RELEASES, day(WIDE, -1), Run("limited", LIMITED, "IMAX")),
    (RELEASES, WIDE, Run("wide", WIDE, None)),
    (wide(WIDE, limited(day(WIDE, -7))), day(WIDE, -7), Run("limited", day(WIDE, -7), None)),
    # Earlier limited runs, re-releases after the wide release and premieres don't count.
    (wide(WIDE, limited(day(WIDE, -10))), day(WIDE, -10), None),
    (wide(WIDE, limited(day(WIDE, 20), "IMAX")), day(WIDE, 20), None),
    ([Release(LIMITED, "Premiere", None), Release(WIDE, "Theatrical", None)], LIMITED, None),
    # No wide release in the country means no run, even with a limited one.
    ([limited(LIMITED, "IMAX")], LIMITED, None),
    ([], WIDE, None),
    # The earliest wide release counts when TMDB lists more than one.
    (wide(WIDE, Release(date(2027, 3, 5), "Theatrical", "re-release")), SUNDAY, Run("wide", WIDE, None)),
    (wide(WIDE, Release(date(2027, 3, 5), "Theatrical", "re-release")), date(2027, 3, 5), None),
])
def test_theater_run(releases, today, expected):
    assert section.theater_run(releases, today) == expected


def movie(title="Harbor Lights", *, tmdb_id=700001, cinemas=LIMITED, grabbed=False, monitored=True, runtime=112):
    return radarr.RadarrMovie(
        tmdb_id=tmdb_id, title=title, year=2026, in_cinemas=cinemas, digital_release=None, grabbed=grabbed,
        monitored=monitored, runtime_min=runtime, poster_url=f"https://images.example/{title}.jpg",
    )


class FakeRadarr:
    def __init__(self, movies):
        self.movies, self.asked = movies, []

    def calendar(self, start, end):
        self.asked.append((start, end))
        return self.movies  # unfiltered: the section must apply the rule itself


class FakeTmdb:
    def __init__(self, releases=None):
        self.by_id, self.asked = releases or {}, []

    def releases(self, tmdb_id, today):
        self.asked.append(tmdb_id)
        return self.by_id.get(tmdb_id, RELEASES)


class FakePosters:
    def poster(self, path, width, height):
        return f"{path}@{width}x{height}".encode()


def at(d, hour=19, minute=30):
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=EASTERN)


def build(movies, now=at(WIDE), releases=None, posters=None):
    return section.in_theaters(FakeRadarr(movies), FakeTmdb(releases), posters or FakePosters(), now)


def titles(result):
    return [item["title"] for item in result["items"]]


def test_item_maps_to_the_payload_contract():
    assert build([movie()], now=at(day(LIMITED, 1))) == {"stale": False, "items": [{
        "title": "Harbor Lights", "stage": "limited", "note": "IMAX", "since": "2026-11-03", "days_ago": 1,
        "runtime_min": 112,
        "poster": "data:image/jpeg;base64,"
                  + base64.b64encode(b"https://images.example/Harbor Lights.jpg@234x351").decode(),
    }]}


@pytest.mark.parametrize("today, stage, days_ago", [
    (LIMITED, "limited", 0),
    (day(LIMITED, 2), "limited", 2),
    (WIDE, "wide", 0),  # the wide release starts the count again
    (day(WIDE, 1), "wide", 1),
    (SUNDAY, "wide", 2),
])
def test_days_ago_counts_from_the_current_stage(today, stage, days_ago):
    [item] = build([movie()], now=at(today))["items"]
    assert (item["stage"], item["days_ago"]) == (stage, days_ago)


def test_candidates_come_from_the_last_90_days():
    calendar = FakeRadarr([
        movie("In range", tmdb_id=1, cinemas=day(WIDE, -90)),
        movie("Too old", tmdb_id=2, cinemas=day(WIDE, -91)),
        movie("Not yet anywhere", tmdb_id=3, cinemas=day(WIDE, 1)),
        movie("No date", tmdb_id=4, cinemas=None),
    ])
    lookups = FakeTmdb({n: wide(WIDE) for n in (1, 2, 3, 4)})
    result = section.in_theaters(calendar, lookups, FakePosters(), at(WIDE))

    assert calendar.asked == [(day(WIDE, -90), day(WIDE, 1))]
    assert titles(result) == ["In range"]
    assert lookups.asked == [1]  # only candidates cost a TMDB lookup


def test_only_monitored_movies_not_yet_grabbed():
    result = build([movie("Wanted", tmdb_id=1), movie("Grabbed", tmdb_id=2, grabbed=True),
                    movie("Unmonitored", tmdb_id=3, monitored=False)])
    assert titles(result) == ["Wanted"]


def test_newest_run_first_then_by_title():
    result = build([
        movie("Bravo", tmdb_id=1), movie("Older", tmdb_id=2), movie("Alpha", tmdb_id=3),
    ], now=at(SUNDAY), releases={2: wide(day(WIDE, -2))})
    assert titles(result) == ["Alpha", "Bravo", "Older"]


def test_nothing_in_a_run_means_no_section():
    assert build([movie()], now=at(day(SUNDAY, 1))) is None


@pytest.mark.parametrize("now, stage", [
    pytest.param(at(day(WIDE, -1), 23, 59), "limited", id="a minute before local midnight"),
    pytest.param(at(WIDE, 0, 0), "wide", id="local midnight"),
])
def test_today_is_the_local_calendar_day(now, stage):
    # 23:59 Eastern is already the next day in UTC; the run must follow the local day.
    assert build([movie()], now=now)["items"][0]["stage"] == stage


def test_the_run_ends_at_the_end_of_sunday():
    assert build([movie()], now=at(SUNDAY, 23, 59)) is not None
    assert build([movie()], now=at(day(SUNDAY, 1), 0, 0)) is None


class DownTmdb:
    def releases(self, tmdb_id, today):
        raise tmdb.TmdbError("TMDB returned HTTP 503")


def test_a_tmdb_failure_fails_the_section():
    # The runner then shows the last good data marked stale, with "tmdb" in errors[].
    with pytest.raises(tmdb.TmdbError):
        section.in_theaters(FakeRadarr([movie()]), DownTmdb(), FakePosters(), at(WIDE))


class DownPosters:
    def poster(self, path, width, height):
        raise plex.PlexError("Plex request failed: ConnectError")


def test_movies_lose_their_posters_when_plex_is_down():
    assert [i["poster"] for i in build([movie()], posters=DownPosters())["items"]] == [None]
