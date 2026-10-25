"""Date-based ordering. This is the factual queue. Model priorities are estimates."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from studyguardian.dates import bucket
from studyguardian.models import Assignment, Dashboard

_ORDER = {"overdue": 0, "this_week": 1, "later": 2, "undated": 3, "completed": 4}
_FAR = datetime.max.replace(tzinfo=timezone.utc)


def sort_key(assignment: Assignment, now: datetime, tz: ZoneInfo) -> tuple:
    kind = bucket(assignment, now, tz)
    due = assignment.due_at.astimezone(timezone.utc) if assignment.due_at else _FAR
    return ( _ORDER[kind], due, assignment.course_name.casefold(), assignment.title.casefold(), assignment.id )


def ordered(assignments: list[Assignment], now: datetime, tz: ZoneInfo) -> list[Assignment]:
    return sorted(assignments, key=lambda item: sort_key(item, now, tz))


def next_action(assignments: list[Assignment], now: datetime, tz: ZoneInfo) -> Assignment | None:
    active = [item for item in assignments if bucket(item, now, tz) != "completed"]
    if not active:
        return None
    return ordered(active, now, tz)[0]


def workload_summary(assignments: list[Assignment], now: datetime, tz: ZoneInfo) -> str:
    counts = {"overdue": 0, "this_week": 0, "later": 0, "undated": 0, "completed": 0}
    for item in assignments:
        counts[bucket(item, now, tz)] += 1
    open_count = counts["overdue"] + counts["this_week"] + counts["later"] + counts["undated"]
    if not assignments:
        return "Nothing is stored yet. Connect Classroom or load the labeled demo week."
    parts = [f"{open_count} open assignment{'s' if open_count != 1 else ''}"]
    details = []
    if counts["this_week"]:
        details.append(f"{counts['this_week']} due this week")
    if counts["overdue"]:
        details.append(f"{counts['overdue']} past due")
    if counts["undated"]:
        details.append(f"{counts['undated']} with no date")
    if counts["later"]:
        details.append(f"{counts['later']} later")
    if counts["completed"]:
        details.append(f"{counts['completed']} already turned in or returned")
    if details:
        parts.append(", ".join(details))
    return ". ".join(parts) + "."


def build_dashboard(assignments: list[Assignment], now: datetime, tz: ZoneInfo) -> Dashboard:
    groups = {"overdue": [], "this_week": [], "later": [], "undated": [], "completed": []}
    for item in ordered(assignments, now, tz):
        groups[bucket(item, now, tz)].append(item)
    return Dashboard(
        next_action=next_action(assignments, now, tz),
        overdue=groups["overdue"],
        this_week=groups["this_week"],
        later=groups["later"],
        undated=groups["undated"],
        completed=groups["completed"],
        summary=workload_summary(assignments, now, tz),
    )
