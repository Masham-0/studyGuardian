"""Optional SerpApi study search. Live calls need the internet. Saved rows work offline."""

from __future__ import annotations

from urllib.parse import urlparse

import requests

from studyguardian.models import WebResource

REPUTABLE_HOSTS = (
    ".edu",
    "khanacademy.org",
    "wikipedia.org",
    "openstax.org",
    "nih.gov",
    "nasa.gov",
    "docs.python.org",
    "developer.mozilla.org",
    "mit.edu",
    "stanford.edu",
    "coursera.org",
    "edx.org",
    "oclc.org",
    "britannica.com",
    "nature.com",
    "sciencedirect.com",
)


class SearchError(Exception):
    pass


def is_reputable(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == hint or host.endswith(hint) for hint in REPUTABLE_HOSTS)


def parse_serp(payload: dict) -> list[WebResource]:
    if not isinstance(payload, dict):
        raise SearchError("SerpApi returned an unexpected payload.")
    if payload.get("error"):
        raise SearchError(str(payload["error"]))
    resources: list[WebResource] = []
    seen: set[str] = set()
    for item in payload.get("organic_results") or []:
        if not isinstance(item, dict):
            continue
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title or url in seen:
            continue
        seen.add(url)
        resources.append(
            WebResource(
                title=title,
                url=url,
                snippet=(item.get("snippet") or "").strip(),
                reputable=is_reputable(url),
            )
        )
    resources.sort(key=lambda item: (0 if item.reputable else 1, item.title.casefold()))
    return resources[:8]


def search_learning_resources(query: str, api_key: str | None, session: requests.Session | None = None) -> list[WebResource]:
    cleaned = " ".join((query or "").split())
    if len(cleaned) < 3:
        raise SearchError("Enter a topic or concept of at least a few words.")
    if not api_key:
        raise SearchError(
            "SerpApi is not configured. Add SERPAPI_API_KEY to .env to search the web. "
            "Uploaded notes and saved resources still work offline."
        )
    http = session or requests.Session()
    try:
        response = http.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": cleaned, "api_key": api_key, "num": 8},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise SearchError("Live search needs an internet connection. Saved resources are unchanged.") from exc
    if response.status_code in {401, 403}:
        raise SearchError("SerpApi rejected the API key. Check SERPAPI_API_KEY.")
    if response.status_code == 429:
        raise SearchError("SerpApi rate-limited this search. Wait and try again. Saved resources are unchanged.")
    if response.status_code >= 400:
        raise SearchError(f"SerpApi returned HTTP {response.status_code}. Saved resources are unchanged.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SearchError("SerpApi returned a response that was not JSON.") from exc
    return parse_serp(payload)
