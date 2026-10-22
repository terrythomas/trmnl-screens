from collector.config import Config


def test_reads_webhooks_per_screen_from_env():
    config = Config.from_env({
        "LARAPAPER_URL": "http://larapaper.example/",
        "MEDIA_WEBHOOK_UUID": "abc",
        "WEATHER_WEBHOOK_UUID": "def",
        "EMPTY_WEBHOOK_UUID": "",
        "INTERVAL_MINUTES": "5",
    })
    assert config.webhook_uuids == {"media": "abc", "weather": "def"}
    assert config.interval_minutes == 5
    assert config.webhook_url("media") == "http://larapaper.example/api/custom_plugins/abc"
    assert config.webhook_url("missing") is None


def config(**env):
    return Config.from_env({"LARAPAPER_URL": "http://x.example", **env})


def test_a_screen_interval_beats_the_global_one():
    c = config(INTERVAL_MINUTES="5", MEDIA_INTERVAL_MINUTES="30")
    assert c.interval_minutes_for("media", default=60) == 30
    assert c.interval_minutes_for("other", default=60) == 5


def test_the_screen_default_applies_when_no_interval_is_set():
    assert config().interval_minutes_for("media", default=60) == 60


def test_interval_falls_back_to_15_minutes():
    assert config().interval_minutes_for("media", default=None) == 15


def test_empty_interval_values_are_ignored():
    c = config(INTERVAL_MINUTES="", MEDIA_INTERVAL_MINUTES="")
    assert c.interval_minutes_for("media", default=60) == 60


def test_a_hyphenated_screen_reads_underscored_variables():
    c = config(GAME_TIME_WEBHOOK_UUID="abc", GAME_TIME_INTERVAL_MINUTES="30")
    assert c.webhook_url("game-time") == "http://x.example/api/custom_plugins/abc"
    assert c.interval_minutes_for("game-time", default=60) == 30
