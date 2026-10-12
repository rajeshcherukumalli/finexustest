"""Unit tests for contract merge + diff (re-scrapes must be monotonic)."""

from __future__ import annotations

import unittest

from lib.contract_merge import element_key, merge_contracts, render_diff_markdown


def _element(label: str, css: str) -> dict:
    return {
        "element_id": f"{label.lower().replace(' ', '_')}_abc123",
        "label": label,
        "selectors": {"playwright": "", "css": css, "xpath": ""},
    }


def _contract(pages: list[dict], scraped_at: str = "2026-06-01T00:00:00Z") -> dict:
    return {
        "contract_version": "1.2.0",
        "application": {"name": "t", "base_url": "https://app.com"},
        "extraction_metadata": {"scraped_at": scraped_at},
        "route_index": [],
        "home_navigation": [],
        "pages": pages,
    }


def _page(page_id: str, elements: list[dict]) -> dict:
    return {
        "page_id": page_id,
        "path": f"/{page_id}",
        "url": f"https://app.com/{page_id}",
        "title": page_id,
        "page_type": "unknown",
        "test_priority": "medium",
        "is_protected": False,
        "elements": elements,
        "forms": [],
    }


class TestMergeContracts(unittest.TestCase):
    def test_new_page_added(self):
        previous = _contract([_page("home", [_element("Home", "#home")])])
        current = _contract(
            [_page("home", [_element("Home", "#home")]), _page("about", [])],
            scraped_at="2026-06-02T00:00:00Z",
        )
        merged, diff = merge_contracts(previous, current)
        self.assertEqual(diff["pages_added"], ["about"])
        self.assertEqual(len(merged["pages"]), 2)

    def test_missing_page_kept_as_stale(self):
        previous = _contract([
            _page("home", []),
            _page("faq", [_element("Q1", "#q1")]),
        ])
        current = _contract([_page("home", [])], scraped_at="2026-06-02T00:00:00Z")
        merged, diff = merge_contracts(previous, current)
        self.assertEqual(diff["pages_stale"], ["faq"])
        faq = next(p for p in merged["pages"] if p["page_id"] == "faq")
        self.assertTrue(faq["stale"])
        self.assertEqual(faq["last_seen"], "2026-06-01T00:00:00Z")
        # stale page still has its elements
        self.assertEqual(len(faq["elements"]), 1)

    def test_missing_element_kept_as_stale(self):
        previous = _contract([
            _page("home", [_element("Login", "#login"), _element("Help", "#help")])
        ])
        current = _contract(
            [_page("home", [_element("Login", "#login")])],
            scraped_at="2026-06-02T00:00:00Z",
        )
        merged, diff = merge_contracts(previous, current)
        home = merged["pages"][0]
        labels = {e["label"]: e for e in home["elements"]}
        self.assertIn("Help", labels)
        self.assertTrue(labels["Help"]["stale"])
        self.assertFalse(labels["Login"].get("stale", False))
        self.assertEqual(diff["elements_stale"]["home"], ["Help"])

    def test_new_element_reported_added(self):
        previous = _contract([_page("home", [_element("Login", "#login")])])
        current = _contract(
            [_page("home", [_element("Login", "#login"), _element("Search", "#search")])],
            scraped_at="2026-06-02T00:00:00Z",
        )
        _merged, diff = merge_contracts(previous, current)
        self.assertEqual(diff["elements_added"]["home"], ["Search"])

    def test_merge_is_idempotent(self):
        previous = _contract([_page("home", [_element("Login", "#login")])])
        current = _contract(
            [_page("home", [_element("Login", "#login")])],
            scraped_at="2026-06-02T00:00:00Z",
        )
        merged, diff = merge_contracts(previous, current)
        self.assertEqual(len(merged["pages"][0]["elements"]), 1)
        self.assertEqual(diff["elements_added"], {})
        self.assertEqual(diff["elements_stale"], {})

    def test_element_id_collision_with_stale_suffixed(self):
        old = _element("Login", "#old-login")
        new = _element("Login", "#new-login")  # same element_id, different selector
        previous = _contract([_page("home", [old])])
        current = _contract([_page("home", [new])], scraped_at="2026-06-02T00:00:00Z")
        merged, _diff = merge_contracts(previous, current)
        ids = [e["element_id"] for e in merged["pages"][0]["elements"]]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate element ids: {ids}")

    def test_partial_merge_does_not_stale_unvisited_pages(self):
        previous = _contract([_page("home", []), _page("faq", [])])
        current = _contract(
            [_page("dashboard", [])], scraped_at="2026-06-02T00:00:00Z"
        )
        merged, diff = merge_contracts(previous, current, mark_missing_pages_stale=False)
        self.assertEqual(diff["pages_stale"], [])
        by_id = {p["page_id"]: p for p in merged["pages"]}
        self.assertEqual(set(by_id), {"home", "faq", "dashboard"})
        self.assertFalse(by_id["home"].get("stale", False))
        self.assertFalse(by_id["faq"].get("stale", False))

    def test_route_index_rebuilt_with_stale_flag(self):
        previous = _contract([_page("home", []), _page("faq", [])])
        current = _contract([_page("home", [])], scraped_at="2026-06-02T00:00:00Z")
        merged, _diff = merge_contracts(previous, current)
        faq_route = next(r for r in merged["route_index"] if r["page_id"] == "faq")
        self.assertTrue(faq_route.get("stale"))

    def test_element_key_prefers_playwright_selector(self):
        el = {
            "element_id": "x",
            "selectors": {"playwright": "page.getByTestId('a')", "css": "#a", "xpath": "/a"},
        }
        self.assertEqual(element_key(el), "page.getByTestId('a')")


class TestDiffMarkdown(unittest.TestCase):
    def test_renders_sections(self):
        previous = _contract([_page("home", [_element("Help", "#help")]), _page("faq", [])])
        current = _contract(
            [_page("home", [_element("Login", "#login")]), _page("about", [])],
            scraped_at="2026-06-02T00:00:00Z",
        )
        _merged, diff = merge_contracts(previous, current)
        md = render_diff_markdown(diff)
        self.assertIn("Pages added (1)", md)
        self.assertIn("- about", md)
        self.assertIn("- faq", md)
        self.assertIn("+ Login", md)
        self.assertIn("− Help (stale)", md)


if __name__ == "__main__":
    unittest.main()
