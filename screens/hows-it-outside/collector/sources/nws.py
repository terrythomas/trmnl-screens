"""National Weather Service source adapter: active alerts for a point, keyless."""

import httpx

from . import SourceError, get_json

# NWS asks every client to identify itself.
USER_AGENT = "trmnl-screens (https://github.com/terrythomas/trmnl-screens)"


class NwsSource:
    def __init__(self, latitude: str, longitude: str, transport: httpx.BaseTransport | None = None):
        self._point = f"{float(latitude):.4f},{float(longitude):.4f}"  # NWS refuses more than four decimals
        self._client = httpx.Client(base_url="https://api.weather.gov", timeout=30, transport=transport,
                                    headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})

    def alerts(self) -> list[dict]:
        """Active alerts (not tests or exercises): event, severity, onset and end (None while open-ended)."""
        body = get_json(self._client, "NWS", "/alerts/active", params={"point": self._point})
        try:
            return [{"event": p["event"], "severity": p["severity"], "onset": p["onset"] or p["effective"],
                     "ends": p["ends"]}
                    for p in (f["properties"] for f in body["features"]) if p["status"] == "Actual"]
        except (KeyError, TypeError):
            raise SourceError("NWS returned an unexpected response") from None
