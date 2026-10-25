"""Optional ElevenLabs speech. Audio is generated only when a caller passes text."""

from __future__ import annotations

from pathlib import Path

import requests

MAX_CHARS = 2500
DISCLOSURE = (
    "The text you select is sent to ElevenLabs to create audio. "
    "StudyGuardian does not send your Classroom courses or other notes unless you select that text."
)


class AudioError(Exception):
    pass


def speech_request(text: str, voice_id: str) -> dict:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise AudioError("Select some revision text before generating audio.")
    if len(cleaned) > MAX_CHARS:
        raise AudioError(
            f"That passage is {len(cleaned)} characters. Select under {MAX_CHARS} characters. "
            "StudyGuardian will not send a whole course."
        )
    return {
        "url": f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        "json": {"text": cleaned, "model_id": "eleven_multilingual_v2"},
    }


def synthesize(
    text: str,
    api_key: str | None,
    voice_id: str,
    destination: Path,
    session: requests.Session | None = None,
) -> Path:
    if not api_key:
        raise AudioError(
            "ElevenLabs is not configured. Add ELEVENLABS_API_KEY to .env. "
            "Revision notes, flashcards, and plans work without audio."
        )
    request = speech_request(text, voice_id)
    http = session or requests.Session()
    try:
        response = http.post(
            request["url"],
            headers={"xi-api-key": api_key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
            json=request["json"],
            timeout=60,
        )
    except requests.RequestException as exc:
        raise AudioError("Audio generation needs an internet connection. Your notes were not changed.") from exc
    if response.status_code in {401, 403}:
        raise AudioError("ElevenLabs rejected the API key. Notes are still available to read.")
    if response.status_code == 429:
        raise AudioError("ElevenLabs rate-limited this request. Wait and try a shorter passage.")
    if response.status_code >= 400:
        raise AudioError(f"ElevenLabs returned HTTP {response.status_code}. No audio was saved.")
    if not response.content:
        raise AudioError("ElevenLabs returned an empty audio file.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return destination
