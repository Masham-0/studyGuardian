"""Environment configuration. Secrets stay in the environment, not the database."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    ollama_host: str
    ollama_model: str
    timezone: str
    data_dir: Path
    google_client_id: str | None
    google_client_secret: str | None
    google_secrets_file: Path | None
    serpapi_key: str | None
    elevenlabs_key: str | None
    elevenlabs_voice: str
    public_demo: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studyguardian.db"

    @property
    def notes_dir(self) -> Path:
        return self.data_dir / "notes"

    @property
    def token_path(self) -> Path:
        return self.data_dir / "google_token.json"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def google_configured(self) -> bool:
        if self.public_demo:
            return False
        if self.google_secrets_file and self.google_secrets_file.exists():
            return True
        return bool(self.google_client_id and self.google_client_secret)


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or (ROOT / ".env"), override=False)
    data_dir = Path(os.getenv("STUDYGUARDIAN_DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = (ROOT / data_dir).resolve()
    secrets = _blank(os.getenv("GOOGLE_CLIENT_SECRETS_FILE"))
    secrets_path = None
    if secrets:
        candidate = Path(secrets)
        secrets_path = candidate if candidate.is_absolute() else (ROOT / candidate).resolve()
    public_demo = os.getenv("STUDYGUARDIAN_PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes"}
    client_id = _blank(os.getenv("GOOGLE_CLIENT_ID"))
    client_secret = _blank(os.getenv("GOOGLE_CLIENT_SECRET"))
    serpapi_key = _blank(os.getenv("SERPAPI_API_KEY"))
    elevenlabs_key = _blank(os.getenv("ELEVENLABS_API_KEY"))
    if public_demo:
        client_id = None
        client_secret = None
        secrets_path = None
        serpapi_key = None
        elevenlabs_key = None
    return Settings(
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        timezone=os.getenv("STUDYGUARDIAN_TIMEZONE", "local"),
        data_dir=data_dir,
        google_client_id=client_id,
        google_client_secret=client_secret,
        google_secrets_file=secrets_path,
        serpapi_key=serpapi_key,
        elevenlabs_key=elevenlabs_key,
        elevenlabs_voice=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
        public_demo=public_demo,
    )


def with_preferences(settings: Settings, prefs: dict[str, str]) -> Settings:
    """Non-secret preferences stored in SQLite override host, model, and timezone."""

    updates = {}
    if prefs.get("ollama_host"):
        updates["ollama_host"] = prefs["ollama_host"].rstrip("/")
    if prefs.get("ollama_model"):
        updates["ollama_model"] = prefs["ollama_model"]
    if prefs.get("timezone"):
        updates["timezone"] = prefs["timezone"]
    return replace(settings, **updates) if updates else settings
