from datetime import datetime, timezone
from pathlib import Path

from studyguardian.config import load_settings
from studyguardian.db import Database
from studyguardian.models import Assignment, Course
from studyguardian.services import ensure_public_demo


def test_public_demo_ignores_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDYGUARDIAN_PUBLIC_DEMO", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "audio")
    monkeypatch.setenv("STUDYGUARDIAN_DATA_DIR", str(tmp_path))
    settings = load_settings(env_file=Path(tmp_path) / "missing.env")
    assert settings.public_demo is True
    assert settings.google_configured is False
    assert settings.google_client_id is None
    assert settings.serpapi_key is None
    assert settings.elevenlabs_key is None


def test_public_demo_seeds_demo_rows_only(tmp_path):
    db = Database(tmp_path / "demo.db")
    db.upsert_course(Course(id="c1", name="Real", section=None, source="live"))
    db.upsert_assignment(
        Assignment(
            id="classroom:c1:1",
            course_id="c1",
            course_name="Real",
            title="Real essay",
            description="",
            due_at=None,
            link="https://classroom.google.com/c/c1/a/1/details",
            submission_status="unknown",
            source="live",
        )
    )
    settings = load_settings(env_file=Path(tmp_path) / "missing.env")
    settings = type(settings)(**{**settings.__dict__, "public_demo": True})
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    first = ensure_public_demo(db, settings, now, timezone.utc)
    second = ensure_public_demo(db, settings, now, timezone.utc)
    assert first == 5
    assert second == 0
    assert [row.title for row in db.list_assignments("live")] == ["Real essay"]
    assert all(row.source == "demo" and row.title.startswith("Demo:") for row in db.list_assignments("demo"))
