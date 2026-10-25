"""Dashboard. The next dated task stays in front of the rest of the week."""

from __future__ import annotations

import streamlit as st

from studyguardian.services import dashboard, timezone_label
from studyguardian.ui.common import assignment_card, context


def render() -> None:
    settings, db, tz, now, scope = context()
    board = dashboard(db, scope, now, tz)
    st.title("StudyGuardian")
    st.caption("Your week, organized. Your exams, less stressful.")
    if not (board.overdue or board.this_week or board.later or board.undated or board.completed):
        st.info(
            "Load a labeled demo week, or connect Classroom in Settings.",
            title="No assignments are stored yet",
        )
        left, right = st.columns(2)
        if left.button("Load demo week", type="primary", width="stretch"):
            from studyguardian.services import load_demo

            load_demo(db, now, tz)
            st.rerun()
        if right.button("Open settings", width="stretch"):
            st.switch_page("settings")
        return

    st.caption(board.summary)
    action = board.next_action
    if action is None:
        st.success("Everything stored here is already turned in or returned.")
    else:
        st.caption("Do this next")
        assignment_card(action, now, tz)
        columns = st.columns(2)
        if columns[0].button("Plan around this", type="primary", width="stretch"):
            st.session_state["focus_id"] = action.id
            st.switch_page("week")
        if action.link:
            columns[1].link_button("Open original", action.link, width="stretch")

    metrics = st.columns(4)
    metrics[0].metric("Past due", len(board.overdue))
    metrics[1].metric("Due this week", len(board.this_week))
    metrics[2].metric("No date", len(board.undated))
    metrics[3].metric("Turned in", len(board.completed))

    st.markdown("#### Also this week")
    shown = (board.overdue + board.this_week)[:4]
    shown = [item for item in shown if action is None or item.id != action.id]
    if not shown:
        st.caption("Nothing else is due this week.")
    for item in shown:
        assignment_card(item, now, tz, compact=True)
    if board.undated:
        st.caption(f"{len(board.undated)} assignment(s) have no due date, so they stay off the front of the queue.")
    st.caption(
        f"Times use {timezone_label(tz)}. Priorities from Gemma are estimates and stay on This Week until you ask for a plan."
    )
