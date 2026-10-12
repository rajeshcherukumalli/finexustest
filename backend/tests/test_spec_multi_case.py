"""Tests for multi-case Playwright spec generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from generators.spec_generator import (
    _allowed_selectors,
    _ensure_locator_first,
    _normalize_llm_case_body,
    _normalize_page_id,
    _resolve_start_path,
    _sanitize_llm_body,
    _test_open_line,
    generate_spec,
)
from lib.contract import load_contract

FIXTURE = Path(__file__).parent / "fixtures" / "nav_contract.json"


@pytest.fixture
def contract():
    return load_contract(FIXTURE)


def _nav_flow_multi_case() -> dict:
    return {
        "module": "navigation",
        "flow_id": "plan-nav",
        "flow_name": "header_nav",
        "tags": ["smoke"],
        "actors": ["public"],
        "ui_pages": ["HomePage"],
        "cases": [
            {
                "id": "plan-nav-H1",
                "title": "Help link",
                "nav_links": [{
                    "element_id": "help_link",
                    "label": "Help",
                    "route": "/help",
                    "assert": {"kind": "pathname", "value": "/help"},
                }],
                "element_refs": [{"element_id": "help_link", "action": "click", "page_id": "home"}],
            },
            {
                "id": "plan-nav-H2",
                "title": "Privacy link",
                "nav_links": [{
                    "element_id": "privacy_link",
                    "label": "Privacy policy",
                    "route": "/privacypolicy",
                    "assert": {"kind": "pathname", "value": "/privacypolicy"},
                }],
                "element_refs": [{"element_id": "privacy_link", "action": "click", "page_id": "home"}],
            },
            {
                "id": "plan-nav-H3",
                "title": "FAQ hash",
                "nav_links": [{
                    "element_id": "faq_hash",
                    "label": "FAQ",
                    "route": "/#faq",
                    "assert": {"kind": "hash", "value": "#faq"},
                }],
                "element_refs": [{"element_id": "faq_hash", "action": "click", "page_id": "home"}],
            },
        ],
    }


def test_multi_case_emits_three_tests(contract):
    flow = _nav_flow_multi_case()
    spec = generate_spec(flow, contract, Path("case.yaml"), use_llm_spec=False)
    assert spec.count("test('plan-nav-H") == 3
    assert "toHaveURL" in spec
    assert "url.hash === '#faq'" in spec or "hash" in spec


def test_spec_includes_allure_annotations(contract):
    flow = _nav_flow_multi_case()
    spec = generate_spec(
        flow,
        contract,
        Path("tests/testcases/plan-nav.yaml"),
        use_llm_spec=False,
    )
    assert "import { allure } from 'allure-playwright'" in spec
    assert "await allure.epic('navigation')" in spec
    assert "await allure.feature('header_nav')" in spec
    assert "await allure.story('Help link')" in spec
    assert "await allure.step(" in spec


def test_content_module_does_not_emit_nav_loop(contract):
    """Content module with stray nav_links must not run the home_navigation click loop."""
    flow = _nav_flow_multi_case()
    flow["module"] = "content"
    spec = generate_spec(flow, contract, Path("case.yaml"), use_llm_spec=False)
    assert spec.count("test('plan-nav-H") == 3
    assert "getByRole('link', { name: 'Help' })" in spec
    assert "for (const link of NAV_LINKS)" not in spec


def test_deterministic_spec_uses_contract_selectors_not_pom_helpers(contract):
    flow = {
        "module": "content",
        "flow_id": "plan-assets",
        "flow_name": "assets_search",
        "tags": ["smoke"],
        "actors": ["public"],
        "ui_pages": ["HomePage", "AssetssectionPage"],
        "cases": [{
            "id": "plan-assets-H1",
            "title": "Search Pashu Bazar",
            "preconditions": ["User is on the home page"],
            "element_refs": [
                {"element_id": "assets_btn", "action": "click", "page_id": "home"},
                {"element_id": "search_assets", "action": "fill", "page_id": "assets_section", "value": "Pashu Bazar"},
            ],
            "assertions": ["page_title_visible"],
        }],
    }
    spec = generate_spec(flow, contract, Path("case.yaml"), use_llm_spec=False)
    assert "clickAssetsButton" not in spec
    assert "fillSearchInput" not in spec
    assert "new HomePage" not in spec
    assert ".fill('Pashu Bazar')" in spec
    assert "Assets" in spec


def test_sanitize_strips_invented_pom_methods(contract):
    slice_data = contract.slice_for_case({
        "element_refs": [{"element_id": "assets_btn", "page_id": "home"}],
    })
    body = """await new HomePage(page).clickAssetsButton();
