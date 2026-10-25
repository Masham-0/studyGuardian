"""Shared Streamlit pieces. Inference is never started from this module."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from studyguardian.config import load_settings
from studyguardian.dates import due_label, status_phrase
from studyguardian.db import Database
from studyguardian.models import Assignment
from studyguardian.services import effective, student_zone

CSS_LIGHT = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;600;700;900&display=swap');

:root {
  --ink: #0a0a0a;
  --muted: #555555;
  --paper: #f5f0e8;
  --card: #ffffff;
  --line: #0a0a0a;
  --accent: #ff3d00;
  --accent-bg: #ff3d0018;
  --sidebar-bg: #0a0a0a;
  --sidebar-fg: #f5f0e8;
  --overdue: #d50000;
  --success: #00c853;
  --ochre: #e65100;
  --demo: #7c4dff;
  --demo-bg: #ede7f6;
  --live-bg: #e8f5e9;
  --border-w: 3px;
  --font-mono: 'Space Mono', monospace;
  --font-sans: 'Inter', -apple-system, sans-serif;
  --note-bg: #fff9c4;
  --note-border: #0a0a0a;
  --source-bg: #e8f5e9;
  --general-bg: #f5f0e8;
  --general-border: #555555;
}
</style>
"""

CSS_DARK = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;600;700;900&display=swap');

:root {
  --ink: #e8e6e3;
  --muted: #9e9e9e;
  --paper: #121212;
  --card: #1e1e1e;
  --line: #e8e6e3;
  --accent: #ff6e40;
  --accent-bg: #ff6e4022;
  --sidebar-bg: #1a1a1a;
  --sidebar-fg: #e8e6e3;
  --overdue: #ff5252;
  --success: #69f0ae;
  --ochre: #ffab40;
  --demo: #b388ff;
  --demo-bg: #2d1f4e;
  --live-bg: #1b3a1b;
  --border-w: 3px;
  --font-mono: 'Space Mono', monospace;
  --font-sans: 'Inter', -apple-system, sans-serif;
  --note-bg: #2a2718;
  --note-border: #e8e6e3;
  --source-bg: #1b3a1b;
  --general-bg: #1e1e1e;
  --general-border: #9e9e9e;
}
</style>
"""

CSS_BASE = """
<style>
/* ── BRUTALIST GLOBAL ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], [data-testid="stMain"],
[data-testid="block-container"] {
  background: var(--paper) !important;
  color: var(--ink) !important;
  font-family: var(--font-sans) !important;
}
header[data-testid="stHeader"] {
  background: var(--paper) !important;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
  background: var(--sidebar-bg) !important;
  border-right: var(--border-w) solid var(--ink) !important;
}
section[data-testid="stSidebar"] * {
  color: var(--sidebar-fg) !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] {
  background: transparent !important;
}
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
  border: 2px solid var(--sidebar-fg) !important;
  border-radius: 0 !important;
}

/* ── TYPOGRAPHY ── */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-sans) !important;
  font-weight: 900 !important;
  letter-spacing: -0.03em !important;
  text-transform: uppercase !important;
}
h1 { border-bottom: 4px solid var(--accent) !important; display: inline-block; padding-bottom: 0.15em; }
.wordmark {
  font-size: 2rem;
  font-weight: 900;
  letter-spacing: -0.04em;
  text-transform: uppercase;
  margin-bottom: 0;
  border-bottom: 4px solid var(--accent);
  display: inline-block;
}
.tagline {
  color: var(--muted);
  margin-top: 0.3rem;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  text-transform: lowercase;
}
.kicker {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.7rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent);
  margin-bottom: 0.3rem;
  border-left: 4px solid var(--accent);
  padding-left: 0.5rem;
}
.next-title {
  font-size: 1.6rem;
  font-weight: 900;
  line-height: 1.2;
  text-transform: uppercase;
  letter-spacing: -0.02em;
}

/* ── BADGES ── */
.badge {
  display: inline-block;
  border-radius: 0 !important;
  padding: 0.15rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 700;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border: 2px solid var(--line);
}
.badge.demo { color: var(--demo); background: var(--demo-bg); border-color: var(--demo); }
.badge.live { color: var(--success); background: var(--live-bg); border-color: var(--success); }

/* ── DUE LABELS ── */
.due { font-weight: 700; font-family: var(--font-mono); font-size: 0.85rem; }
.due.overdue { color: var(--overdue); }
.due.soon { color: var(--success); }
.due.none { color: var(--ochre); }

