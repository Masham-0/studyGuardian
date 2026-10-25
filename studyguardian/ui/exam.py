"""Exam packs grounded in selected notes, with optional spoken audio."""

from __future__ import annotations

import streamlit as st

from studyguardian.ai import ModelOutputError, OllamaError
from studyguardian.audio import DISCLOSURE, AudioError
from studyguardian.services import exam_pack, speak_revision
from studyguardian.ui.common import context


def render() -> None:
    settings, db, _tz, _now, scope = context()
    st.markdown("## Exam prep")
    st.caption("Revision notes, flashcards, and questions are generated locally from the notes you select.")
    if settings.public_demo:
        st.info(
            "Revision packs and spoken audio run on your computer. This public host does not call Gemma or ElevenLabs.",
            title="Exam prep is local",
        )
        return
    courses = db.list_courses(scope)
    if not courses:
        st.info("Add a course by loading the demo week or syncing Classroom.")
        return
    course_id = st.selectbox(
        "Course",
        options=[course.id for course in courses],
        format_func=lambda item: next(course.name for course in courses if course.id == item),
    )
    notes = [note for note in db.list_notes() if note.course_id == course_id]
    if not notes:
        st.info("Upload notes on Courses and Materials first. Exam prep will not invent a textbook.")
        return
    selected = st.multiselect(
        "Notes to use",
        options=[note.id for note in notes],
        default=[notes[0].id],
        format_func=lambda item: next(note.filename for note in notes if note.id == item),
    )
    if st.button("Build revision pack", type="primary", disabled=not selected):
        with st.spinner(f"Asking {settings.ollama_model} to stay inside your notes…"):
            try:
                pack = exam_pack(db, settings, [int(item) for item in selected], course_id)
            except (OllamaError, ModelOutputError) as exc:
                st.error(str(exc))
            else:
                st.session_state["exam_pack"] = pack
    pack = st.session_state.get("exam_pack")
    if pack is None:
        return
    st.caption("Sources: " + ", ".join(pack.source_labels) if pack.source_labels else "No sources.")
    if pack.insufficient:
        st.warning("These notes do not contain enough information for a complete pack.")
    for gap in pack.gaps:
        st.caption("Gap: " + gap)
    for removed in pack.removed_citations:
        st.caption(removed)

    st.markdown("#### Revision notes")
    if not pack.revision_notes:
        st.caption("No grounded revision notes were returned.")
    revision_text = []
    for note in pack.revision_notes:
        st.markdown(f"**{note['heading']}**")
        for bullet in note["bullets"]:
            st.write(f"- {bullet}")
            revision_text.append(bullet)
        st.caption("From " + "; ".join(note.get("sources") or []))

    if pack.concepts:
        st.markdown("#### Concepts")
        for concept in pack.concepts:
            st.markdown(f"**{concept['term']}**")
            st.write(concept["definition"])
            st.caption("From " + "; ".join(concept.get("sources") or []))

    if pack.flashcards:
        st.markdown("#### Flashcards")
        for index, card in enumerate(pack.flashcards, start=1):
            with st.expander(f"Card {index}: {card['front']}"):
                st.write(card["back"])
                st.caption("From " + "; ".join(card.get("sources") or []))

    if pack.questions:
        st.markdown("#### Practice")
        for index, question in enumerate(pack.questions, start=1):
            with st.expander(f"Question {index}"):
                st.write(question["question"])
                st.markdown("**Answer**")
                st.write(question["answer"])
                st.markdown("**Why**")
                st.write(question["explanation"])
                st.caption("From " + "; ".join(question.get("sources") or []))

    if pack.outside_the_notes:
        st.info(pack.outside_the_notes, title="Not from your notes")

    st.markdown("#### Listen")
    st.info(DISCLOSURE, title="Audio leaves this computer")
    passage = st.text_area(
        "Text to read aloud",
        value="\n".join(revision_text[:8]),
        height=140,
        help="Only this box is sent, and only after you confirm.",
    )
    agree = st.checkbox("I understand this text will be sent to ElevenLabs.")
    if st.button("Create audio", disabled=not agree):
        try:
            path = speak_revision(settings, passage)
        except AudioError as exc:
            st.error(str(exc))
        else:
            st.audio(str(path))
            st.caption(f"Saved locally at {path.name}.")
