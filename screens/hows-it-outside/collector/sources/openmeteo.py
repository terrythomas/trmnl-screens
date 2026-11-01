"""Open-Meteo source adapter: the forecast and the air quality, free and keyless."""

import httpx

from . import SourceError, get_json

CURRENT = {"temp": "temperature_2m", "feels": "apparent_temperature", "code": "weather_code", "wind": "wind_speed_10m",
           "is_day": "is_day"}
HOURLY = {"temp": "temperature_2m", "feels": "apparent_temperature", "precip": "precipitation_probability",
          "code": "weather_code", "uv": "uv_index", "wind": "wind_speed_10m", "is_day": "is_day"}
DAILY = {"high": "temperature_2m_max", "low": "temperature_2m_min", "sunrise": "sunrise", "sunset": "sunset"}


class OpenMeteoSource:
    def __init__(self, latitude: str, longitude: str, timezone: str, transport: httpx.BaseTransport | None = None):
        self._where = {"latitude": latitude, "longitude": longitude, "timezone": timezone}
        self._transport = transport

    def forecast(self) -> dict:
        """Current conditions plus hourly and daily rows for today and tomorrow, in local time, °F and mph."""
        body = self._get("https://api.open-meteo.com/v1", "/forecast", current=",".join(CURRENT.values()),
                         hourly=",".join(HOURLY.values()), daily=",".join(DAILY.values()),
                         temperature_unit="fahrenheit", wind_speed_unit="mph", forecast_days=2)
        try:
            hourly, daily = body["hourly"], body["daily"]
            return {
                "current": {k: body["current"][v] for k, v in CURRENT.items()},
                # A missing chance or UV reading counts as none.
                "hours": [{"time": t, **{k: hourly[v][i] or 0 for k, v in HOURLY.items()}}
                          for i, t in enumerate(hourly["time"])],
                "days": [{"date": d, **{k: daily[v][i] for k, v in DAILY.items()}} for i, d in enumerate(daily["time"])],
            }
        except (KeyError, IndexError, TypeError):
            raise SourceError("Open-Meteo returned an unexpected response") from None

    def air(self) -> dict | None:
        """The current US AQI, or None when Open-Meteo has no reading."""
        body = self._get("https://air-quality-api.open-meteo.com/v1", "/air-quality", current="us_aqi")
        try:
            aqi = body["current"]["us_aqi"]
        except (KeyError, TypeError):
            raise SourceError("Open-Meteo air quality returned an unexpected response") from None
        return None if aqi is None else {"aqi": round(aqi)}

    def _get(self, base_url, path, **params):
        with httpx.Client(base_url=base_url, timeout=30, transport=self._transport) as client:
            return get_json(client, "Open-Meteo", path, params={**self._where, **params})
