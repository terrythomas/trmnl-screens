# Spec: F1 screen (v1)

Status: requirements, sources and design settled; payload contract settled, `fixtures/sample.json` to follow
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

The household follows Formula 1 but usually watches sessions delayed, especially races in Australia, Asia and Europe. They want an ambient answer on race weekends: which Grand Prix it is, what the circuit looks like, and when each session starts in local time. The screen must never give away a result, and it should stay out of the playlist on days with nothing on.

## Solution

A new **Screen**, **F1**, in `screens/f1/`, fed by a **Collector** like the other screens ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). The collector reads free public sources only, with no keys or accounts: the season schedule from Jolpica (the Ergast successor) and circuit outlines from the bacinger/f1-circuits GeoJSON set ([ADR-0010](../adr/0010-circuit-outlines-drawn-from-geojson.md)). It pushes the season's schedule and the circuit outlines it needs. The template picks the **Grand Prix** and works out the visibility and **session** states from the render time, so the screen appears, strikes through finished sessions and leaves the playlist on the clock, without a fetch.

The primary **Device** is the TRMNL X; the OG renders the same template ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)) and is part of the same work.

## Behaviour

### Sessions
- A Grand Prix weekend has five sessions, as the source lists them:
  - **Conventional weekend:** Practice 1, Practice 2, Practice 3, Qualifying, Race.
  - **Sprint weekend:** Practice 1, Sprint Qualifying, Sprint, Qualifying, Race.
- Each session has a start time from the source. Its **session end** is the start plus a fixed length: 1 hour for practice, qualifying and Sprint Qualifying sessions, 1 hour for the Sprint, and 2 hours for the race. Delays and red flags are ignored; the screen shows nothing live.
- A session is **over** once its session end has passed.
- Jolpica has no cancellation flags. A cancelled Grand Prix drops out of its schedule; a single cancelled session is struck through at its normal end.

### Session days and visibility (template)
- A **session day** is a local date (`TZ`) on which at least one session starts. A session belongs to the local day it starts on, so Japan's Friday practice at 11:30 JST is a Thursday-evening session day in the US.
- The screen is in the playlist only on session days. It stays up for the whole day, including after its last session, so on race day it shows until midnight.
- On every other day the screen sets `TRMNL_SKIP_DISPLAY`, unless the error banner has been up for 24 hours or more, so a broken collector is never mistaken for a weekend without a race.

### Which Grand Prix
- On a session day, the screen shows the Grand Prix with a session starting that day. Back-to-back and triple-header weekends need no special rule: each weekend's session days pick their own Grand Prix.
- If two Grands Prix ever have sessions on the same local day, the one whose race is earlier is shown.

### Schedule (template)
- The schedule lists all five sessions of the Grand Prix in start order, each with its local day and start time, e.g. "Fri 7:30 AM".
- Sessions that are over stay in the list with their name and time struck through.
- The **next session** is the first that is not over. It is set apart so it can be read at a glance. Once the race is over there is no next session, and the whole schedule is struck through until midnight.

### No spoilers
- The screen never shows results, positions, the grid, fastest laps, winners, championship standings, live status or session progress.
- The collector does not request any results, standings or timing endpoints, so no result can reach the payload by accident.

### Circuit outline
- Each Grand Prix shows its circuit's outline, large.
- No outline artwork is committed to the repository, including tests and fixtures, in the spirit of [ADR-0009](../adr/0009-logos-fetched-at-runtime.md). The collector gets the outline at runtime and caches it in `STATE_DIR/f1/`.
- The collector picks the outline whose location is nearest the circuit's coordinates in bacinger's current-season file, so a new circuit needs no code change. It projects the GeoJSON line to an SVG path, scaling longitude by the cosine of the latitude so the shape is true.
- The outline is a plain line drawing, so the X and OG can use the same drawing; the OG needs no gray.
- A missing outline falls back to the circuit name in its place. It never marks the screen stale.

