"""Pushes a payload to a LaraPaper webhook."""

from typing import Any, Callable

import httpx

Push = Callable[[str, dict[str, Any]], None]


def push(url: str, payload: dict[str, Any]) -> None:
    # Without merge_strategy, LaraPaper replaces the stored data (docs/research/larapaper-deploy.md).
    response = httpx.post(url, json={"merge_variables": payload}, timeout=30)
    response.raise_for_status()
