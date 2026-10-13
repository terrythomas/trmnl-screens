import base64
import importlib
import zlib
from datetime import datetime, timedelta, timezone

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
section = importlib.import_module("trmnl_screens.media.collector.airing")
sonarr = importlib.import_module("trmnl_screens.media.collector.sources.sonarr")
plex = importlib.import_module("trmnl_screens.media.collector.sources.plex")

EASTERN = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 12, 14, 30, tzinfo=EASTERN)
HOUR = timedelta(hours=1)


def episode(series="Night Market", season=2, number=4, *, at=NOW - HOUR, title="An Episode", runtime=44,
            grabbed=False, monitored=True, series_monitored=True, finale=None, series_id=None):
    return sonarr.SonarrEpisode(
        series=series, series_id=series_id or zlib.crc32(series.encode()), season=season, number=number, title=title,
        air_time=at.astimezone(timezone.utc), runtime_min=runtime, grabbed=grabbed, monitored=monitored,
        series_monitored=series_monitored, finale=finale, poster_url=f"https://artworks.example/{series}.jpg",
    )


class FakeSonarr:
    def __init__(self, episodes):
        self.episodes, self.asked = episodes, []

    def calendar(self, start, end):
        self.asked.append((start, end))
        return self.episodes  # unfiltered: the section must apply the window itself


class FakePosters:
    def poster(self, path, width, height):
        return f"{path}@{width}x{height}".encode()


def build(episodes):
    return section.airing(FakeSonarr(episodes), FakePosters(), NOW)


def series_of(result):
    return [row["series"] for row in result["items"]]


def test_asks_sonarr_for_twelve_hours_either_side():
    calendar = FakeSonarr([episode()])
    section.airing(calendar, FakePosters(), NOW)
    assert calendar.asked == [(NOW - 12 * HOUR, NOW + 12 * HOUR)]


def test_window_includes_both_edges_and_nothing_beyond():
    second = timedelta(seconds=1)
    result = build([
        episode("Just before", at=NOW - 12 * HOUR - second),
        episode("Earliest", at=NOW - 12 * HOUR),
        episode("Latest", at=NOW + 12 * HOUR),
        episode("Just after", at=NOW + 12 * HOUR + second),
    ])
    assert series_of(result) == ["Earliest", "Latest"]


def test_only_monitored_episodes_of_monitored_series():
    result = build([
        episode("Watched for", monitored=True, series_monitored=True),
        episode("Episode unmonitored", monitored=False),
        episode("Series unmonitored", series_monitored=False),
    ])
    assert series_of(result) == ["Watched for"]


def poster_uri(url):
    return "data:image/jpeg;base64," + base64.b64encode(f"{url}@234x351".encode()).decode()


def test_row_maps_to_the_payload_contract_in_local_time():
    result = build([
        episode("Copper Valley", 3, 5, title="Lanterns", at=NOW + 6 * HOUR + timedelta(minutes=30),
                runtime=44, grabbed=False),
    ])
    assert result == {"stale": False, "items": [{
        "series": "Copper Valley", "season": 3, "number": 5, "number_end": None, "title": "Lanterns",
        "air_time": "2026-10-12T21:00:00-04:00", "aired": False, "grabbed": False,
        "runtime_min": 44, "milestone": None, "poster": poster_uri("https://artworks.example/Copper Valley.jpg"),
    }]}


def test_aired_and_grabbed_and_sorted_by_air_time():
    result = build([
        episode("Later", at=NOW + 2 * HOUR),
        episode("Earlier", at=NOW - 3 * HOUR, grabbed=True),
        episode("Right now", at=NOW),
    ])
    assert [(r["series"], r["aired"], r["grabbed"]) for r in result["items"]] == [
        ("Earlier", True, True), ("Right now", True, False), ("Later", False, False),
    ]


def test_series_without_a_poster_gets_none():
    no_poster = episode("Bare")
    no_poster = sonarr.SonarrEpisode(**{**no_poster.__dict__, "poster_url": None})
    assert build([no_poster])["items"][0]["poster"] is None


def test_nothing_airing_means_no_section():
    assert build([episode(monitored=False)]) is None


def drop(series="Night Market", season=2, numbers=range(1, 9), at=NOW - 2 * HOUR, **kwargs):
    return [episode(series, season, n, at=at, title=f"Episode {n}", runtime=40 + n, **kwargs) for n in numbers]


def test_a_season_drop_collapses_into_one_row():
    [row] = build(drop())["items"]
    assert (row["season"], row["number"], row["number_end"], row["title"], row["runtime_min"]) == (2, 1, 8, None, 41)


def test_a_drop_is_grabbed_only_when_every_episode_is():
    partly = drop(numbers=[1, 2]) + [episode("Night Market", 2, 3, at=NOW - 2 * HOUR, grabbed=True)]
    fully = drop(numbers=[1, 2, 3], grabbed=True)
    assert build(partly)["items"][0]["grabbed"] is False
    assert build(fully)["items"][0]["grabbed"] is True


def test_only_the_same_series_season_and_air_time_collapse():
    rows = build(
        drop(numbers=[1, 2])
        + drop("Field Notes", numbers=[1, 2])  # another series at the same time
        + drop(season=3, numbers=[1, 2])  # another season of the same series
        + drop(numbers=[3, 4], at=NOW - HOUR)  # the same season, an hour later
    )["items"]
    assert [(r["series"], r["season"], r["number"], r["number_end"]) for r in rows] == [
        ("Night Market", 2, 1, 2), ("Field Notes", 2, 1, 2), ("Night Market", 3, 1, 2), ("Night Market", 2, 3, 4),
    ]


def with_finale(episodes, finale):
    *rest, last = episodes
    return rest + [sonarr.SonarrEpisode(**{**last.__dict__, "finale": finale})]


@pytest.mark.parametrize("episodes, expected", [
    pytest.param([episode(season=1, number=1)], "series_premiere", id="S1E1"),
    pytest.param([episode(season=3, number=1)], "season_premiere", id="S3E1"),
    pytest.param([episode(number=10, finale="season")], "season_finale", id="season finale"),
    pytest.param([episode(number=10, finale="series")], "series_finale", id="series finale"),
    pytest.param([episode(number=5, finale="midseason")], "midseason_finale", id="midseason finale"),
    pytest.param([episode(season=1, number=1, finale="series")], "series_finale", id="a one-episode series ends"),
    pytest.param([episode(number=4)], None, id="ordinary episode"),
    pytest.param(with_finale(drop(), "season"), "entire_season", id="whole season drop"),
    pytest.param(with_finale(drop(season=1), "series"), "entire_season", id="whole miniseries drop"),
    pytest.param(drop(season=3, numbers=range(1, 5)), "season_premiere", id="first batch of a season"),
    pytest.param(drop(season=1, numbers=range(1, 5)), "series_premiere", id="first batch of a series"),
    pytest.param(with_finale(drop(numbers=range(5, 9)), "season"), "season_finale", id="last batch of a season"),
    pytest.param(drop(season=3), "season_premiere", id="whole drop not yet marked with a finale"),
])
def test_milestone(episodes, expected):
    [row] = build(episodes)["items"]
    assert row["milestone"] == expected


class DownPosters:
    def poster(self, path, width, height):
        raise plex.PlexError("Plex request failed: ConnectError")


def test_rows_lose_their_posters_when_plex_is_down():
    result = section.airing(FakeSonarr([episode("Copper Valley")]), DownPosters(), NOW)
    assert [(r["series"], r["poster"]) for r in result["items"]] == [("Copper Valley", None)]
