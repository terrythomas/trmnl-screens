# Spec: Where's My Stuff? screen (v1)

Status: requirements and design settled (2026-10-30); two source facts to confirm with real data (see Open source checks)
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

The household tracks its deliveries in the Parcel app. They want an ambient answer to "where's my stuff?": what has arrived, what is at the door today, what is stuck, and what is still coming. Each answer should prompt the next action: go look, wait by the door, or do nothing. The screen should leave the playlist when there is nothing to show.

## Solution

A new **Screen**, **Where's My Stuff?**, in `screens/wheres-my-stuff/`, fed by a **Collector** like the other screens ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)). The collector reads Parcel's API (the household has Premium) every 15 minutes and pushes each **Delivery** with its **Status**, its text already worked out, in **Action order**, plus the **Headline**. The template only lays them out.

Unlike the other screens, the collector works out every label ("Today", "Late · was Wed", the headline) and the template does no date maths. The data refreshes every 15 minutes, which is close enough, and it keeps the rules in tested Python rather than Liquid.

Scanning email for tracking numbers and adding them to Parcel is a separate project, out of scope here.

The primary **Device** is the TRMNL X. The OG renders the same template ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)) and is part of the same work.

## Behaviour

### Source
- One request per run: `GET https://api.parcel.app/external/deliveries/?filter_mode=recent` with the `api-key` header. Parcel allows 20 requests an hour and caches its responses, so 15 minutes (4 an hour) leaves room for restarts and manual runs.
- Carrier names come from Parcel's supported-carriers list, cached in `STATE_DIR/wheres-my-stuff/` for a day. A carrier missing from it shows its code in capitals. A failure to fetch the list only logs a warning and never marks the screen stale.
- Absent fields are omitted by Parcel, not null. Every field except `status_code` may be missing.

### Status
Parcel's `status_code` maps to one **Status**:

| Status | Parcel codes | Shown as |
|---|---|---|
| Stuck | 1 (frozen), 6 (failed attempt), 7 (exception) | `stuck` |
| Delivered | 0 | `delivered` |
| Out for delivery | 4 | `out_for_delivery` |
| Ready for pickup | 3 | `ready_for_pickup` |
| On the way | 2 | `on_the_way` |
| Not shipped yet | 5 (not found), 8 (info received) | `not_shipped` |

An unknown code is treated as On the way and logged once per run. Stuck deliveries are always shown, never hidden, so they prompt a look.

### Which deliveries
- Everything Parcel returns. Parcel keeps a Delivered delivery in its list until it is deleted in the app, so it stays on the screen until then; there is no time limit (changed 2026-10-30, was 36 hours).
- The delivered time is the date of the newest event, read in `TZ`.
- Event dates look like `October 30, 2026 22:27`, in the event location's local time, newest first. The collector reads them as `TZ` local time; the error is at most a few hours.

### Action order
Deliveries are sorted by Status in this order: Stuck, Out for delivery, Delivered, Ready for pickup, On the way, Not shipped yet. Within a status, the soonest expected date comes first (Delivered: the newest delivery first; Stuck: the longest silent first); a delivery with no estimate goes last. A Late delivery sorts as if due today. Ties keep Parcel's order.

### When (one line per delivery)
`today` is the run's local date. A date `d` is written as "Today", "Tomorrow", the weekday ("Wed") within the next 6 days, or "Nov 12" otherwise.

| Status | `when` |
|---|---|
| Stuck | by cause, with the newest event's date: frozen (1) "No update since Oct 24" (always the month and day); failed attempt (6) "Missed delivery · Today"; exception (7) "Carrier problem · Today"; "No updates yet" with no events |
| Delivered | the delivered time, "8:12 AM"; "Yesterday 8:12 AM" when it was yesterday; "Wed 8:12 AM" within the last 6 days; "Oct 20" when older; "Delivered" when the time can't be read |
| Out for delivery | "Today by 8 PM" from `timestamp_expected_end` (`:MM` only when not on the hour); "Today" without it |
| Ready for pickup | "Pick up by Nov 6" from `date_expected_end` (the date leads, so the OG never cuts it); "Waiting for you" without it |
| On the way, Not shipped yet | the expected date (`date_expected`); "No estimate yet" without it |

