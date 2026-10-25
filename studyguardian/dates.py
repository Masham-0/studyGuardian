"""Due-date conversion and week buckets.

Google Classroom publishes dueDate and dueTime in UTC. Week grouping uses the
student's timezone, so the same instant can fall in different weeks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from studyguardian.models import Assignment, COMPLETED_STATUSES

UTC = timezone.utc


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


def classroom_due_to_utc(due_date: dict | None, due_time: dict | None) -> datetime | None:
    """Convert a Classroom dueDate/dueTime pair to an aware UTC datetime.

    A date without a time is the end of that UTC calendar day. Treating it as
    midnight would mark the assignment overdue for the whole due date.
    """

    if not due_date:
        return None
    try:
        year = int(due_date["year"])
        month = int(due_date["month"])
        day = int(due_date["day"])
    except (KeyError, TypeError, ValueError):
        return None
    if due_time:
        hour = int(due_time.get("hours") or 0)
        minute = int(due_time.get("minutes") or 0)
        second = int(due_time.get("seconds") or 0)
    else:
        hour, minute, second = 23, 59, 59
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except ValueError:
        return None


def week_bounds(now: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Monday 00:00 through the next Monday 00:00 in the student's timezone."""

    local = now.astimezone(tz)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local.weekday())
    return start, start + timedelta(days=7)


def bucket(assignment: Assignment, now: datetime, tz: ZoneInfo) -> str:
    if assignment.submission_status in COMPLETED_STATUSES:
        return "completed"
    if assignment.due_at is None:
        return "undated"
    due_local = assignment.due_at.astimezone(tz)
    now_local = now.astimezone(tz)
    _start, end = week_bounds(now, tz)
    if due_local < now_local:
        return "overdue"
    if due_local < end:
        return "this_week"
    return "later"


def due_label(assignment: Assignment, now: datetime, tz: ZoneInfo) -> str:
    status = assignment.submission_status
    if assignment.due_at is None:
        base = "No due date"
    else:
        local = assignment.due_at.astimezone(tz)
        base = local.strftime("%a %d %b, %H:%M")
    if status in COMPLETED_STATUSES:
        word = "Turned in" if status == "turned_in" else "Returned"
        return f"{word} · was due {base}" if assignment.due_at else word
    if assignment.due_at is None:
        return f"{base} · {status_phrase(status)}"
    if assignment.due_at.astimezone(tz) < now.astimezone(tz):
        return f"Past due {base} · {status_phrase(status)}"
    return f"Due {base} · {status_phrase(status)}"


def status_phrase(status: str) -> str:
    if status == "unknown":
        return "submission unknown"
    if status in {"new", "created"}:
        return "not turned in"
    if status == "reclaimed_by_student":
        return "reclaimed, not turned in"
    if status == "turned_in":
        return "turned in"
    if status == "returned":
        return "returned"
    return "submission unknown"


def format_local(moment: datetime, tz: ZoneInfo) -> str:
    return moment.astimezone(tz).strftime("%a %d %b %Y, %H:%M")
