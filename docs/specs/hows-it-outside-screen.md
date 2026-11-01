# Spec: How's It Outside? screen (v1)

Status: collector and template built (2026-11-01); LaraPaper check next
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

Before heading out, the household wants a glance-from-across-the-room answer to "how's it outside?": what it's like now, what to bring (a jacket and which kind, an umbrella, sunscreen), and what's coming for the rest of the day. Tree and grass pollen and air quality matter for allergies. Severe-weather alerts up to a day ahead should never be missed. The answer has to read on the OG at a desk as well as on the X.

## Solution

A new **Screen**, **How's It Outside?**, in `screens/hows-it-outside/`, fed by a **Collector** like the other screens ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). Every 15 minutes the collector reads three free **Sources** (Open-Meteo forecast, Open-Meteo air quality, NWS alerts) and, once a day, Google Pollen ([ADR-0012](../adr/0012-pollen-from-google.md)). It pushes the current conditions, the **Verdicts**, the **Outlook** and the rest with every label already worked out; the template only lays them out, as on Where's My Stuff?.

The primary **Device** is the OG. The X renders the same template ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)) and is part of the same work. The screen stays in the playlist around the clock.

## Behaviour

### Sources
One location, from `HOWS_IT_OUTSIDE_LATITUDE` / `HOWS_IT_OUTSIDE_LONGITUDE`. Units are °F and mph.

| Source | Request | When | Key |
|---|---|---|---|
| Open-Meteo forecast | `api.open-meteo.com/v1/forecast` with `current` (temperature, feels-like, weather code, wind), `hourly` (temperature, feels-like, precipitation probability, weather code, UV index), `daily` (sunrise, sunset, high, low), `forecast_days=2`, `timezone` = `TZ` | every run | none |
| Open-Meteo air quality | `air-quality-api.open-meteo.com/v1/air-quality` with `current=us_aqi` | every run | none |
| NWS alerts | `api.weather.gov/alerts/active?point=LAT,LON` with a `User-Agent` naming the project | every run | none |
| Google Pollen | `pollen.googleapis.com/v1/forecast:lookup` with `days=1` | first run of the day, then cached in `STATE_DIR/hows-it-outside/` | `GOOGLE_POLLEN_API_KEY` |

- Open-Meteo's free tier allows 10,000 calls a day; a request with more than 10 variables counts as a fraction more than one call. A run costs about 3 calls, so 15 minutes is under 400 a day. Faster gains nothing: "current" moves in 15-minute steps and the US forecast model updates about hourly.
- Open-Meteo's own pollen fields are empty for US locations (checked 2026-10-31), hence Google.
- Each source is its own section, so one failing never blanks the others.

### Outlook
- 06:00 to 10:00: **Day outlook**, from now to 22:00 today.
- Every other time: **Rolling outlook**, from now to 12 hours from now.
- Hours are whole hours from the next hour on, through the outlook's end.

### Verdicts
**Waking hours** are 06:00–22:00. The jacket and umbrella verdicts read only the outlook's waking hours. A 12-hour Rolling outlook always holds some, even late at night.

- **Jacket grade** from the coldest feels-like temperature: `none` (65°F or above), `light` (50–64), `heavy` (35–49), `bundle` (below 35: heavy jacket with hat and gloves).
- **Umbrella** when some hour's precipitation probability is 50% or more; `snow` instead of `rain` when that hour's weather code is snow (71–77, 85–86).
- **Sunscreen** when the UV index reaches 3 or more at any hour of the whole outlook, the current hour included. Its reason line: "UV 2 now · peaks 5 at 1pm", naming the peak only when it rounds higher than now.
- Only verdicts that ask you to bring something are shown; a jacket grade of `none`, no umbrella and no sunscreen show nothing.
- **Reason lines:** the jacket's names the coldest feels-like temperature and its hour, "Feels 39° at 10pm" (the earliest hour on a tie); the umbrella's the highest chance and its hour, "70% at 10am" (the earliest on a tie).

### Current conditions
Temperature; "feels 43°" when feels-like differs by 3° or more; conditions in words from the weather code ("Light rain"); today's high and low; wind ("Wind 18 mph") only above 15 mph.