- **Looking back:** "Missed delivery" and "Carrier problem" name the event's day as "Today", "Yesterday", the weekday within the last 6 days, or "Oct 20".
- **Out for delivery's day** is the date of `by` (`timestamp_expected_end`), else `date_expected`, else its newest event's date.
- **Late:** an Out for delivery, On the way or Not shipped yet delivery whose day is before `today` reads "Late · was Wed" (the date rule, looking back: weekday within 6 days, else "Oct 20") and carries `"late": true`.
- Only Out for delivery and Delivered show a time.

### The sub line
- Stuck shows the tracking number first, then the carrier, so a long carrier name never hides the number.
- Every other status shows the carrier, then the newest event's text, then its location, each when present.
- **Event text never repeats the status.** If the event starts with the status's label (case-insensitive), the label and the punctuation after it are removed: "Delivered, front door" becomes "front door". If nothing is left, the event is dropped.

### Headline
Counts in action order: Stuck, Out for delivery and Delivered by name, Ready for pickup as "to pick up", and On the way and Not shipped yet together as "coming". Every group with deliveries is named, so there are at most five counts and none is hidden. Example: "1 stuck · 3 out for delivery · 1 delivered · 1 to pick up · 5 coming". The headline counts every delivery sent, including those cut to "+N more".

### Visibility
- No deliveries: the template sets `TRMNL_SKIP_DISPLAY`, unless the error banner has been up for 24 hours or more, so a broken collector is never mistaken for a quiet week.
- The screen leaves the playlist on its own once every delivery is gone from Parcel, Delivered ones included.

### Failure behaviour
- If Parcel fails, the collector pushes its last good deliveries marked stale and raises the error banner ("Parcel down since 7:15 AM", with the weekday when it started on an earlier day), as on the other screens. Labels are worked out again from the stored data on every run, so a stale "Today" still becomes "Yesterday" or Late.
- A missing key, or Parcel answering HTTP 401 or 403, is reported as source `parcel-key`, and the banner reads "Parcel key rejected since 6:02 PM" instead of "Parcel down", since it will not fix itself. With nothing to show it reads "Nothing to show until the Parcel key is fixed".
- Errors never contain the URL or the key ([ADR-0003](../adr/0003-public-repo-secrets-policy.md)).

## Payload contract (Where's My Stuff? screen)

`fixtures/sample.json` (a copy of `fixtures/busy.json`) and every other fixture have this shape.

```json
{
  "updated_at": "2026-10-30T09:41:00-04:00",
  "headline": "1 stuck · 1 delivered · 1 coming",
  "deliveries": [
    { "status": "stuck", "description": "Replacement charger", "carrier": "DHL", "when": "No update since Oct 24", "tracking": "1Z999AA10123456784" },
    { "status": "delivered", "description": "Keyboard", "carrier": "USPS", "when": "8:12 AM", "event": "front door", "location": "Springfield, OH" },
    { "status": "on_the_way", "description": "Laptop", "carrier": "FedEx", "when": "Late · was Wed", "late": true, "event": "Departed facility", "location": "Indianapolis, IN" }
  ],
  "stale": true,
  "errors": [{ "source": "parcel", "since": "2026-10-30T07:15:00-04:00" }]
}
```

- `deliveries` holds every shown delivery in action order. The template shows the first 8 (7 on the X while `errors` is not empty, since the banner costs a row) and counts the rest as "+N more deliveries in Parcel". Action order makes the cut ones the furthest-out On the way and Not shipped yet; another status is cut only when more deliveries than that need you.
- `status` is one of `stuck`, `delivered`, `out_for_delivery`, `ready_for_pickup`, `on_the_way`, `not_shipped`.
- `description` falls back to the tracking number when Parcel has none. Emoji are removed from it (the OG cannot draw them). `event`, `location`, `tracking` (Stuck only) and `late` are left out when empty or false.
- `stale` is present only while Parcel is failing and `deliveries` holds its last good data. With no deliveries stored there is no `stale`; the banner alone reports the failure.
- With no deliveries, `deliveries` is `[]` and `headline` is `""`.

## Design (template)

The **Tickets** theme, chosen from two themes in mock-ups and refined through two design critiques and passes on layout, edge cases, copy, type and device fit. The renders are in the private gallery artifact (see the plan).

