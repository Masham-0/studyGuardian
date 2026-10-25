"""Read-only Google Classroom client.

Scopes list courses, published coursework, course materials, and the student's
own submission state. Nothing here creates, edits, grades, or turns in work.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from studyguardian.config import Settings
from studyguardian.dates import classroom_due_to_utc
from studyguardian.models import Assignment, Course, Material

# Narrowest student-readable Classroom scopes for this product.
READONLY_SCOPES = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
)

_SUBMISSION_STATES = {
    "NEW": "new",
    "CREATED": "created",
    "TURNED_IN": "turned_in",
    "RETURNED": "returned",
    "RECLAIMED_BY_STUDENT": "reclaimed_by_student",
}

_RANK = {
    "returned": 5,
    "turned_in": 4,
    "reclaimed_by_student": 3,
    "created": 2,
    "new": 1,
    "unknown": 0,
}


class ClassroomError(Exception):
    pass


class ClassroomNotConfigured(ClassroomError):
    pass


class ClassroomNetworkError(ClassroomError):
    pass


class ClassroomAPIError(ClassroomError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class SyncResult:
    ok: bool
    message: str
    course_count: int = 0
    assignment_count: int = 0
    from_cache: bool = False


def explain_status(status: int | None) -> str:
    if status == 401:
        return "Classroom rejected the saved login. Disconnect and connect again."
    if status == 403:
        return (
            "Classroom refused this read. Enable the Classroom API in Google Cloud, "
            "and use a Google account that is enrolled in the course. "
            "StudyGuardian only requests read access."
        )
    if status == 404:
        return "Classroom could not find that course."
    if status is None:
        return "Classroom could not be reached. An internet connection is required to sync. Cached assignments are unchanged."
    return f"Classroom returned an error ({status}). Cached assignments are unchanged."


def client_config_from_settings(settings: Settings) -> dict | None:
    if settings.google_secrets_file and settings.google_secrets_file.exists():
        try:
            return json.loads(settings.google_secrets_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ClassroomNotConfigured(
                "The Google client secrets file could not be read. Check GOOGLE_CLIENT_SECRETS_FILE."
            ) from exc
    if settings.google_client_id and settings.google_client_secret:
        return {
            "installed": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
    return None


def map_submission_state(value: str | None) -> str:
    if not value:
        return "unknown"
    return _SUBMISSION_STATES.get(value, "unknown")


def best_submission(states: list[str]) -> str:
    if not states:
        return "unknown"
    mapped = [map_submission_state(state) for state in states]
    return max(mapped, key=lambda item: _RANK.get(item, 0))


def materials_from_payload(items: list | None) -> list[Material]:
    materials: list[Material] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if "link" in item and isinstance(item["link"], dict):
            url = (item["link"].get("url") or "").strip()
            title = (item["link"].get("title") or url).strip()
            if url:
                materials.append(Material(title=title, url=url, kind="link"))
        elif "driveFile" in item and isinstance(item["driveFile"], dict):
            drive = item["driveFile"].get("driveFile") or {}
            url = (drive.get("alternateLink") or "").strip()
            title = (drive.get("title") or "Drive file").strip()
            if url:
                materials.append(Material(title=title, url=url, kind="drive"))
        elif "youtubeVideo" in item and isinstance(item["youtubeVideo"], dict):
            video = item["youtubeVideo"]
            url = (video.get("alternateLink") or "").strip()
            title = (video.get("title") or "YouTube video").strip()
            if url:
                materials.append(Material(title=title, url=url, kind="youtube"))
        elif "form" in item and isinstance(item["form"], dict):
            form = item["form"]
            url = (form.get("formUrl") or "").strip()
            title = (form.get("title") or "Form").strip()
            if url:
                materials.append(Material(title=title, url=url, kind="form"))
    return materials


def assignment_from_coursework(
    course: Course,
    work: dict,
    submission_status: str,
) -> Assignment | None:
    if work.get("state") not in (None, "PUBLISHED"):
        return None
    work_id = work.get("id")
    title = (work.get("title") or "").strip()
    if not work_id or not title:
        return None
    return Assignment(
        id=f"classroom:{course.id}:{work_id}",
        course_id=course.id,
        course_name=course.name,
        title=title,
        description=work.get("description") or "",
        due_at=classroom_due_to_utc(work.get("dueDate"), work.get("dueTime")),
        link=work.get("alternateLink"),
        submission_status=submission_status or "unknown",
        source="live",
        materials=materials_from_payload(work.get("materials")),
        course_section=course.section,
    )


def course_from_payload(payload: dict) -> Course | None:
    if payload.get("courseState") not in (None, "ACTIVE"):
        return None
    course_id = payload.get("id")
    name = (payload.get("name") or "").strip()
    if not course_id or not name:
        return None
    return Course(
        id=str(course_id),
        name=name,
        section=payload.get("section"),
        source="live",
        link=payload.get("alternateLink"),
    )


def material_rows(course_id: str, payload: dict) -> dict | None:
    if payload.get("state") not in (None, "PUBLISHED"):
        return None
    material_id = payload.get("id")
    title = (payload.get("title") or "").strip()
    if not material_id or not title:
        return None
    links = materials_from_payload(payload.get("materials"))
    first = links[0] if links else None
    return {
        "id": f"classroom-material:{course_id}:{material_id}",
        "title": title,
        "description": payload.get("description") or "",
        "url": first.url if first else payload.get("alternateLink"),
        "kind": first.kind if first else "material",
    }


def drain_pages(fetch_page, item_key: str) -> list:
    """Follow nextPageToken. Stops if a token repeats."""

    items: list = []
    token = None
    seen: set[str] = set()
    while True:
        page = fetch_page(token) or {}
        items.extend(page.get(item_key) or [])
        token = page.get("nextPageToken")
        if not token or token in seen:
            break
        seen.add(token)
    return items


def _save_token(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class GoogleClassroomClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def token_exists(self) -> bool:
        return self.settings.token_path.exists()

    def connection_label(self) -> str:
        if not self.settings.google_configured:
            return "Google OAuth is not configured. Demo mode is available."
        if not self.token_exists:
            return "Not connected. Classroom sync is optional."
        return "Connected. Tokens stay in the local data folder."

    def connect(self) -> str:
        config = client_config_from_settings(self.settings)
        if config is None:
            raise ClassroomNotConfigured(
                "Add a Desktop OAuth client to .env, or keep using demo mode. "
                "StudyGuardian does not need Google to show the dashboard."
            )
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise ClassroomNotConfigured("Google auth libraries are not installed.") from exc
        flow = InstalledAppFlow.from_client_config(config, list(READONLY_SCOPES))
        credentials = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent",
            open_browser=True,
        )
        _save_token(self.settings.token_path, credentials.to_json())
        return "Connected. StudyGuardian can now read courses and coursework. It cannot turn work in."

    def disconnect(self, revoke: bool = False) -> str:
        token = None
        path = self.settings.token_path
        if path.exists():
            try:
                token = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                token = None
            path.unlink(missing_ok=True)
        if not revoke:
            return "Removed the saved Google login from this computer."
        refresh = None
        if isinstance(token, dict):
            refresh = token.get("refresh_token") or token.get("token")
        if not refresh:
            return "Removed the local login. There was no token left to revoke at Google."
        try:
            import requests

            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": refresh},
                headers={"content-type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
        except Exception:
            return "Removed the local login. Revoking it at Google needs an internet connection, so that step did not finish."
        if response.status_code == 200:
            return "Removed the local login and revoked it at Google."
        return "Removed the local login. Google did not confirm revocation. You can also remove StudyGuardian from your Google Account permissions."

    def _credentials(self):
        if not self.token_exists:
            raise ClassroomNotConfigured("Connect Google Classroom before syncing.")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise ClassroomNotConfigured("Google auth libraries are not installed.") from exc
        try:
            credentials = Credentials.from_authorized_user_file(str(self.settings.token_path), list(READONLY_SCOPES))
        except (OSError, ValueError) as exc:
            raise ClassroomAPIError(
                "The saved Google login could not be read. Disconnect and connect again."
            ) from exc
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as exc:
                raise ClassroomAPIError(
                    "The saved Google login could not be refreshed. Disconnect and connect again.",
                    status=401,
                ) from exc
            _save_token(self.settings.token_path, credentials.to_json())
        return credentials

    def _service(self):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ClassroomNotConfigured("The Google API client is not installed.") from exc
        return build("classroom", "v1", credentials=self._credentials(), cache_discovery=False)

    def _execute(self, request):
        try:
            from googleapiclient.errors import HttpError
        except ImportError:
            HttpError = ()  # type: ignore
        try:
            return request.execute()
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            try:
                status = int(status) if status is not None else None
            except (TypeError, ValueError):
                status = None
            raise ClassroomAPIError(explain_status(status), status=status) from exc
        except Exception as exc:
            name = exc.__class__.__name__
            if "Timeout" in name or "Connection" in name or "Transport" in name:
                raise ClassroomNetworkError(explain_status(None)) from exc
            raise ClassroomAPIError("Classroom request failed. Cached assignments are unchanged.") from exc

    def fetch(self) -> tuple[list[tuple[Course, list[Assignment], list[dict]]], list[str]]:
        """Return normalized courses and a list of non-fatal warnings."""

        service = self._service()
        warnings: list[str] = []
        try:
            course_payloads = drain_pages(
                lambda token: self._execute(
                    service.courses().list(pageSize=100, pageToken=token, courseStates=["ACTIVE"])
                ),
                "courses",
            )
        except ClassroomError:
            raise
        except Exception as exc:
            raise ClassroomNetworkError(explain_status(None)) from exc

        synced: list[tuple[Course, list[Assignment], list[dict]]] = []
        for payload in course_payloads:
            course = course_from_payload(payload)
            if course is None:
                continue
            try:
                work_items = drain_pages(
                    lambda token, course_id=course.id: self._execute(
                        service.courses().courseWork().list(
                            courseId=course_id,
                            pageSize=100,
                            pageToken=token,
                            courseWorkStates=["PUBLISHED"],
                            orderBy="dueDate asc",
                        )
                    ),
                    "courseWork",
                )
            except ClassroomError as exc:
                warnings.append(f"{course.name}: {exc}")
                continue
            submission_by_work: dict[str, list[str]] | None
            try:
                submissions = drain_pages(
                    lambda token, course_id=course.id: self._execute(
                        service.courses().courseWork().studentSubmissions().list(
                            courseId=course_id,
                            courseWorkId="-",
                            pageSize=100,
                            pageToken=token,
                        )
                    ),
                    "studentSubmissions",
                )
                submission_by_work = {}
                for submission in submissions:
                    work_id = str(submission.get("courseWorkId") or "")
                    submission_by_work.setdefault(work_id, []).append(submission.get("state") or "")
            except ClassroomError:
                submission_by_work = None
                warnings.append(
                    f"{course.name}: submission status is unknown because Classroom did not return your submissions."
                )
            assignments: list[Assignment] = []
            for work in work_items:
                work_id = str(work.get("id") or "")
                if submission_by_work is None:
                    status = "unknown"
                else:
                    status = best_submission(submission_by_work.get(work_id, []))
                assignment = assignment_from_coursework(course, work, status)
                if assignment:
                    assignments.append(assignment)
            material_items: list[dict] = []
            try:
                raw_materials = drain_pages(
                    lambda token, course_id=course.id: self._execute(
                        service.courses().courseWorkMaterials().list(
                            courseId=course_id,
                            pageSize=100,
                            pageToken=token,
                            courseWorkMaterialStates=["PUBLISHED"],
                        )
                    ),
                    "courseWorkMaterial",
                )
                for raw in raw_materials:
                    row = material_rows(course.id, raw)
                    if row:
                        material_items.append(row)
            except ClassroomError as exc:
                warnings.append(f"{course.name} materials: {exc}")
            synced.append((course, assignments, material_items))
        return synced, warnings
