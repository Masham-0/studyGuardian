"""Labeled synthetic coursework. Kept in separate rows from Classroom syncs."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from studyguardian.db import Database
from studyguardian.models import Assignment, Course, Material

DEMO_BIO = "demo:course:cell-bio"
DEMO_HIST = "demo:course:world-history"


def _local(now: datetime, tz: ZoneInfo, days: int, hour: int, minute: int = 0) -> datetime:
    local = now.astimezone(tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (local + timedelta(days=days)).astimezone(tz)


def demo_records(now: datetime, tz: ZoneInfo) -> tuple[list[Course], list[Assignment]]:
    courses = [
        Course(
            id=DEMO_BIO,
            name="Demo · Cell Biology",
            section="Synthetic sample",
            source="demo",
            link=None,
        ),
        Course(
            id=DEMO_HIST,
            name="Demo · World History",
            section="Synthetic sample",
            source="demo",
            link=None,
        ),
    ]
    assignments = [
        Assignment(
            id="demo:bio:osmosis",
            course_id=DEMO_BIO,
            course_name=courses[0].name,
            title="Demo: Osmosis lab write-up",
            description=(
                "Synthetic demo assignment. Explain osmosis in plant cells and compare "
                "a hypotonic and a hypertonic solution. This is not a real Classroom task."
            ),
            due_at=_local(now, tz, 1, 17),
            link=None,
            submission_status="created",
            source="demo",
            materials=[
                Material(
                    title="Demo link: OpenStax Biology, membrane transport",
                    url="https://openstax.org/books/biology-2e/pages/5-2-passive-transport",
                    kind="link",
                )
            ],
        ),
        Assignment(
            id="demo:bio:mitosis",
            course_id=DEMO_BIO,
            course_name=courses[0].name,
            title="Demo: Mitosis diagram",
            description="Synthetic demo assignment. Label the stages of mitosis. No due date was set on purpose.",
            due_at=None,
            link=None,
            submission_status="unknown",
            source="demo",
            materials=[],
        ),
        Assignment(
            id="demo:hist:source",
            course_id=DEMO_HIST,
            course_name=courses[1].name,
            title="Demo: Primary source paragraph",
            description="Synthetic demo assignment. This due time is already in the past.",
            due_at=_local(now, tz, -2, 9),
            link=None,
            submission_status="unknown",
            source="demo",
            materials=[],
        ),
        Assignment(
            id="demo:hist:map",
            course_id=DEMO_HIST,
            course_name=courses[1].name,
            title="Demo: Map quiz",
            description="Synthetic demo assignment already marked turned in.",
            due_at=_local(now, tz, -1, 12),
            link=None,
            submission_status="turned_in",
            source="demo",
            materials=[],
        ),
        Assignment(
            id="demo:bio:later",
            course_id=DEMO_BIO,
            course_name=courses[0].name,
            title="Demo: Enzyme review",
            description="Synthetic demo assignment due after this week.",
            due_at=_local(now, tz, 10, 15),
            link=None,
            submission_status="new",
            source="demo",
            materials=[],
        ),
    ]
    return courses, assignments


def seed_demo(db: Database, now: datetime, tz: ZoneInfo) -> int:
    courses, assignments = demo_records(now, tz)
    for course in courses:
        db.upsert_course(course)
    for assignment in assignments:
        db.upsert_assignment(assignment)
    return len(assignments)
