"""Pushes a payload to a LaraPaper webhook."""

from typing import Any, Callable

import httpx

Push = Callable[[str, dict[str, Any], "str | None"], None]


class PushError(Exception):
    """A failed push. The message never contains the webhook URL, which holds a secret UUID."""


def push(url: str, payload: dict[str, Any], merge_strategy: str | None = None) -> None:
    # Without merge_strategy, LaraPaper replaces the stored data (docs/research/larapaper-deploy.md).
    body = {"merge_variables": payload}
    if merge_strategy:
        body["merge_strategy"] = merge_strategy
    try:
        response = httpx.post(url, json=body, timeout=30)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise PushError(f"LaraPaper returned HTTP {e.response.status_code}") from None
    except httpx.HTTPError as e:
        # httpx messages and chained causes can include the URL, so keep only the error type.
        raise PushError(f"push failed: {type(e).__name__}") from None
