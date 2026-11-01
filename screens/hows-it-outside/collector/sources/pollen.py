"""Google Pollen source adapter: today's pollen index by type and plant (ADR-0012)."""

import httpx

from . import SourceError, get_json


class PollenKeyError(SourceError):
    """Google refused the API key, or there is none. It never recovers on its own, so the banner names it apart."""

    source = "google-pollen-key"  # collect_sections reports this instead of the section's source


class PollenSource:
    def __init__(self, api_key: str, latitude: str, longitude: str, transport: httpx.BaseTransport | None = None):
        self._params = {"key": api_key, "location.latitude": latitude, "location.longitude": longitude, "days": 1}
        self._client = httpx.Client(base_url="https://pollen.googleapis.com/v1", timeout=30, transport=transport)

    def today(self) -> dict:
        """Today's dailyInfo entry: pollenTypeInfo and plantInfo, as Google sends them."""
        try:
            body = get_json(self._client, "Google Pollen", "/forecast:lookup", params=self._params)
        except SourceError as e:
            # Google answers a bad key with 400 and a key without the Pollen API enabled with 403.
            if e.status in (400, 403):
                raise PollenKeyError("Google rejected the Pollen API key") from None
            raise
        try:
            return body["dailyInfo"][0]
        except (KeyError, IndexError, TypeError):
            raise SourceError("Google Pollen returned an unexpected response") from None