/* ── CARDS & CONTAINERS ── */
[data-testid="stExpander"] {
  border: var(--border-w) solid var(--ink) !important;
  border-radius: 0 !important;
  background: var(--card) !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--font-mono) !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  font-size: 0.8rem !important;
  letter-spacing: 0.04em !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div:has(> div[data-testid="stVerticalBlock"]) {
  border: var(--border-w) solid var(--ink) !important;
  border-radius: 0 !important;
  background: var(--card) !important;
}

/* ── NOTE & BOXES ── */
.note {
  background: var(--note-bg);
  border: var(--border-w) solid var(--note-border);
  border-radius: 0;
  padding: 0.8rem 1rem;
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 0.85rem;
}
.source-box {
  background: var(--source-bg);
  border-left: 6px solid var(--success);
  border-top: 2px solid var(--success);
  border-bottom: 2px solid var(--success);
  padding: 0.7rem 0.9rem;
  margin: 0.5rem 0;
}
.general-box {
  background: var(--general-bg);
  border-left: 6px solid var(--general-border);
  border-top: 2px solid var(--general-border);
  border-bottom: 2px solid var(--general-border);
  padding: 0.7rem 0.9rem;
  margin: 0.5rem 0;
}

/* ── BUTTONS ── */
button[kind="primary"], .stButton > button[kind="primary"] {
  background: var(--accent) !important;
  color: #ffffff !important;
  border: var(--border-w) solid var(--ink) !important;
  border-radius: 0 !important;
  font-family: var(--font-mono) !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  transition: transform 80ms ease, box-shadow 80ms ease !important;
  box-shadow: 4px 4px 0 var(--ink) !important;
}
button[kind="primary"]:hover {
  transform: translate(-2px, -2px) !important;
  box-shadow: 6px 6px 0 var(--ink) !important;
}
button[kind="primary"]:active {
  transform: translate(2px, 2px) !important;
  box-shadow: 1px 1px 0 var(--ink) !important;
}
button[kind="secondary"], .stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
  background: var(--card) !important;
  color: var(--ink) !important;
  border: 2px solid var(--ink) !important;
  border-radius: 0 !important;
  font-family: var(--font-mono) !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.04em !important;
  box-shadow: 3px 3px 0 var(--ink) !important;
  transition: transform 80ms ease, box-shadow 80ms ease !important;
}
button[kind="secondary"]:hover, .stButton > button:not([kind]):hover {
  transform: translate(-1px, -1px) !important;
  box-shadow: 4px 4px 0 var(--ink) !important;
}
.stLinkButton a {
  border: 2px solid var(--ink) !important;
  border-radius: 0 !important;
  font-family: var(--font-mono) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.04em !important;
}

/* ── INPUTS ── */
input, textarea, [data-baseweb="select"],
[data-baseweb="input"], .stTextInput input,
.stTextArea textarea {
  border: 2px solid var(--ink) !important;
  border-radius: 0 !important;
  font-family: var(--font-mono) !important;
  background: var(--card) !important;
  color: var(--ink) !important;
}
input:focus, textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 3px 3px 0 var(--accent) !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
  border: var(--border-w) solid var(--ink) !important;
  padding: 0.8rem !important;
  background: var(--card) !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--font-mono) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  font-size: 0.7rem !important;
}
[data-testid="stMetricValue"] {
  font-weight: 900 !important;
  font-size: 2rem !important;
}

/* ── ALERTS ── */
[data-testid="stAlert"] {
  border-radius: 0 !important;
  border-width: var(--border-w) !important;
}

/* ── TABS & SEGMENTED CONTROLS ── */
[data-baseweb="tab-list"] {
  border-bottom: var(--border-w) solid var(--ink) !important;
}

