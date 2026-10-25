"""SQLite storage for assignments, plans, notes, and saved web resources."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from studyguardian.models import (
    Assignment,
    Course,
    Material,
    Note,
    PageText,
    PlanItem,
    StudySession,
    WeeklyPlan,
    WebResource,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    section TEXT,
    source TEXT NOT NULL CHECK (source IN ('live', 'demo')),
    link TEXT,
    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    due_at TEXT,
    link TEXT,
    submission_status TEXT NOT NULL DEFAULT 'unknown',
    source TEXT NOT NULL CHECK (source IN ('live', 'demo')),
    materials_json TEXT NOT NULL DEFAULT '[]',
    synced_at TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS course_materials (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    url TEXT,
    kind TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('live', 'demo')),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    edited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT,
    topic TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS note_pages (
    note_id INTEGER NOT NULL,
    page INTEGER NOT NULL,
    locator TEXT NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (note_id, page),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS saved_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL DEFAULT '',
    reputable INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT,
    pack_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS note_pages_fts USING fts5(
    text,
    note_id UNINDEXED,
    page UNINDEXED,
    tokenize = 'porter'
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dump_due(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("due_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _load_due(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _materials_from_json(raw: str) -> list[Material]:
    try:
        payload = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    materials = []
    for item in payload:
        url = (item.get("url") or "").strip()
        title = (item.get("title") or url).strip()
        if url and title:
            materials.append(Material(title=title, url=url, kind=item.get("kind") or "link"))
    return materials


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fts_enabled = False
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            try:
                conn.executescript(FTS)
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def preferences(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM preferences").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_preference(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO preferences(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def upsert_course(self, course: Course, synced_at: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO courses(id, name, section, source, link, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    section = excluded.section,
                    source = excluded.source,
                    link = excluded.link,
                    synced_at = excluded.synced_at
                """,
                (course.id, course.name, course.section, course.source, course.link, synced_at or _utc_now()),
            )

    def upsert_assignment(self, assignment: Assignment, synced_at: str | None = None) -> None:
        materials = [
            {"title": item.title, "url": item.url, "kind": item.kind} for item in assignment.materials
        ]
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO assignments(
                    id, course_id, title, description, due_at, link,
                    submission_status, source, materials_json, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    course_id = excluded.course_id,
                    title = excluded.title,
                    description = excluded.description,
                    due_at = excluded.due_at,
                    link = excluded.link,
                    submission_status = excluded.submission_status,
                    source = excluded.source,
                    materials_json = excluded.materials_json,
                    synced_at = excluded.synced_at
                """,
                (
                    assignment.id,
                    assignment.course_id,
                    assignment.title,
                    assignment.description or "",
                    _dump_due(assignment.due_at),
                    assignment.link,
                    assignment.submission_status or "unknown",
                    assignment.source,
                    json.dumps(materials),
                    synced_at or _utc_now(),
                ),
            )

    def replace_live_course(
        self,
        course: Course,
        assignments: list[Assignment],
        materials: list[dict],
    ) -> None:
        """Replace live rows for one course. Demo rows are never touched."""

        if course.source != "live":
            raise ValueError("replace_live_course only writes live Classroom data")
        now = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO courses(id, name, section, source, link, synced_at)
                VALUES (?, ?, ?, 'live', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    section = excluded.section,
                    source = 'live',
                    link = excluded.link,
                    synced_at = excluded.synced_at
                """,
                (course.id, course.name, course.section, course.link, now),
            )
            keep = [item.id for item in assignments]
            if keep:
                marks = ",".join("?" for _ in keep)
                conn.execute(
                    f"DELETE FROM assignments WHERE course_id = ? AND source = 'live' AND id NOT IN ({marks})",
                    (course.id, *keep),
                )
            else:
                conn.execute(
                    "DELETE FROM assignments WHERE course_id = ? AND source = 'live'",
                    (course.id,),
                )
            conn.execute("DELETE FROM course_materials WHERE course_id = ? AND source = 'live'", (course.id,))
            for item in assignments:
                payload = [{"title": m.title, "url": m.url, "kind": m.kind} for m in item.materials]
                conn.execute(
                    """
                    INSERT INTO assignments(
                        id, course_id, title, description, due_at, link,
                        submission_status, source, materials_json, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'live', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        course_id = excluded.course_id,
                        title = excluded.title,
                        description = excluded.description,
                        due_at = excluded.due_at,
                        link = excluded.link,
                        submission_status = excluded.submission_status,
                        source = 'live',
                        materials_json = excluded.materials_json,
                        synced_at = excluded.synced_at
                    """,
                    (
                        item.id,
                        item.course_id,
                        item.title,
                        item.description or "",
                        _dump_due(item.due_at),
                        item.link,
                        item.submission_status or "unknown",
                        json.dumps(payload),
                        now,
                    ),
                )
            for material in materials:
                conn.execute(
                    """
                    INSERT INTO course_materials(id, course_id, title, description, url, kind, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'live')
                    """,
                    (
                        material["id"],
                        course.id,
                        material.get("title") or "Untitled material",
                        material.get("description") or "",
                        material.get("url"),
                        material.get("kind") or "material",
                    ),
                )

    def list_courses(self, source: str | None = None) -> list[Course]:
        sql = "SELECT * FROM courses"
        params: tuple = ()
        if source in {"live", "demo"}:
            sql += " WHERE source = ?"
            params = (source,)
        sql += " ORDER BY name"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            Course(id=row["id"], name=row["name"], section=row["section"], source=row["source"], link=row["link"])
            for row in rows
        ]

    def list_assignments(self, source: str | None = None) -> list[Assignment]:
        sql = """
            SELECT a.*, c.name AS course_name, c.section AS course_section
            FROM assignments a
            JOIN courses c ON c.id = a.course_id
        """
        params: tuple = ()
        if source in {"live", "demo"}:
            sql += " WHERE a.source = ?"
            params = (source,)
        sql += " ORDER BY a.title"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._assignment_from_row(row) for row in rows]

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT a.*, c.name AS course_name, c.section AS course_section
                FROM assignments a JOIN courses c ON c.id = a.course_id
                WHERE a.id = ?
                """,
                (assignment_id,),
            ).fetchone()
        return self._assignment_from_row(row) if row else None

    def course_materials(self, course_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM course_materials WHERE course_id = ? ORDER BY title",
                (course_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_demo(self) -> int:
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM assignments WHERE source = 'demo'").fetchone()["n"]
            conn.execute("DELETE FROM assignments WHERE source = 'demo'")
            conn.execute("DELETE FROM course_materials WHERE source = 'demo'")
            conn.execute("DELETE FROM courses WHERE source = 'demo'")
            conn.execute("DELETE FROM study_plans WHERE source_scope = 'demo'")
        return count

    def last_live_sync(self) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(synced_at) AS synced FROM assignments WHERE source = 'live'"
            ).fetchone()
        return row["synced"] if row else None

    def save_plan(self, plan: WeeklyPlan, edited: bool = False) -> int:
        payload = json.dumps(_plan_dict(plan))
        now = _utc_now()
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM study_plans
                WHERE week_start = ? AND source_scope = ?
                ORDER BY id DESC LIMIT 1
                """,
                (plan.week_start, plan.source_scope),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE study_plans
                    SET plan_json = ?, edited = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (payload, 1 if edited else 0, now, existing["id"]),
                )
                return existing["id"]
            cursor = conn.execute(
                """
                INSERT INTO study_plans(week_start, source_scope, plan_json, edited, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plan.week_start, plan.source_scope, payload, 1 if edited else 0, now, now),
            )
            return int(cursor.lastrowid)

    def latest_plan(self, week_start: str, source_scope: str) -> tuple[WeeklyPlan, bool] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT plan_json, edited FROM study_plans
                WHERE week_start = ? AND source_scope = ?
                ORDER BY id DESC LIMIT 1
                """,
                (week_start, source_scope),
            ).fetchone()
        if not row:
            return None
        return _plan_from_dict(json.loads(row["plan_json"])), bool(row["edited"])

    def add_note(
        self,
        *,
        course_id: str | None,
        topic: str,
        filename: str,
        stored_path: str,
        sha256: str,
        pages: list[PageText],
    ) -> int:
        now = _utc_now()
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM notes
                WHERE sha256 = ? AND IFNULL(course_id, '') = IFNULL(?, '') AND topic = ?
                """,
                (sha256, course_id, topic),
            ).fetchone()
            if existing:
                return int(existing["id"])
            cursor = conn.execute(
                """
                INSERT INTO notes(course_id, topic, filename, stored_path, sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (course_id, topic, filename, stored_path, sha256, now),
            )
            note_id = int(cursor.lastrowid)
            for page in pages:
                conn.execute(
                    "INSERT INTO note_pages(note_id, page, locator, text) VALUES (?, ?, ?, ?)",
                    (note_id, page.number, page.locator, page.text),
                )
                if self.fts_enabled and page.text.strip():
                    conn.execute(
                        "INSERT INTO note_pages_fts(text, note_id, page) VALUES (?, ?, ?)",
                        (page.text, note_id, page.number),
                    )
        return note_id

    def list_notes(self, course_id: str | None = None) -> list[Note]:
        sql = "SELECT * FROM notes"
        params: tuple = ()
        if course_id:
            sql += " WHERE course_id = ?"
            params = (course_id,)
        sql += " ORDER BY created_at DESC"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_note_from_row(row) for row in rows]

    def get_note(self, note_id: int) -> Note | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return _note_from_row(row) if row else None

    def pages_for(self, note_id: int) -> list[PageText]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT page, locator, text FROM note_pages WHERE note_id = ? ORDER BY page",
                (note_id,),
            ).fetchall()
        return [PageText(number=row["page"], text=row["text"], locator=row["locator"]) for row in rows]

    def search_pages(self, note_id: int, match: str, limit: int = 6) -> list[PageText]:
        if not match.strip():
            return []
        if not self.fts_enabled:
            like = f"%{match.split()[0]}%"
            with self.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT page, locator, text FROM note_pages
                    WHERE note_id = ? AND text LIKE ?
                    ORDER BY page LIMIT ?
                    """,
                    (note_id, like, limit),
                ).fetchall()
            return [PageText(number=row["page"], text=row["text"], locator=row["locator"]) for row in rows]
        with self.connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT page FROM note_pages_fts
                    WHERE note_id = ? AND note_pages_fts MATCH ?
                    ORDER BY bm25(note_pages_fts)
                    LIMIT ?
                    """,
                    (note_id, match, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        if not rows:
            return []
        wanted = [row["page"] for row in rows]
        pages = {page.number: page for page in self.pages_for(note_id)}
        return [pages[number] for number in wanted if number in pages]

    def save_resources(self, query: str, resources: list[WebResource], reasons: dict[str, str]) -> None:
        now = _utc_now()
        with self.connect() as conn:
            for item in resources:
                conn.execute(
                    """
                    INSERT INTO saved_resources(query, title, url, snippet, reputable, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (query, item.title, item.url, item.snippet, 1 if item.reputable else 0, reasons.get(item.url, ""), now),
                )

    def list_resources(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_resources ORDER BY id DESC LIMIT 50"
            ).fetchall()
        return [dict(row) for row in rows]

    def save_exam_pack(self, course_id: str | None, pack: dict) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO exam_packs(course_id, pack_json, created_at) VALUES (?, ?, ?)",
                (course_id, json.dumps(pack), _utc_now()),
            )
            return int(cursor.lastrowid)

    def _assignment_from_row(self, row: sqlite3.Row) -> Assignment:
        return Assignment(
            id=row["id"],
            course_id=row["course_id"],
            course_name=row["course_name"],
            title=row["title"],
            description=row["description"] or "",
            due_at=_load_due(row["due_at"]),
            link=row["link"],
            submission_status=row["submission_status"] or "unknown",
            source=row["source"],
            materials=_materials_from_json(row["materials_json"]),
            course_section=row["course_section"],
        )


def _note_from_row(row: sqlite3.Row) -> Note:
    return Note(
        id=row["id"],
        course_id=row["course_id"],
        topic=row["topic"] or "",
        filename=row["filename"],
        stored_path=row["stored_path"],
        sha256=row["sha256"],
        created_at=row["created_at"],
    )


def _plan_dict(plan: WeeklyPlan) -> dict:
    return {
        "workload_summary": plan.workload_summary,
        "missing_information": plan.missing_information,
        "model": plan.model,
        "generated_at": plan.generated_at,
        "week_start": plan.week_start,
        "source_scope": plan.source_scope,
        "items": [
            {
                "assignment_id": item.assignment_id,
                "priority": item.priority,
                "reason": item.reason,
                "steps": item.steps,
                "order": item.order,
                "model_generated": item.model_generated,
            }
            for item in plan.items
        ],
        "study_sessions": [
            {
                "title": session.title,
                "minutes": session.minutes,
                "assignment_ids": session.assignment_ids,
                "note": session.note,
            }
            for session in plan.study_sessions
        ],
    }


def _plan_from_dict(payload: dict) -> WeeklyPlan:
    return WeeklyPlan(
        workload_summary=payload.get("workload_summary") or "",
        items=[
            PlanItem(
                assignment_id=item["assignment_id"],
                priority=item.get("priority") or "medium",
                reason=item.get("reason") or "",
                steps=list(item.get("steps") or []),
                order=int(item.get("order") or 0),
                model_generated=bool(item.get("model_generated", True)),
            )
            for item in payload.get("items") or []
        ],
        study_sessions=[
            StudySession(
                title=session.get("title") or "Study session",
                minutes=int(session.get("minutes") or 30),
                assignment_ids=list(session.get("assignment_ids") or []),
                note=session.get("note") or "",
            )
            for session in payload.get("study_sessions") or []
        ],
        missing_information=list(payload.get("missing_information") or []),
        model=payload.get("model") or "",
        generated_at=payload.get("generated_at") or "",
        week_start=payload.get("week_start") or "",
        source_scope=payload.get("source_scope") or "all",
    )
