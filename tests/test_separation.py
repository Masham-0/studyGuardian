from datetime import datetime, timezone

from studyguardian.classroom_client import (
    READONLY_SCOPES,
    ClassroomNetworkError,
    assignment_from_coursework,
    best_submission,
    course_from_payload,
    drain_pages,
    explain_status,
    materials_from_payload,
)
from studyguardian.db import Database
from studyguardian.demo import seed_demo
from studyguardian.models import Course
from studyguardian.priority import build_dashboard
from studyguardian.services import dashboard, sync_classroom

UTC = timezone.utc
NOW = datetime(2026, 10, 26, 15, tzinfo=UTC)


def test_scopes_are_read_only():
    assert len(READONLY_SCOPES) == 4
    for scope in READONLY_SCOPES:
        assert scope.endswith(".readonly")
        assert "coursework.students" not in scope
        assert "rosters" not in scope
    blob = " ".join(READONLY_SCOPES)
    assert "classroom.coursework.me " not in blob + " "


def test_normalize_fixture_does_not_invent_fields():
    course = course_from_payload(
        {
            "id": "100",
            "name": "Biology",
            "section": "Period 2",
            "courseState": "ACTIVE",
            "alternateLink": "https://classroom.google.com/c/100",
        }
    )
    work = {
        "id": "55",
        "title": "Osmosis lab",
        "description": "Compare two solutions.",
        "state": "PUBLISHED",
        "alternateLink": "https://classroom.google.com/c/100/a/55/details",
        "dueDate": {"year": 2026, "month": 10, "day": 28},
        "dueTime": {"hours": 16, "minutes": 0},
        "materials": [
            {"link": {"url": "https://openstax.org/books/biology-2e/pages/5-2-passive-transport", "title": "OpenStax"}},
            {"driveFile": {"driveFile": {"title": "Missing link"}}},
        ],
    }
    assert best_submission([]) == "unknown"
    assignment = assignment_from_coursework(course, work, best_submission([]))
    assert assignment.submission_status == "unknown"
    assert assignment.title == "Osmosis lab"
    assert assignment.link.endswith("/55/details")
    assert [item.url for item in assignment.materials] == [
        "https://openstax.org/books/biology-2e/pages/5-2-passive-transport"
    ]
    draft = assignment_from_coursework(course, {**work, "state": "DRAFT"}, "created")
    assert draft is None
    created = assignment_from_coursework(course, work, best_submission(["CREATED"]))
    assert created.submission_status == "created"


def test_materials_skip_entries_without_urls():
    assert materials_from_payload([{"youtubeVideo": {"title": "No url"}}]) == []


def test_pagination_stops_on_a_repeated_token():
    pages = {
        None: {"courses": [{"id": "1"}], "nextPageToken": "a"},
        "a": {"courses": [{"id": "2"}], "nextPageToken": "a"},
    }
    rows = drain_pages(lambda token: pages[token], "courses")
    assert [row["id"] for row in rows] == ["1", "2"]


def test_demo_and_live_filters(tmp_path):
    db = Database(tmp_path / "sep.db")
    seed_demo(db, NOW, UTC)
    db.upsert_course(Course(id="c1", name="Real biology", section=None, source="live"))
    from studyguardian.models import Assignment

    db.upsert_assignment(
        Assignment(
            id="classroom:c1:1",
            course_id="c1",
            course_name="Real biology",
            title="Real essay",
            description="",
            due_at=NOW,
            link="https://classroom.google.com/c/c1/a/1/details",
            submission_status="unknown",
            source="live",
        )
    )
    assert all(row.source == "demo" for row in db.list_assignments("demo"))
    assert all(row.source == "live" for row in db.list_assignments("live"))
    assert len(db.list_assignments(None)) == len(db.list_assignments("demo")) + 1


def test_offline_dashboard_reads_cache_when_sync_fails(tmp_path):
    db = Database(tmp_path / "off.db")
    db.upsert_course(Course(id="c1", name="Biology", section=None, source="live", link=None))
    from studyguardian.models import Assignment

    db.upsert_assignment(
        Assignment(
            id="classroom:c1:9",
            course_id="c1",
            course_name="Biology",
            title="Cached lab",
            description="Already stored",
            due_at=NOW,
            link="https://classroom.google.com/c/c1/a/9/details",
            submission_status="unknown",
            source="live",
        )
    )

    class Offline:
        def fetch(self):
            raise ClassroomNetworkError("Classroom could not be reached.")

    result = sync_classroom(db, Offline())
    assert result.ok is False
    assert result.from_cache is True
    board = dashboard(db, "live", NOW, UTC)
    assert board.next_action.title == "Cached lab"
    built = build_dashboard(db.list_assignments("live"), NOW, UTC)
    assert "Cached lab" in built.summary or built.next_action.title == "Cached lab"
    assert explain_status(None).lower().startswith("classroom could not be reached")
