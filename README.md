# StudyGuardian

Your week, organized. Your exams, less stressful.

- **Hosted demo:** the Render service runs demo mode only. It shows the labeled sample week and does not accept Google login, uploads, web search, audio, or a connection to Ollama.
- Source: https://github.com/Dev-Nidhan/studyguardian
- Demo (about 75 seconds): https://github.com/Dev-Nidhan/studyguardian/blob/main/docs/demo.webm
- License: [MIT](LICENSE)

StudyGuardian is a local study planner for the Hacktoberfest 2026 Week 3 "Slow and Steady" challenge. It keeps Google Classroom coursework, uploaded notes, and study plans on your computer. Gemma, through Ollama, prioritizes work, finds relevant pages in your notes, and builds a revision pack. It does not turn assignments in, and it does not send coursework to a cloud model.

## What it answers

1. What coursework is due this week?
2. What should I work on first?
3. Where is the related material, in Classroom or in my notes?
4. How do I revise from the notes I already have?

Due dates, titles, links, and submission states come from Classroom or from the labeled demo set. Gemma's priorities, step lists, and session lengths are estimates. If StudyGuardian cannot tell whether you submitted something, the status stays **unknown**. It will not call that assignment incomplete.

## What stays local

| Data | Where it goes |
| --- | --- |
| Assignments, plans, preferences | SQLite in `data/studyguardian.db` |
| Uploaded notes | `data/notes/`, stored once per file hash |
| Google token | `data/google_token.json`, gitignored |
| Weekly plan, summaries, revision packs | Ollama on this machine (`gemma3:4b` by default) |
| Live web search | SerpApi, only when you click Search. Needs `SERPAPI_API_KEY` and internet |
| Spoken revision | ElevenLabs, only when you confirm a short passage. Needs `ELEVENLABS_API_KEY` and internet |

The first Classroom sync needs the internet. After that, cached assignments, saved plans, and notes open offline, as long as the app and (for a new plan) Ollama are installed. StudyGuardian cannot fetch new Classroom posts while you are offline.

There is no analytics, telemetry, remote database, or cloud inference. Streamlit's usage stats are turned off in `.streamlit/config.toml`.

## Setup

