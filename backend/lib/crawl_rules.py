"""Deterministic crawl-frontier rules and URL classification helpers.

Pure functions only — no Playwright/LLM dependencies — so the crawl behaviour
that decides *what gets scraped* is unit-testable and identical across runs.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

LOGOUT_RE = re.compile(r"\b(log[-_]?out|sign[-_]?out)\b", re.I)

LOGIN_PATH_RE = re.compile(r"login|signin|sign-in|authenticate", re.I)

ERROR_PAGE_RE = re.compile(
    r"\b(404|502|503|500|bad gateway|not found|service unavailable|gateway timeout)\b",
    re.I,
)

# Path segments that are almost certainly record ids, not distinct page shapes:
# pure numbers, UUIDs, long hex blobs, and mongo-style object ids.
_ID_SEGMENT_RE = re.compile(
    r"^(\d+"
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|[0-9a-f]{16,}"
    r")$",
    re.I,
)


def url_template(url: str) -> str:
    """Collapse id-like path segments so /case/123 and /case/456 share a template."""
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    templated = ["{id}" if _ID_SEGMENT_RE.match(s) else s.lower() for s in segments]
    return f"{parsed.netloc.lower()}/{'/'.join(templated)}"


def is_logout_url(url: str) -> bool:
    return bool(LOGOUT_RE.search(urlparse(url).path))


def select_crawl_urls(
    candidates: list[str],
    seen_templates: set[str],
    visited: set[str],
) -> list[str]:
    """Pick the next URLs to crawl: rule-based, sorted, pattern-deduplicated.

    Mutates ``seen_templates`` with the templates of selected URLs so repeated
    calls keep collapsing /item/{id}-style duplicates across the whole crawl.
    """
    selected: list[str] = []
    for url in sorted(set(candidates)):
        if url in visited:
            continue
        if is_logout_url(url):
            continue
        template = url_template(url)
        if template in seen_templates:
            continue
        seen_templates.add(template)
        selected.append(url)
    return selected


def looks_like_login_redirect(requested_url: str, final_url: str) -> bool:
    """True when a page request was bounced to a login route (=> protected)."""
    if not final_url:
        return False
    req = urlparse(requested_url)
    fin = urlparse(final_url)
    if (req.netloc, req.path.rstrip("/")) == (fin.netloc, fin.path.rstrip("/")):
        return False
    return bool(LOGIN_PATH_RE.search(fin.path)) and not LOGIN_PATH_RE.search(req.path)


def is_http_error_status(status: int | None) -> bool:
    """True for HTTP responses that should not be scraped as app pages."""
    return status is not None and status >= 400


def looks_like_error_page(
    title: str,
    page_text: str,
    http_status: int | None = None,
) -> bool:
    """Detect 404/502-style pages even when status is missing or masked."""
    if is_http_error_status(http_status):
        return True
    haystack = f"{title}\n{(page_text or '')[:800]}".lower()
    return bool(ERROR_PAGE_RE.search(haystack))


def stable_element_id(label: str, selector_key: str, fallback: str = "el") -> str:
    """Deterministic element id: label slug + short hash of the selector.

    Unlike index-based ids, this stays identical across runs as long as the
    element keeps its label and position, so merged contracts and testcases
    that reference element_ids do not churn.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")[:40] or fallback
    digest = hashlib.sha1((selector_key or label or fallback).encode("utf-8")).hexdigest()[:6]
    return f"{slug}_{digest}"
