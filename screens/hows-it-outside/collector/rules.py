"""How's It Outside? labelling rules: everything the template shows, worked out from source data and `now`."""

from datetime import datetime, timedelta

# Forecast times are naive local time, as Open-Meteo sends them for the configured timezone.


def local(now: datetime) -> datetime:
    return now.replace(tzinfo=None)


def hour_of(row: dict) -> datetime:
    return datetime.fromisoformat(row["time"])


def outlook(hours: list[dict], now: datetime) -> tuple[str, list[dict]]:
    """Day outlook (to 22:00) from 06:00 to 10:00, otherwise Rolling (12 hours); whole hours after now."""
    now = local(now)
    if 6 <= now.hour < 10:
        kind, end = "day", now.replace(hour=22, minute=0, second=0, microsecond=0)
    else:
        kind, end = "rolling", now + timedelta(hours=12)
    return kind, [h for h in hours if now < hour_of(h) <= end]

SNOW_CODES = {71, 73, 75, 77, 85, 86}
# Coldest feels-like (°F) at or above which each grade applies, warmest first.
JACKET = [(65, "none"), (50, "light"), (35, "heavy")]


def clock(t: datetime) -> str:
    """'10pm', '4:15pm'."""
    return t.strftime("%-I:%M%p").lower().replace(":00", "")


def verdicts(hours: list[dict], now: datetime) -> dict:
    """What to bring, from the outlook. Jacket and umbrella read only its waking hours (06:00–22:00).

    A 12-hour Rolling outlook always holds some waking hours, so there is no next-morning fallback.
    """
    _, window = outlook(hours, now)
    waking = [h for h in window if 6 <= hour_of(h).hour <= 22]
    result = {}

    coldest = min(waking, key=lambda h: h["feels"])  # min/max keep the earliest on a tie
    result["jacket"] = next((grade for floor, grade in JACKET if round(coldest["feels"]) >= floor), "bundle")
    if result["jacket"] != "none":
        result["jacket_why"] = f"Feels {round(coldest['feels'])}° at {clock(hour_of(coldest))}"

    wettest = max(waking, key=lambda h: h["precip"])
    result["umbrella"] = None
    if wettest["precip"] >= 50:
        result["umbrella"] = "snow" if wettest["code"] in SNOW_CODES else "rain"
        result["umbrella_why"] = f"{wettest['precip']}% at {clock(hour_of(wettest))}"

    current = next(h for h in hours if hour_of(h) == local(now).replace(minute=0, second=0, microsecond=0))
    peak = max(window, key=lambda h: h["uv"])
    result["sunscreen"] = max(current["uv"], peak["uv"]) >= 3
    result["uv"] = f"UV {round(current['uv'])} now"
    if round(peak["uv"]) > round(current["uv"]):
        result["uv"] += f" · peaks {round(peak['uv'])} at {clock(hour_of(peak))}"
    return result

# WMO weather code → (words, icon); clear skies read differently at night.
WEATHER = {
    0: ("Sunny", "sun"), 1: ("Mostly sunny", "sun"), 2: ("Partly cloudy", "partly"), 3: ("Cloudy", "cloud"),
    45: ("Fog", "fog"), 48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "rain"), 53: ("Drizzle", "rain"), 55: ("Heavy drizzle", "rain"),
    56: ("Freezing drizzle", "rain"), 57: ("Freezing drizzle", "rain"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"), 77: ("Snow grains", "snow"),
    80: ("Light showers", "rain"), 81: ("Showers", "rain"), 82: ("Heavy showers", "rain"),
    85: ("Snow showers", "snow"), 86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm, hail", "storm"), 99: ("Thunderstorm, hail", "storm"),
}
NIGHT = {0: ("Clear", "moon"), 1: ("Mostly clear", "moon")}


def weather(code: int, is_day: int) -> tuple[str, str]:
    """(words, icon). An unknown code reads as cloudy rather than failing the screen."""
    return (not is_day and NIGHT.get(code)) or WEATHER.get(code, WEATHER[3])


def conditions(current: dict, day: dict) -> dict:
    words, icon = weather(current["code"], current["is_day"])
    result = {"temp": round(current["temp"])}
    if abs(round(current["feels"]) - result["temp"]) >= 3:
        result["feels"] = round(current["feels"])
    result |= {"conditions": words, "icon": icon, "high": round(day["high"]), "low": round(day["low"])}
    if round(current["wind"]) > 15:
        result["wind"] = round(current["wind"])
    return result


