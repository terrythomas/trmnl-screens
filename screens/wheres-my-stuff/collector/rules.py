"""The screen's rules (spec: Behaviour): Parcel deliveries → stored records → the payload's tickets.

Records keep dates, not labels, so a stale record is labelled again on every run.
"""

import re
from collections import Counter
from datetime import date, datetime

# Parcel's status_code → Status (spec: Status). Unknown codes read as On the way.
STATUS = {0: "delivered", 1: "stuck", 2: "on_the_way", 3: "ready_for_pickup", 4: "out_for_delivery",
          5: "not_shipped", 6: "stuck", 7: "stuck", 8: "not_shipped"}
ORDER = ("stuck", "out_for_delivery", "delivered", "ready_for_pickup", "on_the_way", "not_shipped")
LABEL = {"stuck": "Stuck", "out_for_delivery": "Out for delivery", "delivered": "Delivered",
         "ready_for_pickup": "Ready for pickup", "on_the_way": "On the way", "not_shipped": "Not shipped yet"}

# Headline words per Status; On the way and Not shipped yet count together.
PART = {"stuck": "stuck", "out_for_delivery": "out for delivery", "delivered": "delivered",
        "ready_for_pickup": "to pick up", "on_the_way": "coming", "not_shipped": "coming"}

# Emoji and pictographs, which the OG cannot draw (spec: Payload contract).
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def record(raw: dict, carriers: dict[str, str]) -> dict:
    """One Parcel delivery as the screen stores it: JSON-safe, dates in local TZ, no labels."""
    status = STATUS.get(raw["status_code"], "on_the_way")
    # `or` as well as get(): one null field in one delivery must not fail the whole screen.
    tracking = raw.get("tracking_number") or ""
    code = raw.get("carrier_code") or ""
    newest = (raw.get("events") or [{}])[0]
    description = " ".join(EMOJI.sub("", raw.get("description") or "").split())
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


def shown(records: list[dict], now: datetime) -> list[dict]:
    """The payload's deliveries, labelled for `now`, in action order. Delivered stays until it is deleted in Parcel."""
    today = now.date()
    tickets = [(_sort_key(r, today), _ticket(r, today)) for r in records]
    return [t for _, t in sorted(tickets, key=lambda kt: kt[0])]


def headline(deliveries: list[dict]) -> str:
    counts = Counter(PART[d["status"]] for d in deliveries)  # insertion order is action order
    return " · ".join(f"{n} {part}" for part, n in counts.items())


def _ticket(r, today):
    when, late = _when(r, today)
    ticket = {"status": r["status"], "description": r["description"], "carrier": r["carrier"], "when": when}
    if r["status"] == "stuck":
        ticket["tracking"] = r["tracking"]
    else:
        ticket.update({k: r[k] for k in ("event", "location") if r[k]})
    if late:
        ticket["late"] = True
    return ticket


def _when(r, today):
    """The ticket's one line of timing (spec: When), and whether it is Late."""
    status, event_at = r["status"], _time(r["last_event_at"])
    if status == "stuck":
        if not event_at:
            return "No updates yet", False
        if r["code"] == 6:
            return f"Missed delivery · {_ago(event_at.date(), today)}", False
        if r["code"] == 7:
            return f"Carrier problem · {_ago(event_at.date(), today)}", False
        return f"No update since {_month_day(event_at.date())}", False
    if status == "delivered":
        if not event_at:
            return "Delivered", False
        clock = event_at.strftime("%-I:%M %p")
        days = (today - event_at.date()).days
        if days > 6:
            return _month_day(event_at.date()), False
        return (clock if days == 0 else f"Yesterday {clock}" if days == 1 else f"{event_at:%a} {clock}"), False
    if status == "ready_for_pickup":
        end = _date(r["expected_end"])
        return (f"Pick up by {_month_day(end)}" if end else "Waiting for you"), False
    day = _due(r)
    if day and day < today:
        return f"Late · was {_was(day, today)}", True
    if status == "out_for_delivery":
        by = _time(r["by"])
        words = _ahead(day or today, today)
        return (f"{words} by {_clock(by)}" if by else words), False
    return (_ahead(day, today) if day else "No estimate yet"), False


def _due(r):
    """The day a delivery is expected. Out for delivery falls back to its newest event, so a stored one can turn Late."""
    if r["status"] == "out_for_delivery":
        by, event_at = _time(r["by"]), _time(r["last_event_at"])
        return (by and by.date()) or _date(r["expected"]) or (event_at and event_at.date())
    return _date(r["expected"])


def _sort_key(r, today):
    """Action order, then the soonest first within a status; Delivered newest first; no date last."""
    rank = ORDER.index(r["status"])
    event_at = _time(r["last_event_at"])
    if r["status"] == "delivered":
        return rank, -event_at.timestamp() if event_at else float("inf"), 0
    if r["status"] == "stuck":
        return rank, event_at.timestamp() if event_at else float("inf"), 0
    day = _date(r["expected_end"]) if r["status"] == "ready_for_pickup" else _due(r)
    if not day:
        return rank, float("inf"), 0
    return rank, max(day, today).toordinal(), 0 if day < today else 1  # Late sorts as due today, ahead of today


def _ahead(day, today):
    days = (day - today).days
    return "Today" if days == 0 else "Tomorrow" if days == 1 else f"{day:%a}" if 1 < days <= 6 else _month_day(day)


def _ago(day, today):
    days = (today - day).days
    return "Today" if days == 0 else "Yesterday" if days == 1 else f"{day:%a}" if 1 < days <= 6 else _month_day(day)


def _was(day, today):
    return f"{day:%a}" if (today - day).days <= 6 else _month_day(day)


def _month_day(day):
    return f"{day:%b} {day.day}"


def _clock(moment):
    return moment.strftime("%-I %p" if moment.minute == 0 else "%-I:%M %p")


def _date(value):
    return date.fromisoformat(value) if value else None


def _time(value):
    return datetime.fromisoformat(value) if value else None
