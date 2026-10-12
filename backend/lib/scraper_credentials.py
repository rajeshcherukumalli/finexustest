"""Load scraper authentication settings from environment variables."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

AUTH_ENV_KEYS = (
    "QA_LOGIN_URL",
    "QA_USERNAME",
    "QA_PASSWORD",
    "QA_BASE_URL",
    "QA_TEST_MOBILE",
    "QA_TEST_OTP",
)

FILLABLE_KEYS = ("QA_USERNAME", "QA_PASSWORD", "QA_TEST_MOBILE", "QA_TEST_OTP")

DEFAULT_NAVIGATION_TIMEOUT_MS = 60_000
DEFAULT_BUTTON_PROBE_LIMIT = 30


def button_probe_limit() -> int:
    """Max no-href button clicks per page during scrape (QA_BUTTON_PROBE_LIMIT)."""
    raw = os.getenv("QA_BUTTON_PROBE_LIMIT", str(DEFAULT_BUTTON_PROBE_LIMIT)).strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_BUTTON_PROBE_LIMIT


def navigation_timeout_ms() -> int:
    """Playwright page.goto / load-state timeout (override via QA_NAVIGATION_TIMEOUT_MS)."""
    raw = os.getenv("QA_NAVIGATION_TIMEOUT_MS", str(DEFAULT_NAVIGATION_TIMEOUT_MS)).strip()
    try:
        return max(5_000, int(raw))
    except ValueError:
        return DEFAULT_NAVIGATION_TIMEOUT_MS


def load_scraper_credentials() -> dict[str, str]:
    """Return non-empty auth-related env vars (dotenv should be loaded by caller)."""
    creds = {key: value for key in AUTH_ENV_KEYS if (value := os.getenv(key, "").strip())}
    if creds:
        log.info("Scraper auth env keys present: %s", ", ".join(sorted(creds)))
    return creds


def has_auth_credentials(creds: dict[str, str]) -> bool:
    """True when at least one fillable credential value is available."""
    return any(creds.get(key) for key in FILLABLE_KEYS)


def available_fillable_keys(creds: dict[str, str]) -> list[str]:
    return [key for key in FILLABLE_KEYS if creds.get(key)]


def default_login_url(creds: dict[str, str], base_url: str) -> str | None:
    """Canonical login page for this scrape target (QA_LOGIN_URL only; never guessed)."""
    _ = base_url
    return creds.get("QA_LOGIN_URL") or None


def resolve_auth_url(creds: dict[str, str], base_url: str, discovered_url: str) -> str:
    """Prefer QA_LOGIN_URL so credentials are always applied on the configured login page."""
    return default_login_url(creds, base_url) or discovered_url


def merge_legacy_cli_credentials(
    creds: dict[str, str],
    *,
    login_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, str]:
    """CLI flags override env for backward-compatible scraper invocation."""
    merged = dict(creds)
    if login_url:
        merged["QA_LOGIN_URL"] = login_url
    if username:
        merged["QA_USERNAME"] = username
    if password:
        merged["QA_PASSWORD"] = password
    return merged
