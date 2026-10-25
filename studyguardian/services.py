"""Workflows the interface calls. Dashboard reads the database and does not sync."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from studyguardian.ai import (
    OllamaClient,
    explain_material,
    fts_query,
    generate_exam_pack,
    generate_weekly_plan,
    organize_resources,
)
from studyguardian.audio import synthesize
from studyguardian.classroom_client import ClassroomError, GoogleClassroomClient, SyncResult
from studyguardian.config import Settings, with_preferences
from studyguardian.dates import zone
from studyguardian.db import Database
from studyguardian.demo import seed_demo
from studyguardian.documents import DocumentError, extract_document
from studyguardian.models import Assignment, ExamPack, MaterialInsight, WeeklyPlan
from studyguardian.priority import build_dashboard
from studyguardian.search import search_learning_resources


def effective(settings: Settings, db: Database) -> Settings:
    return with_preferences(settings, db.preferences())


def student_zone(settings: Settings):
    if settings.timezone in {"", "local"}:
        return datetime.now().astimezone().tzinfo
    try:
        return zone(settings.timezone)
    except ValueError:
        return datetime.now().astimezone().tzinfo


def timezone_label(tz) -> str:
    key = getattr(tz, "key", None)
    if key:
        return key
    name = datetime.now(tz).tzname()
    return name or "local time"


def assignments_for(db: Database, source: str | None) -> list[Assignment]:
    scope = source if source in {"live", "demo"} else None
    return db.list_assignments(scope)


def dashboard(db: Database, source: str | None, now: datetime, tz: ZoneInfo):
    return build_dashboard(assignments_for(db, source), now, tz)


def sync_classroom(db: Database, client: GoogleClassroomClient) -> SyncResult:
    try:
        courses, warnings = client.fetch()
    except ClassroomError as exc:
        cached = db.list_assignments("live")
        return SyncResult(
            ok=False,
            message=str(exc),
            assignment_count=len(cached),
            from_cache=bool(cached),
        )
    count = 0
    for course, assignments, materials in courses:
        db.replace_live_course(course, assignments, materials)
        count += len(assignments)
    message = f"Saved {count} assignment{'s' if count != 1 else ''} from {len(courses)} course{'s' if len(courses) != 1 else ''}."
    if warnings:
        message += " " + " ".join(warnings)
    return SyncResult(ok=True, message=message, course_count=len(courses), assignment_count=count, from_cache=False)


def load_demo(db: Database, now: datetime, tz: ZoneInfo) -> int:
    return seed_demo(db, now, tz)


def ensure_public_demo(db: Database, settings: Settings, now: datetime, tz) -> int:
    """Seed labeled demo rows on a public host. Never writes live Classroom data."""

    if not settings.public_demo:
        return 0
    if db.list_assignments("demo"):
        return 0
    return seed_demo(db, now, tz)


def make_plan(db: Database, settings: Settings, source: str | None, now: datetime) -> WeeklyPlan:
    tz = student_zone(settings)
    scope = source if source in {"live", "demo"} else "all"
    rows = assignments_for(db, source)
    client = OllamaClient(settings.ollama_host, settings.ollama_model)
    plan = generate_weekly_plan(rows, client, now=now, tz=tz, source_scope=scope)
    db.save_plan(plan, edited=False)
    return plan


def store_upload(
    db: Database,
    settings: Settings,
    *,
    filename: str,
    data: bytes,
    course_id: str | None,
    topic: str,
) -> int:
    safe_name = Path(filename).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise DocumentError("Upload a PDF or a plain text file.")
    digest = hashlib.sha256(data).hexdigest()
    settings.notes_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.notes_dir / f"{digest}{suffix}"
    created = False
    if not destination.exists():
        destination.write_bytes(data)
        created = True
    try:
        pages = extract_document(destination)
    except DocumentError:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return db.add_note(
        course_id=course_id or None,
        topic=topic.strip(),
        filename=safe_name,
        stored_path=str(destination),
        sha256=digest,
        pages=pages,
    )


def study_insight(db: Database, settings: Settings, assignment_id: str, note_id: int) -> MaterialInsight:
    assignment = db.get_assignment(assignment_id)
    note = db.get_note(note_id)
    if assignment is None or note is None:
        raise DocumentError("Choose an assignment and a note that are already stored.")
    pages = db.pages_for(note_id)
    matched = db.search_pages(note_id, fts_query(f"{assignment.title} {assignment.description}"))
    client = OllamaClient(settings.ollama_host, settings.ollama_model)
    return explain_material(assignment, note.filename, pages, matched, client)


def exam_pack(db: Database, settings: Settings, note_ids: list[int], course_id: str | None) -> ExamPack:
    pages = []
    for note_id in note_ids:
        note = db.get_note(note_id)
        if note is None:
            continue
        for page in db.pages_for(note.id):
            pages.append((note.filename, page))
    client = OllamaClient(settings.ollama_host, settings.ollama_model)
    pack = generate_exam_pack(pages, client)
    db.save_exam_pack(
        course_id,
        {
            "revision_notes": pack.revision_notes,
            "concepts": pack.concepts,
            "flashcards": pack.flashcards,
            "questions": pack.questions,
            "outside_the_notes": pack.outside_the_notes,
            "gaps": pack.gaps,
            "removed_citations": pack.removed_citations,
            "source_labels": pack.source_labels,
            "insufficient": pack.insufficient,
            "model": pack.model,
        },
    )
    return pack


def find_resources(settings: Settings, db: Database, query: str, client: OllamaClient | None = None) -> dict:
    resources = search_learning_resources(query, settings.serpapi_key)
    model = client or OllamaClient(settings.ollama_host, settings.ollama_model)
    try:
        plan = organize_resources(query, resources, model)
    except Exception as exc:
        plan = {
            "overview": f"Gemma did not organize these results ({exc}). The links below are the live search results.",
            "steps": [
                {
                    "action": item.title,
                    "url": item.url,
                    "title": item.title,
                    "why": "Listed by the search provider.",
                    "snippet": item.snippet,
                }
                for item in resources
            ],
            "dropped_urls": [],
            "model": "",
        }
    reasons = {step["url"]: step.get("why", "") for step in plan.get("steps", [])}
    db.save_resources(query, resources, reasons)
    plan["resources"] = resources
    return plan


def speak_revision(settings: Settings, text: str) -> Path:
    destination = settings.audio_dir / "revision.mp3"
    return synthesize(text, settings.elevenlabs_key, settings.elevenlabs_voice, destination)
