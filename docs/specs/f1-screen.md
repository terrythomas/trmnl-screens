# Spec: F1 screen (v1)

Status: requirements settled, design and sources still to verify
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

The household follows Formula 1 but usually watches sessions delayed, especially races in Australia, Asia and Europe. They want an ambient answer on race weekends: which Grand Prix it is, what the circuit looks like, and when each session starts in local time. The screen must never give away a result, and it should stay out of the playlist on days with nothing on.

## Solution

A new **Screen**, **F1**, in `screens/f1/`, fed by a **Collector** like the other screens ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). The collector reads free public sources only, with no keys or accounts. It pushes the season's schedule and the circuit outlines it needs. The template picks the **Grand Prix** and works out the visibility and **session** states from the render time, so the screen appears, strikes through finished sessions and leaves the playlist on the clock, without a fetch.

The primary **Device** is the TRMNL X; the OG renders the same template ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)) and is part of the same work.

## Behaviour

### Sessions
- A Grand Prix weekend has five sessions, as the source lists them:
  - **Conventional weekend:** Practice 1, Practice 2, Practice 3, Qualifying, Race.
  - **Sprint weekend:** Practice 1, Sprint Qualifying, Sprint, Qualifying, Race.
- Each session has a start time from the source. Its **session end** is the start plus a fixed length: 1 hour for practice, qualifying and Sprint Qualifying sessions, 1 hour for the Sprint, and 2 hours for the race. Delays and red flags are ignored; the screen shows nothing live.
- A session is **over** once its session end has passed.
- A session the source marks as cancelled is over from the start, and shown as cancelled.

### Session days and visibility (template)
- A **session day** is a local date (`TZ`) on which at least one session starts. A session belongs to the local day it starts on, so Japan's Friday practice at 11:30 JST is a Thursday-evening session day in the US.
- The screen is in the playlist only on session days. It stays up for the whole day, including after its last session, so on race day it shows until midnight.
- On every other day the screen sets `TRMNL_SKIP_DISPLAY`, unless the error banner has been up for 24 hours or more, so a broken collector is never mistaken for a weekend without a race.

### Which Grand Prix
- On a session day, the screen shows the Grand Prix with a session starting that day. Back-to-back and triple-header weekends need no special rule: each weekend's session days pick their own Grand Prix.
- If two Grands Prix ever have sessions on the same local day, the one whose race is earlier is shown.

### Schedule (template)
- The schedule lists all five sessions of the Grand Prix in start order, each with its local day and start time, e.g. "Fri 7:30 AM".
- Sessions that are over stay in the list with their name and time struck through. A cancelled session is struck through and marked "Cancelled".
- The **next session** is the first that is not over. It is set apart so it can be read at a glance. Once the race is over there is no next session, and the whole schedule is struck through until midnight.

### No spoilers
- The screen never shows results, positions, the grid, fastest laps, winners, championship standings, live status or session progress.
- The collector does not request any results, standings or timing endpoints, so no result can reach the payload by accident.

### Circuit outline
- Each Grand Prix shows its circuit's outline, large.
- No outline artwork is committed to the repository, including tests and fixtures, in the spirit of [ADR-0009](../adr/0009-logos-fetched-at-runtime.md). The collector gets the outline at runtime and caches it in `STATE_DIR/f1/`.
- The outline is a plain line drawing, so the X and OG can use the same drawing; the OG needs no gray.
- A missing outline falls back to the circuit name in its place. It never marks the screen stale.

### Failure behaviour
- If the schedule source fails, the collector pushes its last good schedule, marked stale, and raises the error banner naming the source and since when, as on the other screens.
- An outline that can't be fetched only logs a failure.

## Payload contract (F1 screen)

Draft; `fixtures/sample.json` must match it once settled.

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
        { "kind": "practice_1", "name": "Practice 1", "start": "2026-10-23T12:30:00-04:00", "end": "2026-10-23T13:30:00-04:00", "local_date": "2026-10-23", "cancelled": false }
      ]
    }
  ],
  "outlines": { "example-circuit": "data:image/svg+xml;base64,…" },
  "errors": [{ "source": "schedule", "since": "2026-10-23T18:00:00-04:00" }]
}
```

- `grands_prix` holds the Grands Prix with a session from yesterday onward, up to a small limit, so the template can pick the right one at render time.
- `outlines` only holds entries used by `grands_prix`. A circuit missing from it shows its name instead.
- `kind` is one of `practice_1`, `practice_2`, `practice_3`, `sprint_qualifying`, `sprint`, `qualifying`, `race`.

## Design (template)

To be decided in mock-ups, X first, then OG.
- The circuit outline is the largest element; the schedule sits beside it on the X and under or beside it on the OG, whichever reads better at 800×480.
- The title shows the Grand Prix name and location.
- Struck-through sessions stay legible at 1-bit: strike-through in regular weight, the next session in bold.
- OG text is never smaller than 10 px.

## Configuration

- `.env`: `F1_WEBHOOK_UUID`, plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`.

## Out of scope (v1)

- Results, standings and live timing (spoilers).
- Where to watch.
- Countdowns, weather, circuit facts.
- Mashup layouts.
- Other series (F2, F3, F1 Academy).
- Integration with the Game Time screen.

## Open items to verify early

- **Schedule source:** Jolpica (the Ergast successor) lists every session's start time in UTC and needs no key; OpenF1 is the alternative. Check which one reports cancelled or rescheduled sessions, and how quickly.
- **Outline source and licence:** options include drawing the outline from public circuit coordinates (for example OpenF1 car position data from a past session) or fetching an existing SVG set. Check the licence before choosing, as for ADR-0009. If the choice is significant, record it as an ADR.
- **Sprint length:** confirm the fixed 1-hour Sprint length is close enough to strike it through at a sensible time.
