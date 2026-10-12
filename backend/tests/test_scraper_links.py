"""Unit tests for scraper link normalization and home_navigation."""

from __future__ import annotations

import unittest

from scraper import (
    _assert_spec_for_link,
    _build_playwright_selector,
    _fragment_from_href,
    _normalize_href_for_storage,
    _target_path_from_href,
    build_home_navigation,
)
from lib.contract import Contract, load_contract
from pathlib import Path
import json
import tempfile


class TestHrefNormalization(unittest.TestCase):
    base = "https://dfsqa.beehyv.com"

    def test_normalize_preserves_hash_fragment(self):
        resolved = "https://dfsqa.beehyv.com/#help-support"
        raw = "/#help-support"
        self.assertEqual(
            _normalize_href_for_storage(resolved, raw),
            "https://dfsqa.beehyv.com/#help-support",
        )

    def test_target_path_for_hash_link(self):
        href = "https://dfsqa.beehyv.com/#help-support"
        path = _target_path_from_href(
            href,
            self.base,
            raw_href="/#help-support",
            category="internal_hash",
        )
        self.assertEqual(path, "/#help-support")

    def test_target_path_for_internal_path(self):
        href = "https://dfsqa.beehyv.com/sitemap"
        path = _target_path_from_href(href, self.base, raw_href="/sitemap", category="internal_path")
        self.assertEqual(path, "/sitemap")

    def test_fragment_from_raw_href(self):
        self.assertEqual(
            _fragment_from_href("", "/#help-support"),
            "help-support",
        )

    def test_assert_spec_hash(self):
        spec = _assert_spec_for_link("/#help-support", "/#help-support", "internal_hash")
        self.assertEqual(spec, {"kind": "hash", "value": "#help-support"})

    def test_assert_spec_pathname(self):
        spec = _assert_spec_for_link("/sitemap", "/sitemap", "internal_path")
        self.assertEqual(spec, {"kind": "pathname", "value": "/sitemap"})


class TestPlaywrightSelector(unittest.TestCase):
    def test_prefers_href_locator_for_links(self):
        sel = _build_playwright_selector(
            "a", "link", "Help", None, None, None, None, raw_href="/#help-support"
        )
        self.assertIn("a[href=\"/#help-support\"]", sel)

    def test_role_fallback_uses_exact(self):
        sel = _build_playwright_selector("button", "button", "Submit", None, None, None, None)
        self.assertIn("exact: true", sel)


class TestHomeNavigation(unittest.TestCase):
    def test_filters_header_footer_nav_only(self):
        elements = [
            {
                "element_id": "skip_1",
                "role": "link",
                "label": "Skip to Content",
                "raw_href": "#main",
                "target_path": "/#main",
                "category": "internal_hash",
                "region": "header",
            },
            {
                "element_id": "site_map_1",
                "role": "link",
                "label": "Site Map",
                "raw_href": "/sitemap",
                "target_path": "/sitemap",
                "category": "navigation",
                "region": "footer",
            },
            {
                "element_id": "mandi_1",
                "role": "link",
                "label": "Mandi",
                "raw_href": "/mandi",
                "target_path": "/mandi",
                "category": "navigation",
                "region": "content",
            },
            {
                "element_id": "help_1",
                "role": "link",
                "label": "Help",
                "raw_href": "/#help-support",
                "target_path": "/#help-support",
                "category": "internal_hash",
                "region": "header",
            },
        ]
        nav = build_home_navigation(elements)
        labels = [n["label"] for n in nav]
        self.assertIn("Site Map", labels)
        self.assertIn("Help", labels)
        self.assertNotIn("Mandi", labels)
        self.assertNotIn("Skip to Content", labels)
        help_entry = next(n for n in nav if n["label"] == "Help")
        self.assertEqual(help_entry["assert"]["kind"], "hash")


class TestContractV11(unittest.TestCase):
    def test_loads_v11_with_home_navigation(self):
        data = {
            "contract_version": "1.1.0",
            "application": {"name": "test", "base_url": "https://example.com"},
            "route_index": [],
            "home_navigation": [
                {
                    "element_id": "x_1",
                    "label": "Home",
                    "raw_href": "/",
                    "target_path": "/",
                    "assert": {"kind": "same_page", "value": "/"},
                }
            ],
            "pages": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            contract = load_contract(path)
            self.assertEqual(contract.version, "1.1.0")
            self.assertEqual(len(contract.home_navigation), 1)
            slice_data = contract.slice_for_module("navigation")
            self.assertIn("home_navigation", slice_data)


if __name__ == "__main__":
    unittest.main()
