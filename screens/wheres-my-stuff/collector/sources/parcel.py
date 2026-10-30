"""Parcel source adapter: the deliveries the Parcel app tracks, and its carriers' names."""

import httpx


class ParcelError(Exception):
    """A failed Parcel request. The message never contains the URL or the key (ADR-0003)."""


class ParcelKeyError(ParcelError):
    """Parcel refused the API key, or there is none. It never recovers on its own, so the banner names it apart."""

    source = "parcel-key"  # collect_sections reports this instead of the section's source


class ParcelSource:
    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None):
        self._key = api_key
        self._client = httpx.Client(base_url="https://api.parcel.app/external", timeout=30, transport=transport)

    def deliveries(self) -> list[dict]:
        """Parcel's recent deliveries (active and recently delivered), as Parcel sends them."""
        body = self._get("/deliveries/", params={"filter_mode": "recent"}, headers={"api-key": self._key})
        if not isinstance(body, dict) or "success" not in body:
            raise ParcelError("Parcel returned an unexpected response")
        if not body["success"]:
            raise ParcelError(f"Parcel said: {body.get('error_message', 'no reason given')}")
        if not isinstance(body.get("deliveries"), list):
            raise ParcelError("Parcel returned an unexpected response")
        return body["deliveries"]

    def carriers(self) -> dict[str, str]:
        """Carrier code → display name. The list is public, so the key is not sent."""
        body = self._get("/supported_carriers.json")
        try:
            return {code: entry["name"] for code, entry in body.items()}
        except (AttributeError, KeyError, TypeError):
            raise ParcelError("Parcel returned an unexpected response") from None

    def _get(self, path, **kwargs):
        try:
            response = self._client.get(path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise ParcelKeyError("Parcel rejected the API key") from None
            raise ParcelError(f"Parcel returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            # httpx messages and chained causes can include the URL.
            raise ParcelError(f"Parcel request failed: {type(e).__name__}") from None
        except ValueError:
            raise ParcelError("Parcel returned an unexpected response") from None
