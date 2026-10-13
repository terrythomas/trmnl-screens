import importlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from collector.discovery import discover_screens

SCREEN = Path(__file__).resolve().parent.parent

collect = discover_screens()["media"]
media = importlib.import_module("trmnl_screens.media.collector")


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


@pytest.fixture
def empty_sources(monkeypatch):
    for key in ("PLEX_URL", "PLEX_TOKEN", "SONARR_URL", "SONARR_API_KEY"):
        monkeypatch.setenv(key, "placeholder")
    monkeypatch.setattr(media, "PlexSource", EmptyPlex)
    monkeypatch.setattr(media, "SonarrSource", EmptySonarr)


def test_updated_at_is_local_time_with_offset(empty_sources):
    updated_at = datetime.fromisoformat(collect()["updated_at"])
    assert updated_at.utcoffset() is not None


def test_empty_sections_are_left_out(empty_sources):
    assert set(collect()) == {"updated_at"}


def test_sample_fixture_covers_every_payload_key():
    sample = json.loads((SCREEN / "fixtures" / "sample.json").read_text())
    assert set(sample) == {"updated_at", "errors", "continue_watching", "airing", "releasing_today"}
    for section in ("continue_watching", "airing", "releasing_today"):
        assert {"stale", "items"} <= set(sample[section])
