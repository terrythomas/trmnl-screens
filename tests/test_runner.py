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

    def __call__(self, url, payload):
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


def test_a_screen_without_a_webhook_is_logged_once_as_off(caplog):
    caplog.set_level("INFO")
    enabled_screens({"unknown": lambda: {}}, CONFIG)
    assert [r.getMessage() for r in caplog.records] == [
        "screen unknown: off (set UNKNOWN_WEBHOOK_UUID to enable it)"
    ]
    assert caplog.records[0].levelname == "INFO"


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


def run_schedule(intervals, stop_after, run_seconds=0.0):
    clock = FakeClock(stop_after)
    runs = []

    def run(names):
        runs.append((clock.now, names))
        clock.now += run_seconds

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


def test_run_forever_lets_unexpected_errors_escape():
    def run(names):
        raise RuntimeError("bug")

    try:
        run_forever({"media": 900}, run, sleep=lambda s: None)
    except RuntimeError as e:
        assert str(e) == "bug"
    else:
        raise AssertionError("expected the error to escape")
