from datetime import datetime, timedelta, timezone

from studyguardian.dates import due_label, status_phrase
from studyguardian.models import Assignment
from studyguardian.priority import build_dashboard, next_action

UTC = timezone.utc
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


def item(id_, due, status="unknown", title=None):
    return Assignment(
        id=id_,
        course_id="c",
        course_name="Biology",
        title=title or id_,
        description="",
        due_at=due,
        link=None,
        submission_status=status,
        source="live",
    )


def test_overdue_beats_this_week_and_undated_is_last():
    rows = [
        item("undated", None),
        item("later", NOW + timedelta(days=12), "created"),
        item("soon", NOW + timedelta(days=1), "created"),
        item("late", NOW - timedelta(days=2), "unknown"),
        item("done", NOW - timedelta(days=1), "turned_in"),
    ]
    action = next_action(rows, NOW, UTC)
    assert action.id == "late"
    board = build_dashboard(rows, NOW, UTC)
    assert [row.id for row in board.overdue] == ["late"]
    assert [row.id for row in board.this_week] == ["soon"]
    assert [row.id for row in board.undated] == ["undated"]
    assert [row.id for row in board.completed] == ["done"]
    assert "incomplete" not in board.summary.lower()


def test_more_overdue_work_comes_first():
    rows = [
        item("older", NOW - timedelta(days=5), "created"),
        item("newer", NOW - timedelta(days=1), "new"),
    ]
    assert next_action(rows, NOW, UTC).id == "older"


def test_unknown_past_due_is_not_labeled_incomplete():
    row = item("mystery", NOW - timedelta(hours=3), "unknown", title="Essay")
    label = due_label(row, NOW, UTC)
    assert "Past due" in label
    assert status_phrase(row.submission_status) == "submission unknown"
    assert "incomplete" not in label.lower()


def test_explicit_created_state_can_say_not_turned_in():
    row = item("open", NOW + timedelta(days=1), "created")
    assert "not turned in" in due_label(row, NOW, UTC)
    assert "incomplete" not in due_label(row, NOW, UTC)


def test_no_open_work_has_no_next_action():
    rows = [item("done", NOW, "returned")]
    assert next_action(rows, NOW, UTC) is None
