"""Unit tests for the deterministic crawl-frontier rules."""

from __future__ import annotations

import unittest

from lib.crawl_rules import (
    is_http_error_status,
    is_logout_url,
    looks_like_error_page,
    looks_like_login_redirect,
    select_crawl_urls,
    stable_element_id,
    url_template,
)


class TestUrlTemplate(unittest.TestCase):
    def test_collapses_numeric_ids(self):
        self.assertEqual(
            url_template("https://app.com/case/123"),
            url_template("https://app.com/case/456"),
        )

    def test_collapses_uuids_and_hex(self):
        self.assertEqual(
            url_template("https://app.com/order/550e8400-e29b-41d4-a716-446655440000"),
            url_template("https://app.com/order/00000000-0000-0000-0000-000000000001"),
        )
        self.assertEqual(
            url_template("https://app.com/doc/a1b2c3d4e5f6a7b8c9d0"),
            url_template("https://app.com/doc/ffffffffffffffffffff"),
        )

    def test_distinct_pages_keep_distinct_templates(self):
        self.assertNotEqual(
            url_template("https://app.com/about"),
            url_template("https://app.com/contact"),
        )


class TestSelectCrawlUrls(unittest.TestCase):
    def test_deterministic_sorted_and_deduped(self):
        candidates = [
            "https://app.com/case/2",
            "https://app.com/about",
            "https://app.com/case/1",
            "https://app.com/logout",
        ]
        seen: set[str] = set()
        first = select_crawl_urls(candidates, seen, set())
        # sorted, one case/{id} representative, no logout
        self.assertEqual(first, ["https://app.com/about", "https://app.com/case/1"])

        # identical input again → nothing new (templates already seen)
        again = select_crawl_urls(candidates, seen, set(first))
        self.assertEqual(again, [])

    def test_skips_visited(self):
        seen: set[str] = set()
        out = select_crawl_urls(
            ["https://app.com/about"], seen, {"https://app.com/about"}
        )
        self.assertEqual(out, [])

    def test_logout_variants_excluded(self):
        self.assertTrue(is_logout_url("https://app.com/auth/logout"))
        self.assertTrue(is_logout_url("https://app.com/sign-out"))
        self.assertFalse(is_logout_url("https://app.com/signup"))


class TestLoginRedirect(unittest.TestCase):
    def test_redirect_to_login_detected(self):
        self.assertTrue(looks_like_login_redirect(
            "https://app.com/dashboard",
            "https://app.com/ui/citizen/dristi/home/login",
        ))

    def test_same_url_not_protected(self):
        self.assertFalse(looks_like_login_redirect(
            "https://app.com/about", "https://app.com/about"
        ))

    def test_login_page_itself_not_flagged(self):
        # navigating to /login and staying there is not a protection signal
        self.assertFalse(looks_like_login_redirect(
            "https://app.com/login", "https://app.com/login"
        ))
        # nor is a login page redirecting within login routes
        self.assertFalse(looks_like_login_redirect(
            "https://app.com/login", "https://app.com/login/otp"
        ))

    def test_ordinary_redirect_not_flagged(self):
        self.assertFalse(looks_like_login_redirect(
            "https://app.com/home", "https://app.com/welcome"
        ))


class TestErrorPages(unittest.TestCase):
    def test_http_status_errors(self):
        self.assertTrue(is_http_error_status(404))
        self.assertTrue(is_http_error_status(502))
        self.assertFalse(is_http_error_status(200))
        self.assertFalse(is_http_error_status(None))

    def test_error_page_content(self):
        self.assertTrue(looks_like_error_page("502 Bad Gateway", "nginx error"))
        self.assertTrue(looks_like_error_page("Not Found", "404 page"))
        self.assertFalse(looks_like_error_page("Home", "Welcome to FPA dashboard"))


class TestStableElementId(unittest.TestCase):
    def test_same_inputs_same_id(self):
        a = stable_element_id("Sign In", "body > div > button:nth-of-type(2)")
        b = stable_element_id("Sign In", "body > div > button:nth-of-type(2)")
        self.assertEqual(a, b)

    def test_different_selectors_different_ids(self):
        a = stable_element_id("Sign In", "body > div > button:nth-of-type(1)")
        b = stable_element_id("Sign In", "body > div > button:nth-of-type(2)")
        self.assertNotEqual(a, b)

    def test_unlabeled_element_still_gets_id(self):
        eid = stable_element_id("", "#icon-btn", fallback="button")
        self.assertTrue(eid.startswith("button_"))


if __name__ == "__main__":
    unittest.main()
