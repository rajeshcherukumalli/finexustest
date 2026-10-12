"""Tests for SPA button route discovery and navigation scope helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from lib.scraper_navigation import (
    ButtonProbeCandidate,
    classify_link,
    discover_button_routes,
    is_blocked_host,
    is_in_crawl_scope,
    is_safe_to_probe_button,
    url_change_kind,
)
from scraper import WebScraper, _link_from_dict


def _is_static_asset(url: str) -> bool:
    return url.lower().endswith(".pdf")


BASE_DOMAIN = "app.test"


class TestUrlChangeKind(unittest.TestCase):
    def test_none_when_unchanged(self):
        url = "https://app.test/home"
        self.assertEqual(url_change_kind(url, url), "none")

    def test_hash_only(self):
        before = "https://app.test/home"
        after = "https://app.test/home#services"
        self.assertEqual(url_change_kind(before, after), "hash_only")

    def test_pathname_change(self):
        before = "https://app.test/home"
        after = "https://app.test/dashboard"
        self.assertEqual(url_change_kind(before, after), "pathname")


class TestCrawlScope(unittest.TestCase):
    def test_blocks_youtube(self):
        self.assertTrue(is_blocked_host("www.youtube.com"))
        self.assertFalse(
            is_in_crawl_scope(
                "https://www.youtube.com/watch?v=1",
                BASE_DOMAIN,
                _is_static_asset,
            )
        )

    def test_blocks_pdf(self):
        self.assertFalse(
            is_in_crawl_scope(
                f"https://{BASE_DOMAIN}/file.pdf",
                BASE_DOMAIN,
                _is_static_asset,
            )
        )

    def test_allows_same_domain_path(self):
        self.assertTrue(
            is_in_crawl_scope(
                f"https://{BASE_DOMAIN}/ui/citizen/home",
                BASE_DOMAIN,
                _is_static_asset,
            )
        )

    def test_classify_link_external(self):
        category, crawlable = classify_link(
            "https://drive.google.com/file",
            "https://drive.google.com/file",
            BASE_DOMAIN,
            _is_static_asset,
        )
        self.assertEqual(category, "external")
        self.assertFalse(crawlable)


class TestButtonDenylist(unittest.TestCase):
    def test_skips_logout(self):
        self.assertFalse(
            is_safe_to_probe_button({"text": "Logout", "aria_label": None, "in_form": False})
        )

    def test_skips_form_buttons(self):
        self.assertFalse(
            is_safe_to_probe_button({"text": "Continue", "aria_label": None, "in_form": True})
        )

    def test_allows_neutral_nav(self):
        self.assertTrue(
            is_safe_to_probe_button({"text": "Dashboard", "aria_label": None, "in_form": False})
        )


class TestDiscoverButtonRoutes(unittest.TestCase):
    def test_pathname_click_produces_spa_route(self):
        page = MagicMock()
        page.url = "https://app.test/home"

        def click_side_effect(*_args, **_kwargs):
            page.url = "https://app.test/cases"

        locator = MagicMock()
        locator.first.click.side_effect = click_side_effect
        page.locator.return_value = locator

        candidate = ButtonProbeCandidate(
            selector="#cases-btn",
            text="Cases",
            aria_label=None,
            tag="button",
            region="nav",
            in_form=False,
        )
        with patch(
            "lib.scraper_navigation.extract_live_navigation",
            return_value=([], [candidate]),
        ):
            routes = discover_button_routes(
                page,
                "https://app.test/home",
                base_domain=BASE_DOMAIN,
                normalise_url=lambda u: u.rstrip("/"),
                is_static_asset=_is_static_asset,
                delay=0,
                probe_limit=5,
                navigation_timeout_ms=5000,
            )

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["category"], "spa_route")
        self.assertTrue(routes[0]["crawlable"])
        self.assertEqual(routes[0]["href"], "https://app.test/cases")

    def test_hash_only_not_crawlable(self):
        page = MagicMock()
        page.url = "https://app.test/home"

        def click_side_effect(*_args, **_kwargs):
            page.url = "https://app.test/home#faq"

        locator = MagicMock()
        locator.first.click.side_effect = click_side_effect
        page.locator.return_value = locator

        candidate = ButtonProbeCandidate(
            selector="#faq",
            text="FAQ",
            aria_label=None,
            tag="button",
            region="content",
            in_form=False,
        )
        with patch(
            "lib.scraper_navigation.extract_live_navigation",
            return_value=([], [candidate]),
        ):
            routes = discover_button_routes(
                page,
                "https://app.test/home",
                base_domain=BASE_DOMAIN,
                normalise_url=lambda u: u.split("#")[0].rstrip("/"),
                is_static_asset=_is_static_asset,
                delay=0,
                probe_limit=5,
                navigation_timeout_ms=5000,
            )

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["category"], "internal_hash")
        self.assertFalse(routes[0]["crawlable"])


class TestWebScraperButtonRoutes(unittest.TestCase):
    def test_skips_probe_on_login_when_unauthenticated(self):
        scraper = WebScraper("https://app.test", credentials={})
        scraper.authenticated = False
        page = MagicMock()
        with patch("scraper.discover_button_routes") as inner:
            result = scraper._discover_button_routes(page, "https://app.test/login")
            inner.assert_not_called()
        self.assertEqual(result, [])


class TestLinkFromDict(unittest.TestCase):
    def test_spa_route(self):
        link = _link_from_dict(
            {
                "href": "https://app.test/cases",
                "raw_href": "https://app.test/cases",
                "text": "Cases",
                "tag": "button",
                "category": "spa_route",
                "crawlable": True,
                "region": "nav",
            }
        )
        self.assertEqual(link.category, "spa_route")
        self.assertTrue(link.crawlable)


if __name__ == "__main__":
    unittest.main()
