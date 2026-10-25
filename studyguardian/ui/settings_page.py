"""Connection, model, timezone, and demo controls."""

from __future__ import annotations

import streamlit as st

from studyguardian.classroom_client import ClassroomError, GoogleClassroomClient
from studyguardian.services import load_demo, sync_classroom
from studyguardian.ui.common import context


ZONES = [
    "local",
    "Asia/Kolkata",
    "UTC",
    "America/Los_Angeles",
    "America/New_York",
    "Europe/London",
    "Asia/Singapore",
    "Australia/Sydney",
]


def render() -> None:
    settings, db, tz, now, _scope = context()
    st.markdown("## Settings")
    if settings.public_demo:
        st.info(
            "Classroom sign-in, Ollama, SerpApi, and ElevenLabs are disabled on this server. "
            "Clone the repository to use them on your own computer. The demo week below is synthetic.",
            title="Public demo",
        )
        if st.button("Reload demo week"):
            count = load_demo(db, now, tz)
            st.success(f"Stored {count} labeled demo assignments.")
        return
    st.markdown("#### This computer")
    st.write(
        "The first Classroom sync needs the internet. After that, cached assignments, "
        "saved plans, and uploaded notes open without a connection. "
        "A new sync cannot fetch new Classroom posts while you are offline. "
        "Planning and note reading use Ollama on this machine. "
        "SerpApi search and ElevenLabs audio are the only optional calls that leave the computer, and both wait for a button."
    )

    model_ok = st.session_state.get("ollama_status")
    if st.button("Check Ollama"):
        from studyguardian.ai import OllamaClient

        ok, message = OllamaClient(settings.ollama_host, settings.ollama_model).status()
        st.session_state["ollama_status"] = (ok, message)
        model_ok = st.session_state["ollama_status"]
    if model_ok:
        (st.success if model_ok[0] else st.warning)(model_ok[1])
    else:
        st.caption(f"Model setting: {settings.ollama_model} at {settings.ollama_host}. Check when you want; this page does not call it automatically.")

    host = st.text_input("Ollama host", value=settings.ollama_host)
    model = st.text_input("Ollama model", value=settings.ollama_model)
    timezone = st.selectbox(
        "Timezone for this week",
        options=ZONES,
        index=ZONES.index(settings.timezone) if settings.timezone in ZONES else 0,
    )
    if st.button("Save local preferences"):
        db.set_preference("ollama_host", host.strip())
        db.set_preference("ollama_model", model.strip())
        db.set_preference("timezone", timezone)
        st.success("Saved. API keys stay in .env and were not written to the database.")

    st.markdown("#### Google Classroom")
    client = GoogleClassroomClient(settings)
    st.write(client.connection_label())
    if not settings.google_configured:
        st.info("No OAuth client is configured. The app still runs in demo mode. See .env.example.")
    last = db.last_live_sync()
    if last:
        st.caption(f"Last cached Classroom sync: {last} UTC.")
    if st.button("Connect Classroom", disabled=not settings.google_configured):
        try:
            st.success(client.connect())
        except ClassroomError as exc:
            st.error(str(exc))
    columns = st.columns(2)
    if columns[0].button("Refresh from Classroom", disabled=not client.token_exists):
        with st.spinner("Reading courses. This needs the internet…"):
            result = sync_classroom(db, client)
        if result.ok:
            st.success(result.message)
        elif result.from_cache:
            st.error(result.message + " Showing the last saved assignments.")
        else:
            st.error(result.message)
    if columns[1].button("Disconnect", disabled=not client.token_exists):
        st.info(client.disconnect(revoke=False))
    if st.button("Disconnect and revoke at Google", disabled=not client.token_exists):
        st.info(client.disconnect(revoke=True))

    st.markdown("#### Demo data")
    st.caption("Demo courses are labeled and stored apart from Classroom rows. Loading the demo does not delete a sync.")
    if st.button("Load demo week"):
        count = load_demo(db, now, tz)
        st.success(f"Stored {count} labeled demo assignments.")
    if st.button("Remove demo assignments"):
        removed = db.clear_demo()
        st.success(f"Removed {removed} demo assignments. Classroom rows and uploaded notes were kept.")

    st.markdown("#### Optional keys")
    st.write("SerpApi: " + ("configured" if settings.serpapi_key else "not set"))
    st.write("ElevenLabs: " + ("configured" if settings.elevenlabs_key else "not set"))
    st.caption("Keys are read from the environment. They are not shown here and are not sent to Gemma.")
