import importlib
import json
from pathlib import Path

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
parcel = importlib.import_module("trmnl_screens.wheres-my-stuff.collector.sources.parcel")

RECORDINGS = Path(__file__).parent / "recordings"
RECENT = json.loads((RECORDINGS / "parcel_recent.json").read_text())
CARRIERS = json.loads((RECORDINGS / "parcel_carriers.json").read_text())


def source(handler):
    return parcel.ParcelSource("test-key", transport=httpx.MockTransport(handler))


def replay(body, status=200):
    return lambda request: httpx.Response(status, json=body)


def test_deliveries_asks_for_recent_with_the_key_header():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(200, json=RECENT)

    deliveries = source(handler).deliveries()

    [request] = requested
    assert (request.method, request.url.host, request.url.path) == ("GET", "api.parcel.app", "/external/deliveries/")
    assert request.url.params["filter_mode"] == "recent"
    assert request.headers["api-key"] == "test-key"
    assert deliveries == RECENT["deliveries"]


def test_carriers_maps_code_to_name():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(200, json=CARRIERS)

    carriers = source(handler).carriers()

    [request] = requested
    assert request.url.path == "/external/supported_carriers.json"
    assert "api-key" not in request.headers
    assert carriers["ups"] == "UPS"
    assert carriers["amzlus"] == "Amazon"


def test_unsuccessful_body_raises():
    with pytest.raises(parcel.ParcelError) as e:
        source(replay({"success": False, "error_message": "Invalid API key"})).deliveries()
    assert str(e.value) == "Parcel said: Invalid API key"


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_is_its_own_error(status):
    with pytest.raises(parcel.ParcelKeyError) as e:
        source(replay({}, status)).deliveries()
    assert str(e.value) == "Parcel rejected the API key"
    assert e.value.source == "parcel-key"


def test_http_error_hides_url_and_key():
    with pytest.raises(parcel.ParcelError) as e:
        source(replay({}, 500)).deliveries()
    assert str(e.value) == "Parcel returned HTTP 500"

    def refuse(request):
        raise httpx.ConnectError("connection refused to https://api.parcel.app/external/deliveries/", request=request)

    with pytest.raises(parcel.ParcelError) as e:
        source(refuse).deliveries()
    assert str(e.value) == "Parcel request failed: ConnectError"
    assert "test-key" not in str(e.value) and "api.parcel.app" not in str(e.value)
    assert e.value.__cause__ is None


@pytest.mark.parametrize("body", [[], {"success": True}])
def test_unexpected_body_raises(body):
    with pytest.raises(parcel.ParcelError) as e:
        source(replay(body)).deliveries()
    assert str(e.value) == "Parcel returned an unexpected response"
