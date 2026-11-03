"""Deadlines -> an .ics calendar (RFC 5545) with reminders.

Only actions with a date, marked for the calendar, and not held for review become events
(ARCHITECTURE.md rule S2: questioned dates wait for the sender).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar, Event

from ..models import Action, Digest, is_iso_date

REMINDER_HOUR = 10  # all-day events start at 00:00, so reminders fire at 10:00 local on the chosen day


def calendar_actions(digest: Digest, held: set[int]) -> list[tuple[int, Action]]:
    """Actions that become events: readable date, marked for the calendar, not held (an unreadable date is held by
    the content step; skipping it here too keeps old or hand-edited records from crashing the render)."""
    return [(i, a) for i, a in enumerate(digest.actions) if a.add_to_calendar and is_iso_date(a.due_date) and i not in held]


def build_calendar(digest: Digest, uid_prefix: str, held: set[int] = frozenset(), *, timezone: str) -> bytes | None:
    """The .ics bytes, or None when there is nothing to put in a calendar. Times are in ``timezone``."""
    actions = calendar_actions(digest, held)
    if not actions:
        return None
    cal = Calendar()
    cal.add("prodid", "-//CareCircle//EN")
    cal.add("version", "2.0")
    for index, action in actions:
        cal.add_component(_event(action, f"{uid_prefix}-{index}@roleedge.example", ZoneInfo(timezone)))
    return cal.to_ical()


def _event(action: Action, uid: str, tz: ZoneInfo) -> Event:
    ev = Event()
    ev.add("uid", uid)
    ev.add("summary", f"{action.title_local} / {action.title}")
    ev.add("description", action.how)
    ev.add("dtstamp", datetime.now(UTC))
    day = date.fromisoformat(action.due_date)
    clock = _clock(action.due_time)
    if action.due_time and not clock:  # a time we can't read: an all-day event that still shows it as written
        ev["summary"] = f"{ev['summary']} ({action.due_time})"
    if clock:
        start = datetime.combine(day, clock, tzinfo=tz)
        ev.add("dtstart", start)
        ev.add("dtend", start + timedelta(minutes=30))
    else:
        ev.add("dtstart", day)
        ev.add("dtend", day + timedelta(days=1))
    for days in sorted(set(action.remind_days_before or [1])):
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", action.title_local)
        hours = 0 if clock else REMINDER_HOUR
        alarm.add("trigger", timedelta(days=-days, hours=hours))
        ev.add_component(alarm)
    return ev


def _clock(due_time: str | None) -> time | None:
    """The time of day for 'HH:MM' (models.normalize_time already turned '10:00 AM' into that), else None."""
    try:
        return datetime.strptime(due_time, "%H:%M").time() if due_time else None
    except ValueError:
        return None