Python 3.11+ and [Ollama](https://ollama.com) are required. This project was developed on Python 3.14.

```bash
git clone https://github.com/Dev-Nidhan/studyguardian.git
cd studyguardian
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
ollama pull gemma3:4b
streamlit run app.py
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull gemma3:4b
streamlit run app.py
```

Open the URL Streamlit prints, usually `http://localhost:8501`.

### Demo mode

If Google credentials are empty, the app still starts. On the dashboard, choose **Load demo week**. Every synthetic course is named `Demo · …` and every synthetic assignment title starts with `Demo:`. The sidebar filter can show Classroom only, demo only, or both. Loading or removing the demo never deletes synced Classroom rows.

A sample note lives at `examples/cell-biology-notes.txt`. Upload it on **Courses and Materials** against the demo biology course, then use **Find relevant sections** or **Exam Prep**.

### Ollama

Default model is `gemma3:4b`. Host and model can be changed under Settings; those preferences are stored in SQLite, not in a prompt. Use **Check Ollama** rather than expecting a status call on every click.

If Ollama is stopped, the dashboard still shows the date-based queue. Generating a plan, a note match, or a revision pack shows an error and does not invent a model response. Saved plans remain readable.

Gemma runs only when you press Generate, Find relevant sections, Build revision pack, or Search the web. Streamlit reruns do not call the model again.

## Google Classroom

Create a Google Cloud project, enable the Classroom API, and create an **OAuth client of type Desktop**. A web client will fail with `redirect_uri_mismatch` because StudyGuardian uses a localhost redirect.

Put either of these in `.env` (see `.env.example`):

- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- or `GOOGLE_CLIENT_SECRETS_FILE` pointing at the downloaded JSON, which must stay out of git

Scopes, all read-only:

- `classroom.courses.readonly`
- `classroom.coursework.me.readonly`
- `classroom.courseworkmaterials.readonly`
- `classroom.student-submissions.me.readonly`

StudyGuardian does not request permission to create, change, grade, or submit coursework. Connect and Refresh are on **Settings**. Disconnect deletes the local token. Disconnect and revoke also calls Google's revoke endpoint when the network is available. Tokens are not written into prompts, logs, or the database of assignments.

While Google's app is in testing, add your own Google account as a test user. Classroom data for a school account can also be blocked by a Workspace admin (`admin_policy_enforced`). The screen shows that class of failure without printing the token.

Submission states from Classroom map like this:

| Classroom state | Shown as |
| --- | --- |
| Missing, or the submissions call failed | submission unknown |
| `NEW`, `CREATED` | not turned in |
| `RECLAIMED_BY_STUDENT` | reclaimed, not turned in |
| `TURNED_IN` | turned in |
| `RETURNED` | returned |

## Pages

- **Dashboard.** One next action, chosen by due date, then a short list. Counts for past due, this week, no date, and turned in.
- **This Week.** Assignments grouped by course, with overdue and undated work separated. Generate a plan, edit the steps, and save. Due dates on the plan are read back from the assignment row.
- **Courses and Materials.** Original links, uploaded PDF or text notes, a grounded "what in my notes matches" pass, and the optional web search.
- **Exam Prep.** Revision notes, definitions, flashcards, and practice questions cited to the file and page or text-file locator you provided. A separate box holds anything the model admits is not in the notes.
- **Settings.** Model, timezone, Classroom connection, demo data, and whether optional keys are present. Key values are not displayed.

Week boundaries are Monday 00:00 to the next Monday 00:00 in `STUDYGUARDIAN_TIMEZONE`. Classroom's `dueDate` and `dueTime` are interpreted as UTC, which is how the Classroom API publishes them. A date with no time is treated as 23:59:59 UTC so it is not overdue for the entire due date.

## PDFs and citations

PDF text is extracted locally with PyMuPDF. The same file hash is not copied twice. Password-protected PDFs and PDFs with no text layer (scans) produce an error instead of a guessed summary.

Before a note is sent to Gemma, StudyGuardian searches the extracted pages. Citations that name a page you did not provide are removed and listed. If the notes are too thin, the result says so.

Uploaded text and assignment descriptions are wrapped as data. The model is told to ignore instructions inside them.

## Optional partners

These are off unless you add a key and click the button.

**SerpApi.** Courses and Materials → Study resource finder. The app sends the topic you type, keeps the titles, URLs, and snippets SerpApi actually returned, prefers known educational hosts when sorting, and asks Gemma to order only those URLs. Invented URLs are dropped. Saved rows stay in SQLite so the titles and links are still listed offline. Opening a link still needs the internet. SerpApi is a paid search API; an empty key means the button explains that and does not call the network.

**ElevenLabs.** Exam Prep → Listen. You must check the disclosure box. Only the text in that box is sent, and passages over 2,500 characters are refused before any request. The mp3 is written under `data/audio/`. Missing keys and HTTP errors are shown on the page. The rest of the app works without audio.

**Not used, on purpose.** GitHub Copilot was not part of this build, so this project should not be entered for Best Use of GitHub Copilot. A `.tech` domain is not set up. The Render service is the public demo described above; it does not host Ollama or real Classroom accounts.

## Tests

No Google account, SerpApi key, or ElevenLabs key is required.

```bash
pytest
```

Covered: timezone week boundaries, missing due dates, priority, SQLite plans, demo/live separation, AI JSON validation and rejected citations, PDF extraction, offline cache when sync fails, and partner calls that must not touch the network without a key. The last local run was 41 passed.

## Prize categories this project is built for

- **Best Use of Render.** The public web service is a Streamlit demo of the labeled week. It listens on Render's `PORT`, uses the free instance, and sets `STUDYGUARDIAN_PUBLIC_DEMO=1` so OAuth secrets, private notes, and the local model are not exposed. Gemma still runs only when you start the app on your own computer. Free instances sleep after a period of inactivity, so the first open can take a minute.
- **Best Use of Gemma.** Gemma 3 4B through Ollama is the planner, the note matcher, and the exam-pack writer. Priorities are estimates. Due dates stay on the source record. Citations that name a page the file does not contain are removed.
- **Best Use of SerpApi.** Courses and Materials can search a topic and keep only URLs the search actually returned. This needs `SERPAPI_API_KEY`. The demo recording uses the local notes path.
- **Best Use of ElevenLabs.** Exam Prep can speak a passage the student selects, after a disclosure checkbox. This needs `ELEVENLABS_API_KEY`. Notes and plans work without it.

GitHub Copilot, Render, and a `.tech` domain are not part of this repository.

A live Gemma check is separate, because it needs Ollama and can take a minute:

```bash
python scripts/smoke_ollama.py
```

## Offline limits

- New Classroom coursework will not appear until a successful online refresh.
- A plan you already saved can be read with Ollama stopped. A new plan cannot.
- Web search and audio fail closed when the network or the key is missing. Saved search rows and local notes remain.
- Demo data is synthetic. Do not treat it as your homework.

## Project layout

```
app.py                      Streamlit entry
studyguardian/dates.py         UTC due times and local weeks
studyguardian/priority.py      Date-based queue
studyguardian/db.py            SQLite
studyguardian/classroom_client.py
studyguardian/ai.py            Ollama calls and validators
studyguardian/documents.py     PDF and text extraction
studyguardian/search.py        SerpApi
studyguardian/audio.py         ElevenLabs
studyguardian/services.py      Workflows the pages call
studyguardian/ui/              Dashboard, week, courses, exam, settings
tests/                      Fixtures are in-code. No live Google calls.
```

## License

MIT. See `LICENSE`.