def _sun_events(days: list[dict]) -> list[tuple[datetime, str]]:
    return sorted((datetime.fromisoformat(d[f"sun{kind}"]), kind) for d in days for kind in ("rise", "set"))


def timeline(window: list[dict], days: list[dict]) -> list[dict]:
    events = _sun_events(days)
    rows = []
    for h in window:
        start = hour_of(h)
        row = {"time": clock(start), "icon": weather(h["code"], h["is_day"])[1], "temp": round(h["temp"])}
        if h["precip"] >= 20:
            row["precip"] = h["precip"]
        for t, kind in events:
            if start <= t < start + timedelta(hours=1):
                row[f"sun{kind}"] = clock(t)
        rows.append(row)
    return rows


def sun(days: list[dict], now: datetime) -> list[dict]:
    """The next sunrise and the next sunset, soonest first."""
    upcoming = [(t, kind) for t, kind in _sun_events(days) if t > local(now)]
    firsts = [next(e for e in upcoming if e[1] == kind) for kind in ("rise", "set") if any(e[1] == kind for e in upcoming)]
    return [{"kind": kind, "at": clock(t)} for t, kind in sorted(firsts)]

SEVERITY = ["Extreme", "Severe", "Moderate", "Minor", "Unknown"]
MAX_ALERTS = 3


def alerts(items: list[dict], now: datetime) -> tuple[list[dict], int]:
    """Alert cards in display order (at most three) and how many more there are."""
    def rank(a):
        return SEVERITY.index(a["severity"]) if a["severity"] in SEVERITY else len(SEVERITY)

    def when(word, t):
        return f"{word} {'' if t.date() == now.date() else t.strftime('%a ')}{clock(t)}"

    live, later = [], []
    # NWS sends one copy per forecast zone; the same event and times make one card.
    for a in {(a["event"], a["onset"], a["ends"]): a for a in items}.values():
        onset = datetime.fromisoformat(a["onset"]).astimezone(now.tzinfo)
        ends = a["ends"] and datetime.fromisoformat(a["ends"]).astimezone(now.tzinfo)
        if onset > now + timedelta(hours=24) or (ends and ends <= now):
            continue
        if onset <= now:
            card = {"event": a["event"], "when": when("until", ends) if ends else "in effect"}
            live.append(((rank(a), ends or datetime.max.replace(tzinfo=now.tzinfo)), card))
        else:
            later.append(((onset, rank(a)), {"event": a["event"], "when": when("from", onset), "upcoming": True}))
    cards = [card for _, card in sorted(live, key=lambda x: x[0])] + [card for _, card in sorted(later, key=lambda x: x[0])]
    return cards[:MAX_ALERTS], max(len(cards) - MAX_ALERTS, 0)

POLLEN_LEVELS = ["None", "Very low", "Low", "Moderate", "High", "Very high"]
POLLEN_TYPES = {"TREE": "Tree", "GRASS": "Grass", "WEED": "Weed"}  # also the tie order
# Google's tree plants. Off-season entries carry no plant type, so trees can't be told apart any other way.
TREES = {"MAPLE", "ELM", "COTTONWOOD", "ALDER", "BIRCH", "ASH", "PINE", "OAK", "JUNIPER"}


def pollen(day: dict) -> list[dict]:
    """Pollen types above None, highest first. An entry without indexInfo is Google's way of saying None."""
    def value(entry):
        return entry.get("indexInfo", {}).get("value", 0)

    scores = {e["code"]: value(e) for e in day.get("pollenTypeInfo", [])}
    result = []
    for code in sorted(POLLEN_TYPES, key=lambda c: -scores.get(c, 0)):  # sorted is stable: ties keep tree, grass, weed
        if scores.get(code, 0) > 0:
            result.append({"type": POLLEN_TYPES[code], "level": POLLEN_LEVELS[min(scores[code], 5)]})
            if code == "TREE":
                trees = [p for p in day.get("plantInfo", []) if p["code"] in TREES and value(p) > 0]
                if trees:
                    result[-1]["plant"] = max(trees, key=value)["displayName"]
    return result
