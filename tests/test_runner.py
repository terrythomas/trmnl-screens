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


def test_run_forever_ticks_immediately_then_after_each_interval():
    events = []

    def sleep(seconds):
        events.append(("sleep", seconds))
        if len(events) >= 4:
            raise StopLoop

    try:
        run_forever(lambda: events.append("tick"), 900, sleep=sleep)
    except StopLoop:
        pass
    assert events == ["tick", ("sleep", 900), "tick", ("sleep", 900)]


def test_run_forever_lets_unexpected_errors_escape():
    def tick():
        raise RuntimeError("bug")

    try:
        run_forever(tick, 900, sleep=lambda s: None)
    except RuntimeError as e:
        assert str(e) == "bug"
    else:
        raise AssertionError("expected the error to escape")
