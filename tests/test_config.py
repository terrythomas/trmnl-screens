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


def test_interval_defaults_to_15_minutes():
    assert Config.from_env({"LARAPAPER_URL": "http://x.example"}).interval_minutes == 15