### Outline angle and north arrow (collector)
The outline is turned to fill its space ([ADR-0011](../adr/0011-outlines-rotate-to-fit.md)). One fixed rule decides the angle for every circuit, so no circuit, season or new track needs a choice by hand.
- The collector tries every whole-degree angle from 90° anticlockwise to 90° clockwise, so no outline is ever more than a quarter-turn from north-up.
- At each angle it scales the outline as large as it fits in the **outline area** on each device: anchored to the area's bottom-right corner and kept clear of the **name block** in its top-left corner (see Design). The score is the X scale times the OG scale, so one angle serves both devices.
- It keeps the best angle only if that draws the outline at least 20% larger than north-up, averaged over the two devices (the score is at least 1.2² times north-up's). Otherwise the outline stays north-up. Ties go to the angle nearest north-up.
- The name block is sized to the Grand Prix's own name and location, so a long name pushes the outline down instead of running into it. The collector estimates their widths from their letters, with a margin.
- The **north arrow** is shown on every Grand Prix, rotated or not, so the orientation is always readable. The collector places it per device: outside the circuit (never inside its loop), clear of the line and the name block by a fixed gap, and as close to the line as that allows.
- The angle, the outline's width on each device and the arrow's position depend only on the outline, the name and the layout, so the collector works them out once and caches them with the outline. The cache key includes a layout version; changing the Poster's layout numbers means bumping it.

### Failure behaviour
- If the schedule source fails, the collector pushes its last good schedule, marked stale, and raises the error banner naming the source and since when, as on the other screens.
- An outline that can't be fetched only logs a failure.

## Payload contract (F1 screen)

`fixtures/sample.json` must match it.

```json
{
  "updated_at": "2026-10-23T20:05:00-04:00",
  "grands_prix": [
    {
      "round": 20,
      "name": "Example Grand Prix",
      "location": "Example City, Country",
      "circuit": "example-circuit",
      "sessions": [
        { "kind": "practice_1", "name": "Practice 1", "start": "2026-10-23T12:30:00-04:00", "end": "2026-10-23T13:30:00-04:00", "local_date": "2026-10-23" }
      ]
    }
  ],
  "outlines": {
    "example-circuit": {
      "d": "M0 412L38 380…Z", "w": 1000, "h": 618, "angle": 57,
      "x": { "width": 88.5, "north": [94.1, 81.7] },
      "og": { "width": 67.6, "north": [95.7, 80.2] }
    }
  },
  "errors": [{ "source": "schedule", "since": "2026-10-23T18:00:00-04:00" }]
}
```

- `grands_prix` holds the Grands Prix whose last session starts today or later, at most 3, so the template can pick the right one at render time and a stopped collector still covers a triple-header.
- `outlines` only holds entries used by `grands_prix`. A circuit missing from it shows its name instead.
- An outline is an SVG path already turned to `angle`, scaled so its longer side is 1000, with its width `w` and height `h` in the same units. The template draws it inline, so the stroke is set in CSS and stays the same thickness at any size.
- `angle` is in degrees, clockwise positive, from −90 to 90; 0 is north-up. The north arrow is turned by the same angle.
- Per device (`x`, `og`): `width` is the outline's width as a percentage of the outline area's width, and `north` is the arrow's centre as percentages of the area's width and height.
- `kind` is one of `practice_1`, `practice_2`, `practice_3`, `sprint_qualifying`, `sprint`, `qualifying`, `race`.
- The outline adds about 2 KB per circuit, so three stay far under the 100 KB payload limit.

## Design (template)

The **Poster** layout, chosen from four themes in mock-ups. Sizes are CSS px at the X's logical width (about 1040 px; the framework scales by about 1.8) and at the OG's 800×480.
- **Name block** (top-left): the words before "Grand Prix" in heavy capitals (Inter 900; 104 px X, 68 px OG); "Grand Prix" and any words after it on a smaller line beneath; a short heavy rule; then the location.
- **Outline area**: everything above the tickets. The outline is a thick black line (14 px X, 9 px OG) with round joins, placed and turned as the payload says.
- **North arrow**: a plain "N" with a straight arrow pointing north, about the height of the "Grand Prix" line, in the spot the payload gives. The arrow turns with the outline; the "N" stays upright.
- **Tickets** (bottom): the five sessions as equal tickets in start order, each with the day, start time and session name. A session that is over is struck through (gray on the X, black on the OG). The next session is a solid black ticket with white text.
- OG small text uses the framework's NicoClean pixel face at 16 px; no OG text is smaller than 10 px.
- Framework fonts only.

## Configuration

- `.env`: `F1_WEBHOOK_UUID`, plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`.

## Out of scope (v1)

- Results, standings and live timing (spoilers).
- Where to watch.
- Countdowns, weather, circuit facts.
- Mashup layouts.
- Other series (F2, F3, F1 Academy).
- Integration with the Game Time screen.
- Pre-season testing.
- Cancelled-session marking, turn numbers and broadcast rotation (OpenF1 and MultiViewer could add these later).

## Settled source checks (2026-10-26)

- **Schedule:** Jolpica `/ergast/f1/<year>.json` lists every session's start in UTC, with `circuitId`, name and coordinates. No key; 500 requests an hour. OpenF1 has cancellation flags but no circuit ids, mixes in testing days and allows 30 requests a minute.
- **Outlines:** see ADR-0010.
- **Session lengths:** real lengths are about 35 min for the Sprint, 44 for Sprint Qualifying and 1h35 for the race, so the fixed lengths strike a session through a little late, never early.
- **Orientation:** across the 2026 calendar, the fit rule turns 14 of 23 outlines (from 18° to 90°), and the rest stay north-up. The largest gains are about 2× (Australia on the X, Canada on the OG); Canada, Monza and Madrid gain about 1.6× on the X and 2× on the OG.
