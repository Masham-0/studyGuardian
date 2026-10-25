"""Record a short walkthrough of the local StudyGuardian app.

Requires the app at http://127.0.0.1:8501 and Playwright's Chromium:

    pip install playwright
    python -m playwright install chromium
    python scripts/record_demo.py
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
RAW = OUT / "raw"


def pause(page, ms: int) -> None:
    page.wait_for_timeout(ms)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        launch = {"headless": True}
        chrome = os.environ.get("STUDYGUARDIAN_CHROME")
        if chrome:
            launch["executable_path"] = chrome
        browser = playwright.chromium.launch(**launch)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(RAW),
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8501/", wait_until="domcontentloaded")
        page.get_by_text("Do this next").wait_for(timeout=20000)
        pause(page, 10000)
        page.get_by_role("link", name="This week").click()
        page.get_by_text("Weekly plan").wait_for(timeout=20000)
        pause(page, 6000)
        page.get_by_text("Weekly plan").scroll_into_view_if_needed()
        pause(page, 8000)
        page.get_by_text("Model estimate").first.scroll_into_view_if_needed()
        pause(page, 10000)
        page.get_by_role("link", name="Courses and materials").click()
        page.get_by_text("OpenStax").first.wait_for(timeout=20000)
        pause(page, 8000)
        page.get_by_text("Your notes").scroll_into_view_if_needed()
        pause(page, 7000)
        page.get_by_role("link", name="Settings").click()
        page.get_by_role("button", name="Check Ollama").wait_for(timeout=20000)
        pause(page, 4000)
        page.get_by_role("button", name="Check Ollama").click()
        page.get_by_text("gemma3:4b is installed").wait_for(timeout=15000)
        pause(page, 8000)
        video = page.video
        context.close()
        browser.close()
        if video is not None:
            saved = Path(video.path())
            target = OUT / "demo.webm"
            if target.exists():
                target.unlink()
            saved.replace(target)
            print(target)


if __name__ == "__main__":
    main()
