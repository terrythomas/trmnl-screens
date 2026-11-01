import importlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from collector.discovery import discover_screens

discover_screens()  # registers the screen packages so their submodules can be imported
rules = importlib.import_module("trmnl_screens.hows-it-outside.collector.rules")

NY = ZoneInfo("America/New_York")
MIDNIGHT = datetime(2026, 10, 31)


def at(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=NY)


def hours(changes=None, start=MIDNIGHT, count=48, **base):
    """Hourly rows from `start` (naive local, as Open-Meteo sends them); `changes` maps "D HH" → fields."""
    rows = []
    for i in range(count):
        t = start + timedelta(hours=i)
        row = {"time": t.strftime("%Y-%m-%dT%H:%M"), "temp": 70, "feels": 70, "precip": 0, "code": 3, "uv": 0,
               "wind": 5, "is_day": 1 if 7 <= t.hour < 18 else 0, **base}
        row.update((changes or {}).get(t.strftime("%-d %H"), {}))
        rows.append(row)
    return rows


def times(window):
    return [h["time"][-5:-3] for h in window]


@pytest.mark.parametrize("now, kind, first, last, count", [
    (at(31, 6, 0), "day", "07", "22", 16),
    (at(31, 9, 59), "day", "10", "22", 13),
    (at(31, 10, 0), "rolling", "11", "22", 12),
    (at(31, 5, 59), "rolling", "06", "17", 12),
    (at(31, 14, 5), "rolling", "15", "02", 12),
])
def test_outlook_switches_from_day_to_rolling_at_10am(now, kind, first, last, count):
    got_kind, window = rules.outlook(hours(), now)
    assert got_kind == kind
    assert (times(window)[0], times(window)[-1], len(window)) == (first, last, count)


NOON = at(31, 12, 30)  # Rolling outlook 13:00 to 00:00; waking hours 13:00 to 22:00


@pytest.mark.parametrize("coldest, grade", [(65, "none"), (64, "light"), (50, "light"), (49, "heavy"),
                                            (35, "heavy"), (34, "bundle")])
def test_jacket_grade_steps(coldest, grade):
    assert rules.verdicts(hours({"31 20": {"feels": coldest}}), NOON)["jacket"] == grade


def test_jacket_reads_only_waking_hours_and_names_the_earliest_coldest():
    v = rules.verdicts(hours({"31 23": {"feels": 20}, "31 16": {"feels": 39}, "31 22": {"feels": 39}}), NOON)
    assert (v["jacket"], v["jacket_why"]) == ("heavy", "Feels 39° at 4pm")


def test_no_jacket_has_no_reason():
    assert "jacket_why" not in rules.verdicts(hours(), NOON)


@pytest.mark.parametrize("chance, code, umbrella, why", [
    (49, 61, None, None), (50, 61, "rain", "50% at 3pm"), (80, 73, "snow", "80% at 3pm"), (60, 85, "snow", "60% at 3pm"),
])
def test_umbrella_from_half_chance_and_snow_codes(chance, code, umbrella, why):
    v = rules.verdicts(hours({"31 15": {"precip": chance, "code": code}, "31 18": {"precip": chance}}), NOON)
    assert v["umbrella"] == umbrella
    assert v.get("umbrella_why") == why


def test_umbrella_ignores_rain_overnight():
    assert rules.verdicts(hours({"31 23": {"precip": 90, "code": 63}}), NOON)["umbrella"] is None


@pytest.mark.parametrize("peak, sunscreen, line", [(2.9, False, "UV 1 now · peaks 3 at 2pm"),
                                                   (3.0, True, "UV 1 now · peaks 3 at 2pm")])
def test_sunscreen_from_uv_3(peak, sunscreen, line):
    v = rules.verdicts(hours({"31 12": {"uv": 1.2}, "31 14": {"uv": peak}}), NOON)
    assert (v["sunscreen"], v["uv"]) == (sunscreen, line)


def test_sunscreen_counts_the_current_hour_and_names_no_peak_that_is_not_higher():
    v = rules.verdicts(hours({"31 12": {"uv": 5.4}, "31 13": {"uv": 4.6}}), NOON)
    assert (v["sunscreen"], v["uv"]) == (True, "UV 5 now")


DAYS = [{"date": "2026-10-31", "high": 61.4, "low": 46.6, "sunrise": "2026-10-31T07:27", "sunset": "2026-10-31T17:52"},
        {"date": "2026-11-01", "high": 58, "low": 44, "sunrise": "2026-11-01T06:28", "sunset": "2026-11-01T16:51"}]


def test_conditions_round_and_show_feels_and_wind_only_past_their_thresholds():
    now = rules.conditions({"temp": 48.4, "feels": 45.6, "code": 61, "wind": 15.4, "is_day": 1}, DAYS[0])
    assert now == {"temp": 48, "conditions": "Light rain", "icon": "rain", "high": 61, "low": 47}
    now = rules.conditions({"temp": 48.4, "feels": 45.2, "code": 61, "wind": 15.6, "is_day": 1}, DAYS[0])
    assert (now["feels"], now["wind"]) == (45, 16)


@pytest.mark.parametrize("code, is_day, words, icon", [
    (0, 1, "Sunny", "sun"), (0, 0, "Clear", "moon"), (2, 1, "Partly cloudy", "partly"), (3, 0, "Cloudy", "cloud"),
    (45, 1, "Fog", "fog"), (81, 1, "Showers", "rain"), (75, 0, "Heavy snow", "snow"), (95, 1, "Thunderstorm", "storm"),
])
def test_weather_codes_name_the_conditions(code, is_day, words, icon):
    now = rules.conditions({"temp": 50, "feels": 50, "code": code, "wind": 0, "is_day": is_day}, DAYS[0])
    assert (now["conditions"], now["icon"]) == (words, icon)


