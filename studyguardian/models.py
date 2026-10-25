"""Domain records. Due instants are timezone-aware UTC. Titles come from a source."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Source = Literal["live", "demo"]

COMPLETED_STATUSES = frozenset({"turned_in", "returned"})

# Explicit Classroom states that mean the student has not turned the work in.
# Anything else, including a missing record, stays "unknown".
NOT_TURNED_IN_STATUSES = frozenset({"new", "created", "reclaimed_by_student"})


@dataclass(frozen=True)
class Material:
    title: str
    url: str
    kind: str


@dataclass
class Course:
    id: str
    name: str
    section: str | None
    source: str
    link: str | None = None


@dataclass
class Assignment:
    id: str
    course_id: str
    course_name: str
    title: str
    description: str
    due_at: datetime | None
    link: str | None
    submission_status: str
    source: str
    materials: list[Material] = field(default_factory=list)
    course_section: str | None = None

    @property
    def is_demo(self) -> bool:
        return self.source == "demo"


@dataclass(frozen=True)
class PageText:
    number: int
    text: str
    locator: str


@dataclass
class Note:
    id: int
    course_id: str | None
    topic: str
    filename: str
    stored_path: str
    sha256: str
    created_at: str


@dataclass
class PlanItem:
    assignment_id: str
    priority: str
    reason: str
    steps: list[str]
    order: int
    model_generated: bool = True


@dataclass
class StudySession:
    title: str
    minutes: int
    assignment_ids: list[str]
    note: str


@dataclass
class WeeklyPlan:
    workload_summary: str
    items: list[PlanItem]
    study_sessions: list[StudySession]
    missing_information: list[str]
    model: str
    generated_at: str
    week_start: str
    source_scope: str

    def ordered_items(self) -> list[PlanItem]:
        return sorted(self.items, key=lambda item: (item.order, item.assignment_id))


@dataclass
class SourceSection:
    filename: str
    locator: str
    page: int | None
    summary: str
    why_it_matters: str


@dataclass
class MaterialInsight:
    sections: list[SourceSection]
    concepts: list[dict]
    relation_from_notes: str
    gaps: str
    general_explanation: str
    removed_citations: list[str]
    pages_sent: list[str]
    truncated: bool
    weak_match: bool
    insufficient: bool
    model: str


@dataclass
class ExamPack:
    revision_notes: list[dict]
    concepts: list[dict]
    flashcards: list[dict]
    questions: list[dict]
    outside_the_notes: str
    gaps: list[str]
    removed_citations: list[str]
    source_labels: list[str]
    insufficient: bool
    model: str


@dataclass
class WebResource:
    title: str
    url: str
    snippet: str
    reputable: bool


@dataclass
class Dashboard:
    next_action: Assignment | None
    overdue: list[Assignment]
    this_week: list[Assignment]
    later: list[Assignment]
    undated: list[Assignment]
    completed: list[Assignment]
    summary: str

    def upcoming_by_course(self) -> list[tuple[str, list[Assignment]]]:
        grouped: dict[str, list[Assignment]] = {}
        ordered = self.overdue + self.this_week + self.undated
        for assignment in ordered:
            grouped.setdefault(assignment.course_name, []).append(assignment)
        return list(grouped.items())
