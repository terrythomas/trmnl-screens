import logging

import pytest

from collector.config import Config
from collector.runner import enabled_screens, run_forever, run_tick

CONFIG = Config(
    larapaper_url="http://larapaper.example",
    webhook_uuids={"media": "media-uuid", "other": "other-uuid"},
)


class FakePush:
    def __init__(self, fail_for=()):
        self.calls = []
        self.fail_for = fail_for

    def __call__(self, url, payload, merge_strategy=None):
        if any(url.endswith(uuid) for uuid in self.fail_for):
            raise ConnectionError("LaraPaper unreachable")
        self.calls.append((url, payload))


def test_pushes_each_screen_payload_to_its_webhook():
    push = FakePush()
    run_tick({"media": lambda: {"a": 1}, "other": lambda: {"b": 2}}, CONFIG, push)
    assert push.calls == [
        ("http://larapaper.example/api/custom_plugins/media-uuid", {"a": 1}),
        ("http://larapaper.example/api/custom_plugins/other-uuid", {"b": 2}),
    ]


def test_passes_each_screen_its_merge_strategy():
    seen = []
    run_tick({"media": lambda: {}, "other": lambda: {}}, CONFIG,
             lambda url, payload, merge_strategy=None: seen.append(merge_strategy), {"other": "deep_merge"})
    assert seen == [None, "deep_merge"]


def test_a_failing_collector_does_not_block_other_screens():
    def broken():
        raise RuntimeError("source down")

    push = FakePush()
    results = run_tick({"media": broken, "other": lambda: {"b": 2}}, CONFIG, push)
    assert results == {"media": False, "other": True}
    assert [url for url, _ in push.calls] == ["http://larapaper.example/api/custom_plugins/other-uuid"]


def test_a_failing_push_does_not_block_other_screens():
    push = FakePush(fail_for=["media-uuid"])
    results = run_tick({"media": lambda: {}, "other": lambda: {}}, CONFIG, push)
    assert results == {"media": False, "other": True}


def test_screen_without_webhook_is_skipped():
    push = FakePush()
    results = run_tick({"unknown": lambda: {}}, CONFIG, push)
    assert results == {"unknown": False}
    assert push.calls == []


def test_only_screens_with_a_webhook_are_enabled():
    def media():
        return {}

    screens = enabled_screens({"media": media, "unknown": lambda: {}}, CONFIG)
    assert screens == {"media": media}


def test_a_screen_can_ask_for_its_next_run_in_seconds_from_its_payload():
    seen, sooner = [], {}
    run_tick({"media": lambda: {"live": True}, "other": lambda: {}}, CONFIG, FakePush(),
             next_runs={"media": lambda payload: seen.append(payload) or 5, "other": lambda payload: None},
             sooner=sooner)
    assert seen == [{"live": True}]
    assert sooner == {"media": 300}


def test_a_failing_screen_asks_for_nothing():
    sooner = {}
    run_tick({"media": lambda: {}}, CONFIG, FakePush(fail_for=["media-uuid"]),
             next_runs={"media": lambda payload: 5}, sooner=sooner)
    assert sooner == {}


@pytest.mark.parametrize("answer", [0, -5, "5", True, float("nan")])
def test_a_bad_answer_keeps_the_interval_and_is_logged(answer, caplog):
    sooner = {}
    results = run_tick({"media": lambda: {}}, CONFIG, FakePush(), next_runs={"media": lambda payload: answer},
                       sooner=sooner)
    assert results == {"media": True}
    assert sooner == {}
    assert [r.levelname for r in caplog.records if "next_run_minutes" in r.getMessage()] == ["WARNING"]


def test_no_answer_keeps_the_interval_without_a_warning(caplog):
    sooner = {}
    run_tick({"media": lambda: {}}, CONFIG, FakePush(), next_runs={"media": lambda payload: None}, sooner=sooner)
    assert sooner == {}
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_an_answer_under_a_minute_is_raised_to_a_minute():
    sooner = {}
    run_tick({"media": lambda: {}}, CONFIG, FakePush(), next_runs={"media": lambda payload: 0.01}, sooner=sooner)
    assert sooner == {"media": 60}


