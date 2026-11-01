import importlib

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
sources = importlib.import_module("trmnl_screens.hows-it-outside.collector.sources")
openmeteo = importlib.import_module("trmnl_screens.hows-it-outside.collector.sources.openmeteo")
nws = importlib.import_module("trmnl_screens.hows-it-outside.collector.sources.nws")
google = importlib.import_module("trmnl_screens.hows-it-outside.collector.sources.pollen")

LAT, LON = "12.3456789", "-98.7654321"  # invented

FORECAST = {
    "utc_offset_seconds": -14400, "timezone": "America/New_York",
    "current": {"time": "2026-10-31T09:15", "interval": 900, "temperature_2m": 48.2, "apparent_temperature": 43.1,
                "weather_code": 61, "wind_speed_10m": 18.3, "is_day": 1},
    "hourly": {"time": ["2026-10-31T09:00", "2026-10-31T10:00"], "temperature_2m": [48.0, 49.1],
               "apparent_temperature": [43.0, 44.2], "precipitation_probability": [70, None],
               "weather_code": [61, 3], "uv_index": [1.05, None], "wind_speed_10m": [18.0, 12.2], "is_day": [1, 1]},
    "daily": {"time": ["2026-10-31", "2026-11-01"], "sunrise": ["2026-10-31T07:27", "2026-11-01T06:28"],
              "sunset": ["2026-10-31T17:52", "2026-11-01T16:51"], "temperature_2m_max": [61.4, 58.0],
              "temperature_2m_min": [46.6, 44.0]},
}
ALERTS = {"type": "FeatureCollection", "features": [
    {"properties": {"event": "Wind Advisory", "severity": "Moderate", "status": "Actual", "messageType": "Alert",
                    "effective": "2026-10-31T06:00:00-04:00", "onset": "2026-10-31T09:00:00-04:00",
                    "ends": "2026-10-31T18:00:00-04:00", "expires": "2026-10-31T12:00:00-04:00"}},
    {"properties": {"event": "Flood Watch", "severity": "Severe", "status": "Actual", "messageType": "Update",
                    "effective": "2026-10-31T07:00:00-04:00", "onset": None, "ends": None,
                    "expires": "2026-10-31T19:00:00-04:00"}},
    {"properties": {"event": "Test Message", "severity": "Unknown", "status": "Test", "messageType": "Alert",
                    "effective": "2026-10-31T07:00:00-04:00", "onset": None, "ends": None, "expires": None}},
]}
POLLEN_DAY = {"date": {"year": 2026, "month": 10, "day": 31},
              "pollenTypeInfo": [{"code": "GRASS", "displayName": "Grass"}], "plantInfo": [{"code": "OAK", "displayName": "Oak"}]}


def capture(body, status=200):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json=body)

    return requests, httpx.MockTransport(handler)


def test_forecast_asks_for_fahrenheit_mph_two_days_and_returns_rows():
    requests, transport = capture(FORECAST)
    forecast = openmeteo.OpenMeteoSource(LAT, LON, "America/New_York", transport=transport).forecast()
    [r] = requests
    assert (r.url.host, r.url.path) == ("api.open-meteo.com", "/v1/forecast")
    assert {k: r.url.params[k] for k in ("latitude", "longitude", "temperature_unit", "wind_speed_unit",
                                         "forecast_days", "timezone")} == {
        "latitude": LAT, "longitude": LON, "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "forecast_days": "2", "timezone": "America/New_York"}
    assert forecast["current"] == {"temp": 48.2, "feels": 43.1, "code": 61, "wind": 18.3, "is_day": 1}
    assert forecast["hours"][1] == {"time": "2026-10-31T10:00", "temp": 49.1, "feels": 44.2, "precip": 0, "code": 3,
                                    "uv": 0, "wind": 12.2, "is_day": 1}
    assert forecast["days"][0] == {"date": "2026-10-31", "high": 61.4, "low": 46.6, "sunrise": "2026-10-31T07:27",
                                   "sunset": "2026-10-31T17:52"}


def test_air_reads_the_us_aqi():
    requests, transport = capture({"current": {"time": "2026-10-31T09:15", "us_aqi": 42}})
    assert openmeteo.OpenMeteoSource(LAT, LON, "America/New_York", transport=transport).air() == {"aqi": 42}
    assert requests[0].url.host == "air-quality-api.open-meteo.com"
    assert requests[0].url.params["current"] == "us_aqi"
    _, transport = capture({"current": {"time": "2026-10-31T09:15", "us_aqi": None}})
    assert openmeteo.OpenMeteoSource(LAT, LON, "America/New_York", transport=transport).air() is None


def test_alerts_name_the_project_and_keep_real_alerts():
    requests, transport = capture(ALERTS)
    alerts = nws.NwsSource(LAT, LON, transport=transport).alerts()
    [r] = requests
    assert (r.url.host, r.url.path, r.url.params["point"]) == ("api.weather.gov", "/alerts/active", "12.3457,-98.7654")
    assert "trmnl-screens" in r.headers["User-Agent"]
    assert alerts == [
        {"event": "Wind Advisory", "severity": "Moderate", "onset": "2026-10-31T09:00:00-04:00",
         "ends": "2026-10-31T18:00:00-04:00"},
        {"event": "Flood Watch", "severity": "Severe", "onset": "2026-10-31T07:00:00-04:00", "ends": None},
    ]


def test_pollen_sends_the_key_and_returns_today():
    requests, transport = capture({"regionCode": "US", "dailyInfo": [POLLEN_DAY]})
    assert google.PollenSource("test-key", LAT, LON, transport=transport).today() == POLLEN_DAY
    [r] = requests
    assert (r.url.host, r.url.path) == ("pollen.googleapis.com", "/v1/forecast:lookup")
    assert {k: r.url.params[k] for k in ("key", "days", "location.latitude", "location.longitude")} == {
        "key": "test-key", "days": "1", "location.latitude": LAT, "location.longitude": LON}


@pytest.mark.parametrize("status", [400, 403])
def test_a_rejected_pollen_key_is_reported_apart(status):
    _, transport = capture({"error": {"message": "API key not valid"}}, status)
    with pytest.raises(google.PollenKeyError) as e:
        google.PollenSource("test-key", LAT, LON, transport=transport).today()
    assert e.value.source == "google-pollen-key"


def refuse(request):
    raise httpx.ConnectError(f"cannot reach {request.url}")


@pytest.mark.parametrize("call", [
    lambda t: openmeteo.OpenMeteoSource(LAT, LON, "UTC", transport=t).forecast(),
    lambda t: openmeteo.OpenMeteoSource(LAT, LON, "UTC", transport=t).air(),
    lambda t: nws.NwsSource(LAT, LON, transport=t).alerts(),
    lambda t: google.PollenSource("test-key", LAT, LON, transport=t).today(),
])
@pytest.mark.parametrize("transport", [
    httpx.MockTransport(refuse), httpx.MockTransport(lambda r: httpx.Response(500)),
    httpx.MockTransport(lambda r: httpx.Response(200, text="not json")),
    httpx.MockTransport(lambda r: httpx.Response(200, json={"unexpected": True})),
], ids=["unreachable", "http-500", "not-json", "wrong-shape"])
def test_failures_never_show_the_url_key_or_location(call, transport):
    with pytest.raises(sources.SourceError) as e:
        call(transport)
    message = str(e.value) + repr(e.value.__cause__)  # sections log only the message
    assert not any(secret in message for secret in (LAT, LON, "12.3457", "test-key", "http"))
