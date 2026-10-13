import importlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent

collect = discover_screens()["media"]
media = importlib.import_module("trmnl_screens.media.collector")
sonarr = importlib.import_module("trmnl_screens.media.collector.sources.sonarr")


class EmptyPlex:
    def __init__(self, url, token):
        pass

    def continue_watching(self):
        return []


class EmptySonarr:
    def __init__(self, url, api_key):
        pass

    def calendar(self, start, end):
        return []


class EmptyRadarr:
    def __init__(self, url, api_key):
        pass

    def calendar(self, start, end):
        return []


@pytest.fixture
def empty_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    for key in ("PLEX_URL", "PLEX_TOKEN", "SONARR_URL", "SONARR_API_KEY", "RADARR_URL", "RADARR_API_KEY"):
        monkeypatch.setenv(key, "placeholder")
    monkeypatch.setattr(media, "PlexSource", EmptyPlex)
    monkeypatch.setattr(media, "SonarrSource", EmptySonarr)
    monkeypatch.setattr(media, "RadarrSource", EmptyRadarr)


def test_updated_at_is_local_time_with_offset(empty_sources):
    updated_at = datetime.fromisoformat(collect()["updated_at"])
    assert updated_at.utcoffset() is not None


def test_empty_sections_are_left_out(empty_sources):
    assert collect().keys() == {"updated_at", "errors"}


class AiringSonarr(EmptySonarr):
    def calendar(self, start, end):
        return [sonarr.SonarrEpisode(
            series="Night Market", series_id=100, season=2, number=4, title="Lanterns", air_time=start + (end - start) / 2,
            runtime_min=44, grabbed=False, monitored=True, series_monitored=True, finale=None, poster_url=None,
        )]


class DownSonarr(EmptySonarr):
    def calendar(self, start, end):
        raise sonarr.SonarrError("Sonarr returned HTTP 503")


def test_a_failing_source_keeps_its_last_good_section_marked_stale(empty_sources, monkeypatch):
    monkeypatch.setattr(media, "SonarrSource", AiringSonarr)
    assert collect()["airing"]["stale"] is False

    monkeypatch.setattr(media, "SonarrSource", DownSonarr)
    payload = collect()

    assert payload["airing"]["stale"] is True
    assert payload["airing"]["items"][0]["series"] == "Night Market"
    assert [e["source"] for e in payload["errors"]] == ["sonarr"]


def test_sample_fixture_covers_every_payload_key():
    sample = json.loads((SCREEN / "fixtures" / "sample.json").read_text())
    assert set(sample) == {"updated_at", "errors", "continue_watching", "airing", "in_theaters", "streaming"}
    for section in ("continue_watching", "airing", "in_theaters", "streaming"):
        assert {"stale", "items"} <= set(sample[section])
