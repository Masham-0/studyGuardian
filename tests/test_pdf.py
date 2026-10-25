from pathlib import Path

import pymupdf
import pytest

from studyguardian.documents import DocumentError, extract_document, extract_pdf
from studyguardian.db import Database


def _pdf(path: Path, lines: list[str]) -> None:
    document = pymupdf.open()
    for line in lines:
        page = document.new_page()
        page.insert_text((72, 72), line)
    document.save(path)
    document.close()


def test_pdf_extraction_keeps_page_numbers(tmp_path):
    path = tmp_path / "notes.pdf"
    _pdf(path, ["Osmosis is the diffusion of water.", "Mitosis separates sister chromatids."])
    pages = extract_pdf(path)
    assert [page.number for page in pages] == [1, 2]
    assert pages[0].locator == "page 1"
    assert "Osmosis" in pages[0].text
    assert "Mitosis" in pages[1].text


def test_invalid_pdf_raises(tmp_path):
    path = tmp_path / "notes.pdf"
    path.write_bytes(b"this is not a pdf")
    with pytest.raises(DocumentError):
        extract_pdf(path)


def test_empty_text_pdf_raises(tmp_path):
    path = tmp_path / "blank.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()
    with pytest.raises(DocumentError):
        extract_pdf(path)


def test_text_file_and_duplicate_upload(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Turgor pressure keeps a plant cell firm.\n", encoding="utf-8")
    pages = extract_document(path)
    assert pages[0].locator == "text file"
    db = Database(tmp_path / "notes.db")
    data = path.read_bytes()
    from studyguardian.config import Settings
    from studyguardian.services import store_upload

    settings = Settings(
        ollama_host="http://127.0.0.1:11434",
        ollama_model="gemma3:4b",
        timezone="UTC",
        data_dir=tmp_path / "data",
        google_client_id=None,
        google_client_secret=None,
        google_secrets_file=None,
        serpapi_key=None,
        elevenlabs_key=None,
        elevenlabs_voice="voice",
    )
    first = store_upload(db, settings, filename="notes.txt", data=data, course_id=None, topic="cells")
    second = store_upload(db, settings, filename="notes.txt", data=data, course_id=None, topic="cells")
    assert first == second
    stored = list((tmp_path / "data" / "notes").glob("*.txt"))
    assert len(stored) == 1
    hits = db.search_pages(first, "turgor")
    assert hits and "Turgor" in hits[0].text
