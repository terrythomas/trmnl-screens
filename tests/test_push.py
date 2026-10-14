import logging

import httpx
import pytest

from collector.config import Config
from collector.push import PushError, push
from collector.runner import run_tick

SECRET = "secret-webhook-uuid"


def fake_post(response=None, error=None):
    def post(url, **kwargs):
        if error:
            raise error
        response.request = httpx.Request("POST", url)
        return response
    return post


@pytest.mark.parametrize("post", [
    fake_post(response=httpx.Response(404)),
    fake_post(error=httpx.ConnectError(f"cannot reach http://larapaper.example/api/custom_plugins/{SECRET}")),
])
def test_failed_push_never_logs_the_webhook_uuid(monkeypatch, caplog, post):
    monkeypatch.setattr(httpx, "post", post)
    config = Config(larapaper_url="http://larapaper.example", webhook_uuids={"media": SECRET})

    with caplog.at_level(logging.DEBUG):
        results = run_tick({"media": lambda: {}}, config, push)

    assert results == {"media": False}
    assert "media" in caplog.text
    assert SECRET not in caplog.text


def test_push_error_reports_status(monkeypatch):
    monkeypatch.setattr(httpx, "post", fake_post(response=httpx.Response(413)))
    with pytest.raises(PushError, match="HTTP 413"):
        push(f"http://larapaper.example/api/custom_plugins/{SECRET}", {})


@pytest.mark.parametrize("strategy, body", [
    (None, {"merge_variables": {"a": 1}}),
    ("deep_merge", {"merge_variables": {"a": 1}, "merge_strategy": "deep_merge"}),
])
def test_push_sends_the_merge_strategy_only_when_set(monkeypatch, strategy, body):
    sent = {}

    def post(url, json, **kwargs):
        sent.update(json)
        return httpx.Response(200, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)

    push("http://larapaper.example/api/custom_plugins/x", {"a": 1}, strategy)
    assert sent == body
