"""This Week: source assignments plus an editable plan generated only on request."""

from __future__ import annotations

import streamlit as st

from studyguardian.ai import ModelOutputError, OllamaError
from studyguardian.dates import week_bounds
from studyguardian.dates import bucket as date_bucket
from studyguardian.models import PlanItem, StudySession, WeeklyPlan
from studyguardian.services import dashboard, make_plan, timezone_label
from studyguardian.ui.common import assignment_card, context


def _scope_name(scope: str | None) -> str:
    return scope if scope in {"live", "demo"} else "all"


def render() -> None:
    settings, db, tz, now, scope = context()
    board = dashboard(db, scope, now, tz)
    start, end = week_bounds(now, tz)
    st.markdown("## This week")
    st.caption(
        f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')} · {timezone_label(tz)}. "
        "Due dates below come from the stored assignment, not from the model."
    )
    st.write(board.summary)
    if board.next_action:
        st.markdown('<p class="kicker">Next action</p>', unsafe_allow_html=True)
        assignment_card(board.next_action, now, tz, compact=True)

    sections = [
        ("Past due", board.overdue),
        ("Due this week", board.this_week),
        ("No due date", board.undated),
        ("Later", board.later),
        ("Turned in or returned", board.completed),
    ]
    for title, rows in sections:
        if not rows:
            continue
        st.markdown(f"#### {title}")
        grouped: dict[str, list] = {}
        for item in rows:
            grouped.setdefault(item.course_name, []).append(item)
        for course_name, items in grouped.items():
            st.caption(course_name)
            for item in items:
                assignment_card(item, now, tz, compact=True)

    st.markdown("#### Weekly plan")
    st.caption("Gemma runs only when you generate or regenerate. Editing the steps does not call the model.")
    scope_name = _scope_name(scope)
    saved = db.latest_plan(start.isoformat(), scope_name)
    plan = saved[0] if saved else None
    edited = saved[1] if saved else False
    if plan and edited:
        st.caption("You edited this plan. Regenerate replaces your edits.")

    if settings.public_demo:
        st.info(
            "Gemma stays on your computer. This public host only shows the date-based order for the labeled demo week.",
            title="Planning is local",
        )
    elif st.button("Generate plan with Gemma", type="primary", disabled=not (board.overdue or board.this_week or board.undated or board.later)):
        with st.spinner(f"Asking {settings.ollama_model} locally…"):
            try:
                plan = make_plan(db, settings, scope, now)
            except (OllamaError, ModelOutputError) as exc:
                st.error(str(exc))
                plan = None
            else:
                st.success("Plan saved on this computer.")
        saved = db.latest_plan(start.isoformat(), scope_name)
        plan = saved[0] if saved else plan

    if plan is None:
        st.info("No plan is saved for this week yet. The list above is ordered by due date.")
        return
    _editor(db, plan, board, now, tz)


def _editor(db, plan: WeeklyPlan, board, now, tz) -> None:
    by_id = {item.id: item for item in board.overdue + board.this_week + board.later + board.undated + board.completed}
    st.info(plan.workload_summary, title="Gemma's summary (estimate)")
    if plan.missing_information:
        st.warning("\n".join(f"- {item}" for item in plan.missing_information), title="Missing or ambiguous information")
    updated_items: list[PlanItem] = []
    for item in plan.ordered_items():
        source = by_id.get(item.assignment_id)
        title = source.title if source else item.assignment_id
        label = "Model estimate" if item.model_generated else "Date-based fallback, not a model step"
        with st.expander(f"{item.order}. {title} · {item.priority} priority ({label})", expanded=item.order == min(i.order for i in plan.items)):
            if source:
                st.caption(f"Due date from the source record: {source.due_at.isoformat() if source.due_at else 'none'}")
                if item.priority == "high" and date_bucket(source, now, tz) == "later":
                    st.caption("Gemma marked this high. The source due date is after this week, so treat the priority as an estimate.")
            st.write(item.reason)
            steps = st.text_area(
                "Steps",
                value="\n".join(item.steps),
                key=f"steps-{plan.generated_at}-{item.assignment_id}",
                height=120,
            )
            updated_items.append(
                PlanItem(
                    assignment_id=item.assignment_id,
                    priority=item.priority,
                    reason=item.reason,
                    steps=[line.strip() for line in steps.splitlines() if line.strip()] or item.steps,
                    order=item.order,
                    model_generated=item.model_generated,
                )
            )
    sessions: list[StudySession] = []
    if plan.study_sessions:
        st.markdown("##### Suggested sessions")
        st.caption("Lengths are estimates.")
        for index, session in enumerate(plan.study_sessions):
            st.write(f"**{session.title}** · about {session.minutes} minutes")
            note = st.text_input(
                "Session note",
                value=session.note,
                key=f"session-{plan.generated_at}-{index}",
            )
            sessions.append(
                StudySession(
                    title=session.title,
                    minutes=session.minutes,
                    assignment_ids=session.assignment_ids,
                    note=note,
                )
            )
    if st.button("Save plan edits"):
        plan.items = updated_items
        plan.study_sessions = sessions or plan.study_sessions
        db.save_plan(plan, edited=True)
        st.success("Saved your edits locally.")