await page.getByRole('button', { name: 'Assets', exact: true }).click();"""
    out = _sanitize_llm_body(body, _allowed_selectors(slice_data), contract, {}, slice_data)
    assert "clickAssetsButton()" not in out
    assert "getByRole('button'" in out


def test_content_assets_spec_clicks_not_header_nav(contract):
    flow = {
        "module": "content",
        "flow_id": "plan-assets",
        "flow_name": "assets_search",
        "tags": ["smoke"],
        "actors": ["public"],
        "ui_pages": ["HomePage", "AssetssectionPage"],
        "cases": [{
            "id": "plan-assets-H1",
            "title": "Search Pashu",
            "element_refs": [
                {"element_id": "assets_btn", "action": "click", "page_id": "home"},
                {"element_id": "search_assets", "action": "fill", "page_id": "assets_section"},
            ],
            "assertions": ["page_title_visible"],
        }],
    }
    spec = generate_spec(flow, contract, Path("case.yaml"), use_llm_spec=False)
    assert "Assets" in spec
    assert "about-home" not in spec
    assert "#faq" not in spec


def test_full_nav_case_matches_home_navigation_count(contract):
    """Integration-style: validated single nav case → spec clicks match home_navigation."""
    from lib.contract_validate import validate_flow

    flow = {
        "module": "content",
        "flow_id": "plan-8ccab92d",
        "flow_name": "header_nav",
        "tags": ["smoke"],
        "actors": ["public"],
        "ui_pages": ["HomePage"],
        "cases": [{
            "title": "All header links",
            "nav_links": [{"element_id": "bogus", "label": "Fake"}],
        }],
    }
    meta = {"module": "navigation", "user_intent": "verify all nav links in header"}
    validated, _ = validate_flow(flow, contract, meta)
    assert len(validated["cases"]) == 1
    assert len(validated["cases"][0]["nav_links"]) == len(contract.home_navigation)

    spec = generate_spec(validated, contract, Path("case.yaml"), use_llm_spec=False)
    assert spec.count("test('plan-8ccab92d-H1") == 1
    assert spec.count(".click()") >= len(contract.home_navigation)
    assert spec.count("toHaveURL") >= len(contract.home_navigation)


def test_normalize_page_id_snake_case():
    assert _normalize_page_id("assets_section") == "assets_section"
    assert _normalize_page_id("AssetsSectionPage") == "assets_section"


def test_resolve_start_path_uses_home_precondition(contract):
    flow = {
        "module": "content",
        "ui_pages": ["AssetsSectionPage"],
        "cases": [{
            "preconditions": ["User is on the home page"],
            "element_refs": [{"element_id": "assets_7", "page_id": "assets_section"}],
        }],
    }
    assert _resolve_start_path(flow, contract, "content") == "/"


def test_ensure_locator_first_adds_disambiguation():
    line = "await page.getByRole('button', { name: 'Assets', exact: true }).click();"
    assert ".first().click()" in _ensure_locator_first(line)


def test_test_title_escapes_apostrophes():
    line = _test_open_line("plan-1-H1", "Search for 'Pashu'")
    assert "Search for \\'Pashu\\'" in line
    assert line.count("test(") == 1


def test_normalize_llm_case_body_strips_wrapper():
    body = """test('plan-1-H1: Search for "Pashu"', async ({ page }) => {
  await page.click('button');
});"""
    inner = _normalize_llm_case_body(body)
    assert "test(" not in inner
    assert "await page.click('button');" in inner
    assert "});" not in inner


def test_spec_title_with_apostrophe_is_valid_ts(contract):
    flow = {
        "module": "content",
        "flow_id": "plan-pashu",
        "flow_name": "assets_search",
        "tags": ["smoke"],
        "actors": ["public"],
        "ui_pages": ["HomePage"],
        "cases": [{
            "id": "plan-pashu-H1",
            "title": "Navigate to Assets Page and Search for 'Pashu'",
            "element_refs": [
                {"element_id": "assets_btn", "action": "click", "page_id": "home"},
            ],
            "assertions": ["page_title_visible"],
        }],
    }
    spec = generate_spec(flow, contract, Path("case.yaml"), use_llm_spec=False)
    assert spec.count("test('plan-pashu-H1:") == 1
    assert "Search for \\'Pashu\\'" in spec
    assert "Search for 'Pashu'" not in spec.split("test(")[1].split("', async")[0]


def test_assertions_hash_pathname():
    from lib.assertions import assert_line_from_contract

    hash_line = assert_line_from_contract({"kind": "hash", "value": "#faq"})
    assert "url.hash === '#faq'" in hash_line

    path_line = assert_line_from_contract({"kind": "pathname", "value": "/help"})
    assert "pathname === '/help'" in path_line
