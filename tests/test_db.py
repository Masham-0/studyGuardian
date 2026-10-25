from datetime import datetime, timedelta, timezone

from studyguardian.db import Database
from studyguardian.demo import seed_demo
from studyguardian.models import Assignment, Course, Material, PlanItem, StudySession, WeeklyPlan
from studyguardian.dates import zone

UTC = timezone.utc
NOW = datetime(2026, 10, 26, 9, tzinfo=UTC)


def live_assignment(assignment_id="classroom:c1:w1", due=None, status="unknown"):
    return Assignment(
        id=assignment_id,
        course_id="c1",
        course_name="Biology",
        title="Real lab",
        description="From Classroom",
        due_at=due,
        link="https://classroom.google.com/c/c1/a/w1/details",
        submission_status=status,
        source="live",
        materials=[Material(title="Sheet", url="https://example.com/sheet", kind="link")],
    )


def test_assignment_and_plan_round_trip(tmp_path):
    db = Database(tmp_path / "one.db")
    db.upsert_course(Course(id="c1", name="Biology", section="A", source="live", link="https://classroom.google.com/c/c1"))
    original = live_assignment(due=NOW + timedelta(days=1), status="created")
    db.upsert_assignment(original)
    plan = WeeklyPlan(
        workload_summary="Two things.",
        items=[
            PlanItem(
                assignment_id=original.id,
                priority="high",
                reason="Due soon. Estimate.",
                steps=["Read the prompt"],
                order=1,
            )
        ],
        study_sessions=[StudySession(title="Evening", minutes=25, assignment_ids=[original.id], note="")],
        missing_information=[],
        model="gemma3:4b",
        generated_at="2026-10-26T09:00:00+00:00",
        week_start="2026-10-26T00:00:00+05:30",
        source_scope="live",
    )
    db.save_plan(plan)
    reopened = Database(tmp_path / "one.db")
    loaded = reopened.list_assignments("live")
    assert loaded[0].title == "Real lab"
    assert loaded[0].due_at == original.due_at
    assert loaded[0].materials[0].url == "https://example.com/sheet"
    saved, edited = reopened.latest_plan(plan.week_start, "live")
    assert edited is False
    assert saved.items[0].steps == ["Read the prompt"]
    saved.items[0].steps = ["Read the prompt", "Sketch the setup"]
    reopened.save_plan(saved, edited=True)
    again, edited_flag = reopened.latest_plan(plan.week_start, "live")
    assert edited_flag is True
    assert again.items[0].steps == ["Read the prompt", "Sketch the setup"]


def test_due_date_change_stays_on_the_assignment_not_the_plan(tmp_path):
    db = Database(tmp_path / "due.db")
    db.upsert_course(Course(id="c1", name="Biology", section=None, source="live"))
    row = live_assignment(due=NOW + timedelta(days=2))
    db.upsert_assignment(row)
    plan = WeeklyPlan(
        workload_summary="",
        items=[PlanItem(assignment_id=row.id, priority="medium", reason="", steps=["Go"], order=1)],
        study_sessions=[],
        missing_information=[],
        model="gemma3:4b",
        generated_at="t",
        week_start="week",
        source_scope="live",
    )
    db.save_plan(plan)
    moved = live_assignment(due=NOW + timedelta(days=4))
    db.upsert_assignment(moved)
    assert db.get_assignment(row.id).due_at == moved.due_at
    saved, _edited = db.latest_plan("week", "live")
    assert not hasattr(saved.items[0], "due_at") or getattr(saved.items[0], "due_at", None) is None


def test_demo_seed_does_not_remove_live_rows(tmp_path):
    db = Database(tmp_path / "mix.db")
    db.upsert_course(Course(id="c1", name="Biology", section=None, source="live"))
    db.upsert_assignment(live_assignment())
    seed_demo(db, NOW, zone("UTC"))
    live = db.list_assignments("live")
    demo = db.list_assignments("demo")
    assert [row.id for row in live] == ["classroom:c1:w1"]
    assert demo and all(row.source == "demo" and row.title.startswith("Demo:") for row in demo)
    assert all(row.id.startswith("demo:") for row in demo)
    removed = db.clear_demo()
    assert removed == len(demo)
    assert db.list_assignments("live")[0].id == "classroom:c1:w1"
    assert db.list_assignments("demo") == []


def test_replace_live_course_leaves_demo_untouched(tmp_path):
    db = Database(tmp_path / "replace.db")
    seed_demo(db, NOW, zone("UTC"))
    demo_ids = {row.id for row in db.list_assignments("demo")}
    course = Course(id="c9", name="History", section=None, source="live", link="https://classroom.google.com/c/c9")
    db.replace_live_course(course, [live_assignment("classroom:c9:w2").__class__(
        id="classroom:c9:w2",
        course_id="c9",
        course_name="History",
        title="Paper",
        description="",
        due_at=None,
        link="https://classroom.google.com/c/c9/a/w2/details",
        submission_status="unknown",
        source="live",
    )], [])
    assert {row.id for row in db.list_assignments("demo")} == demo_ids
    db.replace_live_course(course, [], [])
    assert db.list_assignments("live") == []
    assert {row.id for row in db.list_assignments("demo")} == demo_ids
