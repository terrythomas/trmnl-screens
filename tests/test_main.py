import os
import sys

import pytest

import collector.__main__ as entry
from collector.discovery import Screen


@pytest.fixture
def run(monkeypatch):
    """Run main() with the given args and webhook env, against one fake screen."""

    def _run(args, env):
        monkeypatch.setattr(entry, "load_dotenv", lambda: None)
        monkeypatch.setattr(entry, "discover_screens", lambda: {"media": Screen(lambda: {})})
        monkeypatch.setattr(entry, "push", lambda url, payload: None)
        for key in list(os.environ):
            if key.endswith(("_WEBHOOK_UUID", "INTERVAL_MINUTES")):
                monkeypatch.delenv(key)
        for key, value in {"LARAPAPER_URL": "http://larapaper.example", **env}.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr(sys, "argv", ["collector", *args])
        return entry.main()

    return _run


def test_exits_with_an_error_when_no_screen_is_enabled(run, capsys):
    with pytest.raises(SystemExit) as exit:
        run(["--once"], {})
    assert exit.value.code == 2
    assert "no screens enabled" in capsys.readouterr().err


def test_exits_with_an_error_when_the_named_screen_is_off(run, capsys):
    with pytest.raises(SystemExit) as exit:
        run(["--once", "--screen", "deals"], {"MEDIA_WEBHOOK_UUID": "media-uuid"})
    assert exit.value.code == 2
    assert "screen deals is not enabled" in capsys.readouterr().err


def test_runs_an_enabled_screen_once(run):
    assert run(["--once"], {"MEDIA_WEBHOOK_UUID": "media-uuid"}) == 0
