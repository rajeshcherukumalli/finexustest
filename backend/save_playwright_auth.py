#!/usr/bin/env python3
"""Log in via scraper auth and save Playwright storage state for E2E tests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# backend/ on path when run as script
_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))

from lib.scraper_credentials import default_login_url, load_scraper_credentials  # noqa: E402
from lib.scraper_auth import authenticate_at_url  # noqa: E402
from scraper import WebScraper  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Save Playwright storage state after scraper login")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write authenticated_user.json (storage state)",
    )
    parser.add_argument("--login-url", help="Override QA_LOGIN_URL")
    parser.add_argument("--base-url", help="App base URL (default: login URL origin or QA_LOGIN_URL)")
    parser.add_argument("--headed", action="store_true", help="Show browser while logging in")
    args = parser.parse_args()

    load_dotenv(_BACKEND.parent / ".env")
    load_dotenv()

    creds = load_scraper_credentials()
    login_url = args.login_url or default_login_url(creds, "") or creds.get("QA_LOGIN_URL")
    if not login_url:
        print("Set QA_LOGIN_URL in qa-automation/.env", file=sys.stderr)
        return 1

    base_url = args.base_url or login_url.rsplit("/login", 1)[0] or login_url
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    scraper = WebScraper(
        base_url=base_url,
        login_url=login_url,
        credentials=creds,
        max_pages=1,
        headed=args.headed,
        interact=False,
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context = browser.new_context()
        page = context.new_page()
        ok = authenticate_at_url(scraper, page, login_url)
        if not ok:
            print("Login failed — check QA_USERNAME/QA_PASSWORD or OTP creds in .env", file=sys.stderr)
            browser.close()
            return 1
        context.storage_state(path=str(out))
        print(f"Saved storage state → {out}")
        print(f"Logged in at: {page.url}")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