def test_timeline_rows_carry_rain_from_20_percent_and_the_sunset_on_its_hour():
    _, window = rules.outlook(hours({"31 15": {"precip": 19}, "31 16": {"precip": 20}, "31 17": {"code": 0}}), NOON)
    rows = rules.timeline(window, DAYS)
    assert rows[2] == {"time": "3pm", "icon": "cloud", "temp": 70}
    assert rows[3] == {"time": "4pm", "icon": "cloud", "temp": 70, "precip": 20}
    assert rows[4] == {"time": "5pm", "icon": "sun", "temp": 70, "sunset": "5:52pm"}
    assert [r["time"] for r in rows if "sunrise" in r or "sunset" in r] == ["5pm"]


@pytest.mark.parametrize("now, expected", [
    (at(31, 6, 0), [{"kind": "rise", "at": "7:27am"}, {"kind": "set", "at": "5:52pm"}]),
    (at(31, 12, 0), [{"kind": "set", "at": "5:52pm"}, {"kind": "rise", "at": "6:28am"}]),
    (at(31, 19, 0), [{"kind": "rise", "at": "6:28am"}, {"kind": "set", "at": "4:51pm"}]),
])
def test_sun_lists_the_next_sunrise_and_sunset_soonest_first(now, expected):
    assert rules.sun(DAYS, now) == expected


ALERT_NOW = at(31, 15, 40)  # a Saturday


def alert(event, onset, ends, severity="Moderate"):
    return {"event": event, "severity": severity, "onset": onset.isoformat(), "ends": ends and ends.isoformat()}


def test_alerts_keep_those_starting_within_24_hours_and_not_yet_over():
    cards, more = rules.alerts([
        alert("Over", at(31, 9), at(31, 15, 40)),
        alert("Too far", at(31, 15, 41) + timedelta(hours=24), None),
        alert("Ongoing", at(30, 9), None),
        alert("Tomorrow", at(31, 15, 40) + timedelta(hours=24), datetime(2026, 11, 1, 18, tzinfo=NY)),
    ], ALERT_NOW)
    assert cards == [{"event": "Ongoing", "when": "in effect"},
                     {"event": "Tomorrow", "when": "from Sun 3:40pm", "upcoming": True}]
    assert more == 0


def test_alerts_in_effect_come_first_by_severity_then_soonest_end_then_later_ones_by_onset():
    cards, more = rules.alerts([
        alert("Flood Watch", at(31, 18), at(31, 23), "Moderate"),
        alert("Wind Advisory", at(31, 12), at(31, 18), "Minor"),
        alert("Severe Thunderstorm Warning", at(31, 15), at(31, 17), "Severe"),
        alert("Tornado Warning", at(31, 15, 30), at(31, 16, 15), "Extreme"),
        alert("Hurricane Force Wind Warning", at(31, 12), datetime(2026, 11, 4, 23, 45, tzinfo=NY), "Extreme"),
        alert("Freeze Watch", at(31, 18), at(31, 23), "Severe"),
    ], ALERT_NOW)
    assert cards == [{"event": "Tornado Warning", "when": "until 4:15pm"},
                     {"event": "Hurricane Force Wind Warning", "when": "until Wed 11:45pm"},
                     {"event": "Severe Thunderstorm Warning", "when": "until 5pm"}]
    assert more == 3
    cards, _ = rules.alerts([
        alert("Flood Watch", at(31, 18), at(31, 23), "Moderate"),
        alert("Freeze Watch", at(31, 18), at(31, 23), "Severe"),
        alert("Gale Watch", at(31, 17), None, "Minor"),
    ], ALERT_NOW)
    assert [c["event"] for c in cards] == ["Gale Watch", "Freeze Watch", "Flood Watch"]
    assert cards[0]["when"] == "from 5pm"


def kind(code, value=None):
    entry = {"code": code, "displayName": code.title()}
    if value is not None:
        entry["indexInfo"] = {"code": "UPI", "value": value, "category": "ignored"}
    return entry


def test_pollen_lists_types_above_none_highest_first_and_names_the_top_tree():
    day = {"pollenTypeInfo": [kind("GRASS", 2), kind("TREE", 4), kind("WEED", 2)],
           "plantInfo": [kind("GRAMINALES", 5), kind("MAPLE", 2), kind("OAK", 4), kind("BIRCH", 4), kind("RAGWEED")]}
    assert rules.pollen(day) == [{"type": "Tree", "level": "High", "plant": "Oak"},
                                 {"type": "Grass", "level": "Low"}, {"type": "Weed", "level": "Low"}]


def test_pollen_ties_go_tree_grass_weed_and_levels_span_the_index():
    day = {"pollenTypeInfo": [kind("WEED", 1), kind("GRASS", 5), kind("TREE", 1)], "plantInfo": [kind("PINE")]}
    assert rules.pollen(day) == [{"type": "Grass", "level": "Very high"}, {"type": "Tree", "level": "Very low"},
                                 {"type": "Weed", "level": "Very low"}]


def test_off_season_pollen_is_empty():
    day = {"pollenTypeInfo": [kind("GRASS"), kind("TREE", 0), kind("WEED")], "plantInfo": [kind("OAK")]}
    assert rules.pollen(day) == []


def test_the_same_alert_for_two_zones_is_one_card():
    twice = [alert("Wind Advisory", at(31, 12), at(31, 18)), alert("Wind Advisory", at(31, 12), at(31, 18)),
             alert("Wind Advisory", at(31, 12), at(31, 20))]
    cards, _ = rules.alerts(twice, ALERT_NOW)
    assert [c["when"] for c in cards] == ["until 6pm", "until 8pm"]