### Alerts
- Every active NWS alert whose onset is within 24 hours and whose end is after now (no end counts as ongoing, and reads "in effect"). Any severity. NWS sends one copy per forecast zone, so alerts with the same event, onset and end are one card.
- Alerts in effect come first, ordered by NWS severity (Extreme, Severe, Moderate, Minor, Unknown), then soonest end. Alerts starting later follow, soonest onset first, then severity.
- Each alert is a card: its event name and when, "until 6pm" when in effect, "from 2pm" before onset (the weekday when not today). A long name is cut with "…"; the time and "+N more" never are. A card for an alert in effect is solid black; one starting later is outlined. Overlapping alerts (a tornado warning inside a severe thunderstorm warning) each get their own card. The collector sends at most three, and counts the rest in `more_alerts`. NWS headlines repeat the event name, so they are not shown.

### Pollen
- Tree, grass and weed, each from Google's 0–5 index as its category word (None, Very low, Low, Moderate, High, Very high).
- The highest-scoring tree plant is named ("Oak") when tree pollen is above None. Trees are a fixed list of Google's plant codes (MAPLE, ELM, COTTONWOOD, ALDER, BIRCH, ASH, PINE, OAK, JUNIPER), since off-season responses carry no plant type.
- A type or plant with no `indexInfo` counts as None; that is how Google reports the off-season.
- Only types above None are shown. Pollen is left out entirely when all three are None, or when the cached values are for a previous day.

### Air quality
The AQI number with a mark for its EPA level: a check up to 50 (Good), a yield sign from 51 to 100 (Moderate), a siren on black from 101 ("Unhealthy for sensitive groups") up. The template picks the mark from the number.

### Failure behaviour
- A failing forecast section keeps its last good data, re-sliced to `now` on every run: the outlook, verdicts and current conditions are worked out again from the stored hours, with "current" taken from the stored hour for now, and the error pill marks it. After 3 hours of failure (or once the stored hours no longer cover now), the conditions block reads "No weather since 11:15am" and verdicts and timeline are left out.
- Air quality and alerts keep their last good data, marked stale, like other screens. Pollen follows its day rule above.
- The error pill names the failing source and since when: "Weather down since…", "Air quality down since…", "Alerts down since…", "Pollen down since…". A missing or rejected Google key is reported as `google-pollen-key` ("Pollen key rejected since…"), as on Where's My Stuff?.
- Errors never contain URLs, keys or coordinates ([ADR-0003](../adr/0003-public-repo-secrets-policy.md)).

## Payload contract

`fixtures/sample.json` and every other fixture have this shape.

```json
{
  "updated_at": "2026-10-31T09:15:00-04:00",
  "now": { "temp": 48, "feels": 43, "conditions": "Light rain", "icon": "rain", "high": 55, "low": 41, "wind": 18 },
  "verdicts": { "jacket": "heavy", "jacket_why": "Feels 39° at 10pm", "umbrella": "rain", "umbrella_why": "70% at 10am", "sunscreen": false, "uv": "UV 1 now · peaks 2 at 1pm" },
  "alerts": [
    { "event": "Tornado Warning", "when": "until 4:15pm" },
    { "event": "Hurricane Force Wind Warning", "when": "until Wed 11:45pm" },
    { "event": "Flood Watch", "when": "from 6pm", "upcoming": true }
  ],
  "more_alerts": 1,
  "outlook": {
    "kind": "day",
    "hours": [
      { "time": "10am", "icon": "rain", "temp": 49, "precip": 60 },
      { "time": "11am", "icon": "cloud", "temp": 51 },
      { "time": "5pm", "icon": "cloud", "temp": 50, "sunset": "5:47pm" }
    ]
  },
  "pollen": [{ "type": "Tree", "level": "High", "plant": "Oak" }, { "type": "Grass", "level": "Low" }],
  "air": { "aqi": 42 },
  "sun": [{ "kind": "set", "at": "5:47pm" }, { "kind": "rise", "at": "7:21am" }],
  "stale": ["air"],
  "errors": [{ "source": "open-meteo-air", "since": "2026-10-31T08:45:00-04:00" }]
}
```

- `now.feels` and `now.wind` are left out when they don't meet their thresholds. `now.icon` and `hours[].icon` are one of `sun`, `moon`, `partly`, `cloud`, `fog`, `rain`, `storm`, `snow`.
- `verdicts.jacket` is one of `none`, `light`, `heavy`, `bundle`; `verdicts.umbrella` is `rain`, `snow` or `null`.
- `hours[].precip` is left out under 20%. `hours[].sunrise` / `hours[].sunset` give the time on the hour a sunrise or sunset falls in. The X shows every hour; the OG every other hour, always keeping an hour with a sunrise or sunset.
- `sun` holds the next sunrise and the next sunset after now, soonest first, so it never shows one already past and the later one is what a full footer drops.
- `pollen` lists the types above None, highest level first (ties: tree, grass, weed); `plant` names the top tree on the tree entry. Left out when the list would be empty or the data is from a previous day.
- `verdicts.jacket_why` is left out when the jacket grade is `none`; `verdicts.umbrella_why` when `umbrella` is `null`.
- `alerts` is `[]` with none, in display order; `upcoming` is present (true) only on alerts that haven't started; `more_alerts` is left out unless more than three are in effect. `pollen` and `air` are left out when there is nothing to show. `stale` lists the sections showing last good data, and is left out when none are.
- With the forecast gone: `now` is `{ "missing_since": "3:15pm" }` and `verdicts` and `outlook` are left out.

