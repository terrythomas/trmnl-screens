import os
import sys

import pytest

import collector.__main__ as entry
from collector.discovery import Screen


@pytest.fixture
def run(monkeypatch):
    """Run main() with the given args and webhook env, against one fake screen."""

    def _run(args, env, load=lambda name, init: Screen(lambda: {})):
        monkeypatch.setattr(entry, "load_dotenv", lambda: None)
        monkeypatch.setattr(entry, "find_screens", lambda: {"media": "media/collector/__init__.py"})
        monkeypatch.setattr(entry, "load_screen", load)
        monkeypatch.setattr(entry, "push", lambda url, payload, merge_strategy=None: None)
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


def test_exits_with_an_error_naming_a_screens_missing_module(run, capsys):
    def load(name, init):
        raise ModuleNotFoundError("No module named 'feedparser'", name="feedparser")

    with pytest.raises(SystemExit) as exit:
        run(["--once"], {"MEDIA_WEBHOOK_UUID": "media-uuid"}, load=load)
    assert exit.value.code == 2
    err = capsys.readouterr().err
    assert "screen media needs feedparser" in err
    assert "pip install '.[media]'" in err


def test_a_disabled_screen_is_never_imported(run):
    loaded = []

    def load(name, init):
        loaded.append(name)
        return Screen(lambda: {})

    with pytest.raises(SystemExit):
        run(["--once"], {}, load=load)
    assert loaded == []


def test_a_missing_module_of_the_screens_own_is_not_blamed_on_an_extra(run):
    def load(name, init):
        raise ModuleNotFoundError(name="trmnl_screens.media.collector.typo")

    with pytest.raises(ModuleNotFoundError):
        run(["--once"], {"MEDIA_WEBHOOK_UUID": "media-uuid"}, load=load)
