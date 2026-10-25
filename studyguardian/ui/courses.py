"""Courses, Classroom materials, uploaded notes, and optional web search."""

from __future__ import annotations

import streamlit as st

from studyguardian.ai import ModelOutputError, OllamaError
from studyguardian.audio import DISCLOSURE
from studyguardian.documents import DocumentError
from studyguardian.search import SearchError
from studyguardian.services import find_resources, store_upload, study_insight
from studyguardian.ui.common import context, source_badge


def render() -> None:
    settings, db, tz, now, scope = context()
    st.markdown("## Courses and materials")
    st.caption("Classroom links are shown as they were synced. Uploaded notes stay on this computer.")
    courses = db.list_courses(scope)
    assignments = db.list_assignments(scope)
    if not courses:
        st.info("No courses yet. Load the demo week from the dashboard, or connect Classroom in Settings.")
        return
    course_names = {course.id: course.name for course in courses}
    course_id = st.selectbox(
        "Course",
        options=[course.id for course in courses],
        format_func=lambda item: course_names[item],
    )
    course = next(item for item in courses if item.id == course_id)
    source_badge(course.source)
    if course.link:
        st.link_button("Open course", course.link)

    course_assignments = [item for item in assignments if item.course_id == course_id]
    st.markdown("#### Assignments and their links")
    if not course_assignments:
        st.caption("This course has no stored assignments.")
    for assignment in course_assignments:
        with st.container(border=True):
            st.markdown(f"**{assignment.title}**")
            st.caption(assignment.description[:300] if assignment.description else "No description was provided.")
            if assignment.link:
                st.link_button("Open assignment", assignment.link, key=f"link-{assignment.id}")
            if assignment.materials:
                for material in assignment.materials:
                    st.markdown(f"- [{material.title}]({material.url}) · {material.kind}")
            else:
                st.caption("No linked materials were included with this assignment.")

    posted = db.course_materials(course_id)
    if posted:
        st.markdown("#### Other course materials")
        for material in posted:
            if material.get("url"):
                st.markdown(f"- [{material['title']}]({material['url']})")
            else:
                st.markdown(f"- {material['title']}")
            if material.get("description"):
                st.caption(material["description"][:240])

    st.markdown("#### Your notes")
    if settings.public_demo:
        st.info(
            "Uploads, note matching, web search, and audio are turned off here so a shared server never keeps private files.",
            title="Local only",
        )
        return
    uploaded = st.file_uploader("Upload a PDF or text note", type=["pdf", "txt", "md"])
    topic = st.text_input("Topic", placeholder="membranes, mitosis, primary sources")
    if st.button("Save note", disabled=uploaded is None):
        try:
            note_id = store_upload(
                db,
                settings,
                filename=uploaded.name,
                data=uploaded.getvalue(),
                course_id=course_id,
                topic=topic,
            )
        except DocumentError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved locally as note {note_id}. The same file is not copied twice.")

    notes = [note for note in db.list_notes() if note.course_id in {course_id, None}]
    course_notes = [note for note in notes if note.course_id == course_id]
    if not course_notes:
        st.caption("No notes are attached to this course yet.")
    else:
        st.caption("Attached notes: " + ", ".join(note.filename for note in course_notes))

    st.markdown("#### Find what in my notes matches an assignment")
    if course_assignments and course_notes:
        assignment_id = st.selectbox(
            "Assignment",
            options=[item.id for item in course_assignments],
            format_func=lambda item: next(row.title for row in course_assignments if row.id == item),
        )
        note_id = st.selectbox(
            "Note",
            options=[note.id for note in course_notes],
            format_func=lambda item: next(note.filename for note in course_notes if note.id == item),
        )
        if st.button("Find relevant sections"):
            with st.spinner("Reading the note locally…"):
                try:
                    insight = study_insight(db, settings, assignment_id, int(note_id))
                except (OllamaError, ModelOutputError, DocumentError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["insight"] = insight
        insight = st.session_state.get("insight")
        if insight:
            _show_insight(insight)
    else:
        st.caption("Add a note and keep at least one assignment to match them.")

    st.markdown("#### Study resource finder")
    st.caption("Optional live web search through SerpApi. Results are not the same as your uploaded notes.")
    query = st.text_input("Topic or concept", key="serp-query")
    if st.button("Search the web"):
        with st.spinner("Searching, then asking Gemma to order the real links…"):
            try:
                found = find_resources(settings, db, query)
            except SearchError as exc:
                st.error(str(exc))
            else:
                st.session_state["web_plan"] = found
    web_plan = st.session_state.get("web_plan")
    if web_plan:
        st.markdown("**Live web results**")
        if web_plan.get("overview"):
            st.write(web_plan["overview"])
        for step in web_plan.get("steps") or []:
            st.markdown(f"- [{step['title']}]({step['url']})")
            if step.get("snippet"):
                st.caption(step["snippet"])
            if step.get("why"):
                st.caption("Why it might help: " + step["why"])
        if web_plan.get("dropped_urls"):
            st.caption("Dropped links the model mentioned that were not in the search results.")
    saved = db.list_resources()
    if saved:
        with st.expander("Saved resources (available offline as titles and links)"):
            for item in saved:
                st.markdown(f"- [{item['title']}]({item['url']})")
                st.caption(item.get("snippet") or "")
    st.caption(DISCLOSURE + " Audio for a revision pack is on the Exam Prep page, and only after you ask.")


def _show_insight(insight) -> None:
    if insight.weak_match:
        st.caption("Keyword match was weak, so the closest opening pages were sent.")
    if insight.truncated:
        st.caption("Only some pages were sent: " + ", ".join(insight.pages_sent))
    if insight.insufficient:
        st.warning(insight.gaps or "The notes do not contain enough information.")
    st.markdown("**From your file**")
    if not insight.sections:
        st.caption("No grounded sections survived validation.")
    for section in insight.sections:
        with st.container(border=True):
            st.caption(f"From {section.filename}, {section.locator}")
            st.write(section.summary)
            if section.why_it_matters:
                st.caption(section.why_it_matters)
    for concept in insight.concepts:
        st.markdown(f"**{concept['term']}** — {concept['from_notes']}")
        st.caption(concept.get("filename", ""))
    if insight.relation_from_notes:
        st.write(insight.relation_from_notes)
    if insight.general_explanation:
        st.info(insight.general_explanation, title="General explanation, not a quotation from your file")
    for removed in insight.removed_citations:
        st.caption(removed)