## Design (template)

The **Panel** theme, chosen from two in mock-ups (2026-10-31, round 2). Renders are in the private gallery artifact.

- **Top block:** current conditions on the left (temperature very large with the conditions icon beside it, then conditions in words, then feels-like and wind, then high and low). The shown verdicts stack on the right, each a black tile with its icon, then its label and reason line. No divider between the two halves. With nothing to bring, the conditions take the whole width.
- **Jacket icons:** one jacket drawn thin (light) or heavy (heavy); jacket, beanie and mitten side by side for the hat-and-gloves grade, labelled "Coat, hat, gloves".
- **Shrinking under alerts:** the temperature gives up the most (to about 60% with three cards); the verdicts barely shrink. No text on the OG goes under 15px.
- **Degree sign:** the big temperature's ° is drawn as a ring, since the OG's bitmap font turns a large ° into a blob.
- **Alert cards:** up to three bars across the top, one per alert, each with a warning triangle, the event name and its time; the last carries "+N more". Alerts in effect are solid black; alerts starting later are outlined (black on white) and come after them. Each card shrinks the top block (and with three, the timeline) so everything still fits: three cards are the designed maximum. The error banner is an outlined pill instead, so the two never look alike. With no forecast left, the conditions block reads "No weather since 11:15am" across the screen and the pill is not shown.
- **Timeline:** a strip of columns under a rule: hour, icon, temperature, then the precipitation chance as a solid bar with no track (taller for higher chances), with the number over it on the X only (too small to read on the OG). Sunrise and sunset sit under their hour as a sun-on-the-horizon icon (arrow up or down) and the time.
- **Bottom line:** pollen (plant icon; the highest type in bold, the top tree named), the AQI mark and number, then the next sunrise and sunset with the same icons. It is one line: whatever doesn't fit drops off the end, so sunrise and sunset go first.
- **Priority** when the OG runs out of room, highest first: current conditions → verdicts → alert cards → timeline → pollen → AQI → sunrise/sunset.
- **Icons:** Tabler outline icons, inline SVG; the beanie and mitten are drawn in the same style since no icon set has them. All text black; framework fonts only; every payload string escaped; the template includes `view view--full`.

## Configuration

- `.env`: `HOWS_IT_OUTSIDE_LATITUDE`, `HOWS_IT_OUTSIDE_LONGITUDE`, `GOOGLE_POLLEN_API_KEY`, `HOWS_IT_OUTSIDE_WEBHOOK_UUID`, `HOWS_IT_OUTSIDE_PLUGIN_ID`, optional `HOWS_IT_OUTSIDE_INTERVAL_MINUTES`, plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`.
- `settings.yml`: webhook strategy, refresh interval 15.

## Testing

- **Source adapters:** pytest with `httpx.MockTransport` against invented responses in each API's real shape: request parameters, the NWS `User-Agent`, error wrapping without URL, key or coordinates.
- **Rules:** pytest with a fixed `now`: the outlook switch at 06:00 and 10:00, waking hours and the late-night fallback, each jacket step's edges, umbrella at 49/50% and snow, sunscreen at UV 2.9/3, alert filtering and order, pollen hiding, AQI at 100/101, forecast re-slicing when stale.
- **Template:** checked by eye in `trmnlp serve` with every fixture on the OG and the X, then once on LaraPaper.

## Out of scope (v1)

- Dust mites and other indoor allergens (no outdoor source reports them).
- Minute-by-minute rain, radar maps, multi-day forecasts.
- More than one location; mashup layouts.

## Open source checks

Confirm with real data before calling the screen done, then delete this section:
- How long real NWS event names get ("Excessive Heat Warning", "Winter Weather Advisory") and whether a card fits them on the OG with "+N more".

Settled (2026-10-31): Google Pollen allows 5,000 free requests a month (once a day is about 31). For the location it lists tree, grass and weed plus 11 plants, 9 of them trees; off-season every entry has only `code` and `displayName`.
