# Calendar sync

The Calendar screen gets its events from an iOS Shortcut on the phone, which pushes them to the screen's LaraPaper webhook (ADR-0007). This page is the contract between the Shortcut and the template, plus the steps to build the Shortcut.

## Payload

The Shortcut POSTs JSON to `<LARAPAPER_URL>/api/custom_plugins/<CALENDAR_WEBHOOK_UUID>`:

```json
{
  "merge_variables": {
    "synced_at": "2026-10-14T09:12:00-04:00",
    "events": [
      {
        "title": "Design review",
        "start": "2026-10-14T10:00:00-04:00",
        "end": "2026-10-14T11:00:00-04:00",
        "all_day": false,
        "calendar": "Work",
        "reply": "Pending",
        "attendees": ["Alex Rivera", "Sam Chen"],
        "description": "Walk through the new onboarding flow."
      }
    ]
  }
}
```

| Field | Meaning |
|---|---|
| `synced_at` | When the Shortcut ran, ISO 8601 with offset. |
| `events` | Every event that hasn't ended yet, through the end of tomorrow, from the chosen calendars. |
| `title` | The event title. |
| `start`, `end` | ISO 8601 with offset. |
| `all_day` | `true` for all-day events. |
| `calendar` | The calendar's short label, e.g. `Work` or `Home`. |
| `reply` | Your own attendee status as iOS reports it: `Accepted`, `Pending`, `Tentative` or `Declined`. Empty when the event has no attendees. The template hides `Declined` events. |
| `attendees` | Other attendees' names, without you. |
| `description` | The event notes, untrimmed. The template cuts meeting-link boilerplate. |

Fixtures may also set `preview_now` (ISO 8601) to pin the time the template renders against. The Shortcut never sends it.

## Building the Shortcut

Action names can differ slightly between iOS versions; search for each in the action list.

1. **Find Calendar Events** where **Calendar** is any of your chosen calendars, **End Date** is after *Current Date*, and **Start Date** is before *the start of the day after tomorrow* (an **Adjust Date** action adding 2 days to the start of today).
2. **Repeat with Each** event. Inside the loop:
   1. **Set Variable** `Event` to *Repeat Item*.
   2. **Get Details of Calendar Events** for `Event`: Title, Start Date, End Date, Is All Day, Calendar, Notes, Attendees. Format both dates with **Format Date** set to ISO 8601, including the time.
   3. Map the calendar name to its short label with a **Dictionary** (`{"<calendar name>": "Work", ...}`) and **Get Value for Key**.
   4. **Repeat with Each** attendee. Inside this inner loop, first **Set Variable** `Attendee` to *Repeat Item 2*, then use `Attendee` as the input of every following action. Picking the wrong token here (*Repeat Index* instead of *Repeat Item 2*) fails with "couldn't convert from Number to Event Attendee".
      - **Get Details of Event Attendees**: Is Me, Name, Status.
      - If **Is Me** is true, **Set Variable** `Reply` to Status; otherwise **Add to Variable** `Others` the Name.
   5. Build a **Dictionary** with the payload's event fields, using `Reply` and `Others`, and **Add to Variable** `Events`. Clear `Reply` and `Others` before the next event.
3. **Get Contents of URL**: method POST, request body JSON, one field `merge_variables` (Dictionary) holding `synced_at` (**Current Date** formatted as ISO 8601) and `events` (the `Events` variable, as an Array).

## When it runs

Personal automations, each set to run without asking:

- When the Calendar app is closed, to pick up edits just made.
- When the phone joins the home Wi-Fi.
- At set times every hour during the workday.

LaraPaper is usually reachable only on the home network, so pushes made away from home fail; the Calendar collector keeps the screen current in the meantime, and the screen shows when the last sync was.
