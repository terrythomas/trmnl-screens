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


@pytest.fixture
def empty_plex(monkeypatch):
    monkeypatch.setenv("PLEX_URL", "http://plex.example:32400")
    monkeypatch.setenv("PLEX_TOKEN", "secret-plex-token")
    monkeypatch.setattr(media, "PlexSource", EmptyPlex)


def test_updated_at_is_local_time_with_offset(empty_plex):
    updated_at = datetime.fromisoformat(collect()["updated_at"])
    assert updated_at.utcoffset() is not None


def test_empty_continue_watching_is_left_out(empty_plex):
    assert "continue_watching" not in collect()


def test_sample_fixture_covers_every_payload_key():
    sample = json.loads((SCREEN / "fixtures" / "sample.json").read_text())
    assert set(sample) == {"updated_at", "errors", "continue_watching", "airing", "releasing_today"}
    for section in ("continue_watching", "airing", "releasing_today"):
        assert {"stale", "items"} <= set(sample[section])
