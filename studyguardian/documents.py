"""Local document extraction. PDFs are read with PyMuPDF and never uploaded."""

from __future__ import annotations

from pathlib import Path

from studyguardian.models import PageText


class DocumentError(Exception):
    pass


def extract_pdf(path: Path) -> list[PageText]:
    try:
        import pymupdf
    except ImportError as exc:
        raise DocumentError("PyMuPDF is not installed. Run pip install -r requirements.txt.") from exc
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise DocumentError(f"Could not read {path.name} as a PDF. The file may be damaged.") from exc
    if document.is_encrypted and not document.authenticate(""):
        document.close()
        raise DocumentError(f"{path.name} is password-protected. StudyGuardian cannot read it.")
    pages: list[PageText] = []
    try:
        if document.page_count == 0:
            raise DocumentError(f"{path.name} has no pages.")
        for index, page in enumerate(document, start=1):
            text = page.get_text("text") or ""
            pages.append(PageText(number=index, text=text.strip(), locator=f"page {index}"))
    finally:
        document.close()
    if not any(page.text for page in pages):
        raise DocumentError(f"{path.name} has no extractable text. It may be a scanned image.")
    return pages


def extract_text_file(path: Path) -> list[PageText]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise DocumentError(f"Could not read {path.name}.") from exc
    if not text:
        raise DocumentError(f"{path.name} is empty.")
    return [PageText(number=1, text=text, locator="text file")]


def extract_document(path: Path) -> list[PageText]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in {".txt", ".md"}:
        return extract_text_file(path)
    raise DocumentError("Upload a PDF or a plain text file (.pdf, .txt, .md).")