/* ── THEME TOGGLE ── */
.theme-toggle-btn {
  position: fixed;
  top: 0.75rem;
  right: 1rem;
  z-index: 999999;
  width: 44px;
  height: 44px;
  border: 3px solid var(--ink);
  background: var(--card);
  color: var(--ink);
  font-size: 1.3rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 3px 3px 0 var(--ink);
  transition: transform 80ms ease, box-shadow 80ms ease;
  border-radius: 0;
  padding: 0;
  line-height: 1;
}
.theme-toggle-btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 var(--ink);
}
.theme-toggle-btn:active {
  transform: translate(2px, 2px);
  box-shadow: 1px 1px 0 var(--ink);
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 10px; }
::-webkit-scrollbar-track { background: var(--paper); }
::-webkit-scrollbar-thumb {
  background: var(--ink);
  border: 2px solid var(--paper);
}
</style>
"""

THEME_TOGGLE_JS = """
<script>
(function() {
  const KEY = 'studyguardian_theme';
  function getTheme() {
    return localStorage.getItem(KEY) || 'light';
  }
  function applyTheme(theme) {
    // Remove existing theme style
    const old = document.getElementById('sg-theme-vars');
    if (old) old.remove();

    const style = document.createElement('style');
    style.id = 'sg-theme-vars';

    if (theme === 'dark') {
      style.textContent = `
        :root {
          --ink: #e8e6e3;
          --muted: #9e9e9e;
          --paper: #121212;
          --card: #1e1e1e;
          --line: #e8e6e3;
          --accent: #ff6e40;
          --accent-bg: #ff6e4022;
          --sidebar-bg: #1a1a1a;
          --sidebar-fg: #e8e6e3;
          --overdue: #ff5252;
          --success: #69f0ae;
          --ochre: #ffab40;
          --demo: #b388ff;
          --demo-bg: #2d1f4e;
          --live-bg: #1b3a1b;
          --note-bg: #2a2718;
          --note-border: #e8e6e3;
          --source-bg: #1b3a1b;
          --general-bg: #1e1e1e;
          --general-border: #9e9e9e;
        }
      `;
    } else {
      style.textContent = `
        :root {
          --ink: #0a0a0a;
          --muted: #555555;
          --paper: #f5f0e8;
          --card: #ffffff;
          --line: #0a0a0a;
          --accent: #ff3d00;
          --accent-bg: #ff3d0018;
          --sidebar-bg: #0a0a0a;
          --sidebar-fg: #f5f0e8;
          --overdue: #d50000;
          --success: #00c853;
          --ochre: #e65100;
          --demo: #7c4dff;
          --demo-bg: #ede7f6;
          --live-bg: #e8f5e9;
          --note-bg: #fff9c4;
          --note-border: #0a0a0a;
          --source-bg: #e8f5e9;
          --general-bg: #f5f0e8;
          --general-border: #555555;
        }
      `;
    }
    document.head.appendChild(style);
    localStorage.setItem(KEY, theme);

    // Update toggle button icon
    const btn = document.getElementById('sg-theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀' : '●';
  }

  // Apply saved theme immediately
  applyTheme(getTheme());

  // Create toggle button if it doesn't exist
  function ensureToggle() {
    if (document.getElementById('sg-theme-toggle')) return;
    const btn = document.createElement('button');
    btn.id = 'sg-theme-toggle';
    btn.className = 'theme-toggle-btn';
    btn.title = 'Toggle dark / light';
    btn.textContent = getTheme() === 'dark' ? '☀' : '●';
    btn.onclick = function() {
      const next = getTheme() === 'dark' ? 'light' : 'dark';
      applyTheme(next);
    };
    document.body.appendChild(btn);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureToggle);
  } else {
    ensureToggle();
  }
  // Also retry after Streamlit re-renders
  const observer = new MutationObserver(ensureToggle);
  observer.observe(document.body, { childList: true, subtree: false });
})();
</script>
"""


def _css_for_theme() -> str:
    """Return the combined CSS. Theme switching is handled client-side by JS."""
    return CSS_LIGHT + CSS_BASE + THEME_TOGGLE_JS


def inject() -> None:
    st.markdown(_css_for_theme(), unsafe_allow_html=True)


@st.cache_resource
def get_db() -> Database:
    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return Database(settings.db_path)


def context():
    db = get_db()
    settings = effective(load_settings(), db)
    tz = student_zone(settings)
    now = datetime.now(tz)
    source = st.session_state.get("source_filter") or "all"
    scope = source if source in {"live", "demo"} else None
    return settings, db, tz, now, scope


def go(page: str) -> None:
    st.switch_page(page)


def source_badge(source: str) -> None:
    if source == "demo":
        st.badge("Demo data", color="violet")
    else:
        st.badge("Classroom", color="green")


def due_line(assignment: Assignment, now: datetime, tz) -> None:
    label = due_label(assignment, now, tz)
    if assignment.due_at is None:
        st.markdown(f":orange[{label}]")
    elif "Past due" in label:
        st.markdown(f":red[{label}]")
    else:
        st.markdown(f":green[{label}]")


def status_line(assignment: Assignment) -> str:
    return "Submission status: " + status_phrase(assignment.submission_status)


def assignment_card(assignment: Assignment, now: datetime, tz, *, compact: bool = False) -> None:
    with st.container(border=True):
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f"**{assignment.title}**")
            st.caption(assignment.course_name)
        with right:
            source_badge(assignment.source)
        due_line(assignment, now, tz)
        st.caption(status_line(assignment))
        if assignment.description and not compact:
            st.write(assignment.description[:500])
        if assignment.link:
            st.link_button("Open original", assignment.link)
        elif assignment.source == "demo":
            st.caption("Demo records have no Classroom link.")
        if assignment.materials:
            st.caption("Linked materials")
            for material in assignment.materials:
                st.markdown(f"- [{material.title}]({material.url})")
