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
        "attendees": "Alex Rivera, Sam Chen",
        "description": "Walk through the new onboarding flow."
      }
    ]
  }
}
```

| Field | Meaning |
|---|---|
| `synced_at` | When the Shortcut ran, ISO 8601 with offset. |
| `events` | Every event today that hasn't ended yet, from the chosen calendars. |
| `title` | The event title. |
| `start`, `end` | ISO 8601 with offset. |
| `all_day` | Whether the event is all-day: `true`, `Yes` or `1` (the Shortcut sends whatever iOS gives it). |
| `calendar` | The calendar's short label, e.g. `Work` or `Home`. |
| `reply` | Your own attendee status as iOS reports it: `Accepted`, `Pending`, `Tentative` or `Declined`, in any case. Empty when the event has no attendees. The template hides declined events. |
| `attendees` | Other attendees' names, without you, separated by `, `. |
| `description` | The event notes, untrimmed. The template cuts meeting-link boilerplate. |

Fixtures may also set `preview_now` (ISO 8601) to pin the time the template renders against. The Shortcut never sends it.

## Getting the Shortcut

`screens/calendar/shortcut/Calendar Sync.shortcut` is the Shortcut, unsigned; `build.py` beside it generates it. iOS only imports signed Shortcuts, and only a Mac can sign them:

```sh
shortcuts sign --mode anyone --input "screens/calendar/shortcut/Calendar Sync.shortcut" --output ~/Desktop/"Calendar Sync.shortcut"
```

AirDrop the signed file to the phone and add it. Then run it once from the Shortcuts app. The first run sets it up:

1. It asks for LaraPaper's address as the phone reaches it (for example `http://larapaper.example:4567`) and the Calendar plugin's webhook UUID.
2. It lists the calendars that have upcoming events; pick the ones the screen should show.
3. It asks for a short label for each, such as `Work` or `Home`.

The answers are saved to `Shortcuts/trmnl-calendar.json` in iCloud Drive, and every later run reads them and syncs without asking. To change them, delete that file and run the Shortcut again. iOS asks once for access to the calendars and to iCloud Drive.

The events come from Find Calendar Events (Start Date is today, End Date is after now), and each one's reply comes from the attendee marked Is Me.

## When it runs

Personal automations, each running Calendar Sync and set to run without asking (iOS doesn't let a Shortcut file bring its own automations):

- When the Calendar app is closed, to pick up edits just made.
- When the phone joins the home Wi-Fi.
- At set times every hour during the workday.

LaraPaper is usually reachable only on the home network, so pushes made away from home fail; the Calendar collector keeps the screen current in the meantime, and the screen shows when the last sync was.