def test_a_failing_hook_keeps_the_interval_and_the_push_counts(caplog):
    def broken(payload):
        raise KeyError("games")

    push, sooner = FakePush(), {}
    results = run_tick({"media": lambda: {}}, CONFIG, push, next_runs={"media": broken}, sooner=sooner)
    assert results == {"media": True}
    assert len(push.calls) == 1
    assert sooner == {}
    assert any("next_run_minutes" in r.getMessage() and r.exc_info for r in caplog.records)


def test_a_screen_without_a_webhook_is_logged_once_as_off(caplog):
    caplog.set_level("INFO")
    enabled_screens({"unknown": lambda: {}}, CONFIG)
    assert [r.getMessage() for r in caplog.records] == [
        "screen unknown: off (set UNKNOWN_WEBHOOK_UUID to enable it)"
    ]
    assert caplog.records[0].levelname == "INFO"


def test_names_a_dashed_screen_s_variable_as_config_reads_it(caplog):
    caplog.set_level("INFO")
    enabled_screens({"game-time": lambda: {}}, CONFIG)
    run_tick({"game-time": lambda: {}}, CONFIG, FakePush())
    assert [r.getMessage() for r in caplog.records] == [
        "screen game-time: off (set GAME_TIME_WEBHOOK_UUID to enable it)",
        "screen game-time: no GAME_TIME_WEBHOOK_UUID set, skipping",
    ]


class StopLoop(Exception):
    pass


class FakeClock:
    """A monotonic clock that only moves when the loop sleeps or a run takes time."""

    def __init__(self, stop_after):
        self.now = 0.0
        self.stop_after = stop_after

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.now > self.stop_after:
            raise StopLoop


def run_schedule(intervals, stop_after, run_seconds=0.0, asks=lambda at, names: {}):
    clock = FakeClock(stop_after)
    runs = []

    def run(names):
        runs.append((clock.now, names))
        at = clock.now
        clock.now += run_seconds
        return asks(at, names)

    try:
        run_forever(intervals, run, clock=clock, sleep=clock.sleep)
    except StopLoop:
        pass
    return runs


def test_every_screen_runs_at_startup_then_on_its_own_interval():
    runs = run_schedule({"fast": 60, "slow": 180}, stop_after=180)
    assert runs == [
        (0, ["fast", "slow"]),
        (60, ["fast"]),
        (120, ["fast"]),
        (180, ["fast", "slow"]),
    ]


def test_each_interval_starts_when_the_run_ends():
    runs = run_schedule({"media": 900}, stop_after=1900, run_seconds=10)
    assert [at for at, _ in runs] == [0, 910, 1820]


def test_a_screen_that_asks_sooner_runs_sooner_until_it_stops_asking():
    # "live" asks for 5 minutes while its game is on, from 0 to 600 seconds.
    runs = run_schedule(
        {"live": 3600, "media": 900}, stop_after=3600,
        asks=lambda at, names: {"live": 300} if "live" in names and at < 600 else {},
    )
    assert runs == [
        (0, ["live", "media"]),
        (300, ["live"]),
        (600, ["live"]),
        (900, ["media"]),
        (1800, ["media"]),
        (2700, ["media"]),
        (3600, ["media"]),
    ]


def test_a_sooner_request_counts_from_the_end_of_the_run():
    runs = run_schedule({"live": 3600}, stop_after=700, run_seconds=10, asks=lambda at, names: {"live": 300})
    assert [at for at, _ in runs] == [0, 310, 620]


def test_a_request_later_than_the_interval_does_not_delay_the_run():
    runs = run_schedule({"media": 900}, stop_after=1800, asks=lambda at, names: {"media": 7200})
    assert [at for at, _ in runs] == [0, 900, 1800]


def test_run_forever_lets_unexpected_errors_escape():
    def run(names):
        raise RuntimeError("bug")

    try:
        run_forever({"media": 900}, run, sleep=lambda s: None)
    except RuntimeError as e:
        assert str(e) == "bug"
    else:
        raise AssertionError("expected the error to escape")
