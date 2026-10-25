from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from studyguardian.dates import bucket, classroom_due_to_utc, due_label, status_phrase, week_bounds
from studyguardian.models import Assignment

UTC = timezone.utc
IST = ZoneInfo("Asia/Kolkata")
LA = ZoneInfo("America/Los_Angeles")


def assignment(**kwargs) -> Assignment:
    base = dict(
        id="a1",
        course_id="c1",
        course_name="Biology",
        title="Lab",
        description="",
        due_at=None,
        link=None,
        submission_status="unknown",
        source="live",
    )
    base.update(kwargs)
    return Assignment(**base)


def test_classroom_due_time_is_utc():
    due = classroom_due_to_utc({"year": 2026, "month": 10, "day": 26}, {"hours": 6, "minutes": 30})
    assert due == datetime(2026, 10, 26, 6, 30, tzinfo=UTC)


def test_date_without_time_is_end_of_utc_day():
    due = classroom_due_to_utc({"year": 2026, "month": 10, "day": 26}, None)
    assert due == datetime(2026, 10, 26, 23, 59, 59, tzinfo=UTC)
    assert classroom_due_to_utc(None, {"hours": 1}) is None
    assert classroom_due_to_utc({"year": 2026, "month": 13, "day": 1}, None) is None


def test_same_instant_falls_in_different_weeks():
    now = datetime(2026, 10, 25, 22, 0, tzinfo=UTC)
    due = assignment(due_at=datetime(2026, 10, 26, 6, 0, tzinfo=UTC), submission_status="created")
    assert bucket(due, now, UTC) == "later"
    assert bucket(due, now, IST) == "this_week"
    utc_start, utc_end = week_bounds(now, UTC)
    ist_start, ist_end = week_bounds(now, IST)
    assert utc_end == datetime(2026, 10, 26, 0, 0, tzinfo=UTC)
    assert ist_start.astimezone(IST).weekday() == 0
    assert due.due_at < utc_end or bucket(due, now, UTC) == "later"
    assert ist_start <= due.due_at.astimezone(IST) < ist_end


def test_los_angeles_sunday_evening_stays_in_that_week():
    now = datetime(2026, 10, 26, 1, 0, tzinfo=UTC)  # Sunday 18:00 in Los Angeles
    due = assignment(due_at=datetime(2026, 10, 26, 5, 0, tzinfo=UTC), submission_status="new")
    assert now.astimezone(LA).weekday() == 6
    assert bucket(due, now, LA) == "this_week"
    assert "Past due" not in due_label(due, now, LA)


def test_missing_due_date_is_undated_and_not_called_incomplete():
    item = assignment(due_at=None, submission_status="unknown")
    now = datetime(2026, 10, 26, 12, tzinfo=UTC)
    assert bucket(item, now, UTC) == "undated"
    label = due_label(item, now, UTC)
    assert "No due date" in label
    assert "incomplete" not in label.lower()
    assert status_phrase("unknown") == "submission unknown"
    assert "incomplete" not in status_phrase("created")


def test_turned_in_is_completed_even_if_the_date_passed():
    item = assignment(
        due_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        submission_status="returned",
    )
    now = datetime(2026, 10, 26, 12, tzinfo=UTC)
    assert bucket(item, now, UTC) == "completed"
    assert due_label(item, now, UTC).startswith("Returned")


def test_week_starts_monday():
    now = datetime(2026, 10, 28, 15, tzinfo=IST)  # Wednesday
    start, end = week_bounds(now, IST)
    assert start.astimezone(IST).weekday() == 0
    assert end - start == (end - start)
    assert (end - start).days == 7
