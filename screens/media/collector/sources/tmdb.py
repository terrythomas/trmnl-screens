"""TMDB source adapter for In Theaters: a movie's release dates in one country.

TMDB's API needs an account, so this reads the public release page
(themoviedb.org/movie/<id>/releases) instead. Each movie's page is fetched at most
once per day; the parsed dates are cached in a small JSON file next to the state.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

# A plain, descriptive User-Agent: TMDB's bot protection answers browser-like ones with 403.
USER_AGENT = "trmnl-screens (+https://github.com/terrythomas/trmnl-screens)"


@dataclass(frozen=True)
class Release:
    date: date
    type: str  # as TMDB labels it: "Premiere", "Theatrical (limited)", "Theatrical", "Digital", "Physical", "TV"
    note: str | None  # e.g. "IMAX"


class TmdbError(Exception):
    """A failed TMDB request or an unreadable page. The message never contains the URL."""

    source = "tmdb"  # reported in errors[] instead of the section's own source


class TmdbSource:
    def __init__(self, country: str, cache_path: Path, transport: httpx.BaseTransport | None = None):
        self._country = country.upper()
        self._cache_path = cache_path
        self._cache: dict | None = None
        self._client = httpx.Client(
            base_url="https://www.themoviedb.org",
            # en-US keeps dates as MM/DD/YYYY and type names in English, whatever the country.
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US"},
            follow_redirects=True,  # /movie/<id> redirects to /movie/<id>-<slug>
            timeout=30,
            transport=transport,
        )

    def releases(self, tmdb_id: int, today: date) -> list[Release]:
        """The movie's releases in the configured country; empty when it has none there."""
        cache = self._load()
        key = f"{self._country}/{tmdb_id}"
        entry = cache.get(key)
        if not isinstance(entry, dict) or entry.get("fetched") != today.isoformat():
            entry = {"fetched": today.isoformat(), "releases": [_dump(r) for r in self._fetch(tmdb_id)]}
            cache[key] = entry
            self._save(today)
        return [_release(r) for r in entry["releases"]]

    def _fetch(self, tmdb_id: int) -> list[Release]:
        try:
            response = self._client.get(f"/movie/{tmdb_id}/releases")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TmdbError(f"TMDB returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            raise TmdbError(f"TMDB request failed: {type(e).__name__}") from None
        return parse_releases(response.text, self._country)

    def _load(self) -> dict:
        if self._cache is None:
            try:
                self._cache = dict(json.loads(self._cache_path.read_text()))
            except FileNotFoundError:
                self._cache = {}
            except (ValueError, TypeError):
                log.warning("TMDB cache %s is unreadable, starting fresh", self._cache_path.name)
                self._cache = {}
        return self._cache

    def _save(self, today: date) -> None:
        # Entries from earlier days would be fetched again anyway, so drop them.
        cache = {k: v for k, v in self._load().items() if v.get("fetched") == today.isoformat()}
        self._cache = cache
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache))
        os.replace(temporary, self._cache_path)


def parse_releases(html: str, country: str) -> list[Release]:
    """The release rows under the country's heading on a TMDB release page.

    Raises TmdbError when the page has no release tables at all: every movie that
    reaches here has a theatrical date somewhere, so that means the page changed.
    """
    parser = _ReleasePage(country.upper())
    parser.feed(html)
    if not parser.countries:
        raise TmdbError("TMDB release page has no release tables")
    try:
        return [
            Release(datetime.strptime(day, "%m/%d/%Y").date(), kind, note or None)
            for day, _certification, kind, _language, note in parser.rows
        ]
    except ValueError:
        raise TmdbError("TMDB release page has an unexpected date") from None


class _ReleasePage(HTMLParser):
    """Collects the five-cell <td> rows that follow <h2 id="<country>" class="release">."""

    def __init__(self, country: str):
        super().__init__()
        self.country = country
        self.countries: list[str] = []  # every release heading seen, to tell "no rows" from "page changed"
        self.rows: list[tuple[str, ...]] = []
        self._current: str | None = None
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2" and "release" in (attrs.get("class") or "").split():
            self._current = attrs.get("id")
            self.countries.append(self._current)
        elif tag == "tr":
            self._cells = []
        elif tag == "td" and self._cells is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None and self._cells is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            if self._current == self.country and self._cells and len(self._cells) == 5:
                self.rows.append(tuple(self._cells))
            self._cells = None


def _dump(r: Release) -> dict:
    return {"date": r.date.isoformat(), "type": r.type, "note": r.note}


def _release(r: dict) -> Release:
    return Release(date.fromisoformat(r["date"]), r["type"], r["note"])