- **Ticket:** a boxed label per delivery with its status on a tab: icon and status name in capitals. Stuck and Out for delivery tabs are solid black (go look, wait by the door); Stuck's icon is a yield sign (an upside-down triangle, drawn, a size larger than the other icons). Delivered's tab is outlined: inside its box on an X row, hugging its icon and label on a tall ticket. Other tabs are plain.
- **Headline** above the tickets, heavy, with a rule under it, on one line. On the X it is 46px, shrinking to fit one line when long (2240 ÷ length, in px). Hidden when blank.
- **X, 4 or more deliveries:** one column of up to 8 rows: tab, then description (32px) over the sub line (19px), then `when` (30px) on the right; 4–5 rows scale everything by 1.2. A long `when` wraps onto a second line (at most 320px wide) instead of squeezing the description; a two-part `when` ("Missed delivery · Today") wraps only after its dot. A Late `when` is a black pill. Long descriptions (over 26 characters) drop to 27px; all clamp to one line. In a run of one status, only the first tab names it; the rest show its icon alone, like a ditto mark.
- **X, 2–3 deliveries (tall):** each ticket fills its share of the height: tab across the top, description (up to 3 lines), sub line, then `when`, as one centred group sharing one left edge. Three tall tickets under the error banner step their text down one size so the `when` line still fits.
- **One delivery (poster), both devices:** no box; an outlined tab, then a large description, a very large `when`, and the sub line, centred vertically.
- **OG:** a grid filled row by row, left to right: one column for 1–3 deliveries, two for more, up to 4 rows. Tab and `when` share the top line; the description sits under them. The sub line is hidden except Stuck's tracking line. Text grows when there are few deliveries. When a `when` is cut, only its words are cut, never the STALE mark. In the two-column grid the STALE mark sits in the card's bottom-right corner, since a half-width card has no room for it beside the `when`.
- **Overflow:** "+N more deliveries in Parcel" under the list.
- **Error banner:** a black pill above the headline ("Parcel down since…" or "Parcel key rejected since…"); each `when` gets a small STALE mark while stale. Empty and failing: "Nothing to show until Parcel is back".
- **Title bar:** a package icon, "Where's My Stuff?", and "updated 9:41 AM".
- All text is black: grey breaks up on the OG and fades across a room. Every payload string is escaped. Icons are inline SVG, never emoji. Framework fonts only. LaraPaper does not add the `view view--full` wrapper, so the template includes it.

## Configuration

- `.env`: `PARCEL_API_KEY`, `WHERES_MY_STUFF_WEBHOOK_UUID`, `WHERES_MY_STUFF_PLUGIN_ID`, optional `WHERES_MY_STUFF_INTERVAL_MINUTES`, plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`.
- `settings.yml`: webhook strategy, refresh interval 15.

## Testing

- **Source adapter:** pytest with `httpx.MockTransport` against invented responses that keep Parcel's real shape (never a real response; [ADR-0003](../adr/0003-public-repo-secrets-policy.md)): the request's path, query and header; error wrapping without the URL or key; omitted fields.
- **Screen collector:** pytest with a fake source and a fixed `now`, covering the status map, Delivered staying, action order, every `when` row, Late, event de-duplication, the headline fold, stale relabelling and the empty payload.
- **Template:** checked by eye in `trmnlp serve` with every fixture in `fixtures/` on the X and the OG, then once on LaraPaper. The fixtures cover a busy day (`busy`, `sample`), long and odd text (`edge`), 1–3 deliveries (`quiet`, `door`, `stuck`), failures with data (`stale`, `busy-stale`, `bad-key`) and without (`empty-error`). Every fixture is in action order.

## Out of scope (v1)

- Adding deliveries to Parcel, including from email.
- Mashup layouts.
- Delivery photos, maps, or history beyond the newest event.

## Open source checks

Confirm with real data before calling the screen done, then delete this section:
- What a Stuck delivery's response looks like, especially whether `date_expected` is kept.

Settled: `recent` keeps Delivered deliveries until they are deleted in Parcel (seen 2026-10-30). A wrong key gets HTTP 401 with `{"success": false, "error_message": "Account not found"}` (checked 2026-10-30), so it reads as "Parcel key rejected". On LaraPaper (checked 2026-10-30), Liquid's `size` counts characters, so the headline shrink matches the preview, but `escape` turns "·" into `&middot;`: text is split on " · " before it is escaped.
