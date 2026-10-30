"""The screen's rules (spec: Behaviour): Parcel deliveries → stored records → the payload's tickets.

Records keep dates, not labels, so a stale record is labelled again on every run.
"""

import re
from datetime import datetime

# Parcel's status_code → Status (spec: Status). Unknown codes read as On the way.
STATUS = {0: "delivered", 1: "stuck", 2: "on_the_way", 3: "ready_for_pickup", 4: "out_for_delivery",
          5: "not_shipped", 6: "stuck", 7: "stuck", 8: "not_shipped"}
ORDER = ("stuck", "out_for_delivery", "delivered", "ready_for_pickup", "on_the_way", "not_shipped")
LABEL = {"stuck": "Stuck", "out_for_delivery": "Out for delivery", "delivered": "Delivered",
         "ready_for_pickup": "Ready for pickup", "on_the_way": "On the way", "not_shipped": "Not shipped yet"}

# Emoji and pictographs, which the OG cannot draw (spec: Payload contract).
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def record(raw: dict, carriers: dict[str, str]) -> dict:
    """One Parcel delivery as the screen stores it: JSON-safe, dates in local TZ, no labels."""
    status = STATUS.get(raw["status_code"], "on_the_way")
    tracking = raw.get("tracking_number", "")
    code = raw.get("carrier_code", "")
    newest = (raw.get("events") or [{}])[0]
    description = " ".join(EMOJI.sub("", raw.get("description", "")).split())
    return {
        "status": status,
        "code": raw["status_code"],
        "description": description or tracking,
        "carrier": carriers.get(code, code.upper()),
        "tracking": tracking,
        "event": _trim(newest.get("event"), status),
        "location": newest.get("location") or None,
        "expected": _day(raw.get("date_expected")),
        "expected_end": _day(raw.get("date_expected_end")),
        "by": _stamp(raw.get("timestamp_expected_end")),
        "last_event_at": _event_time(newest.get("date")),
    }


def _trim(event, status):
    """Event text never repeats the status: "Delivered, front door" → "front door"."""
    if not event:
        return None
    label = LABEL[status]
    if event.lower().startswith(label.lower()):
        event = event[len(label):].lstrip(" ,.-–—:")
    return event or None


def _day(value):
    return value[:10] if value else None  # "2026-11-04 12:00:00" → "2026-11-04"


def _stamp(epoch):
    return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds") if epoch else None


def _event_time(value):
    # Event dates are in the event location's local time; read as TZ, which is close enough (spec: Which deliveries).
    try:
        return datetime.strptime(value, "%B %d, %Y %H:%M").astimezone().isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return None
