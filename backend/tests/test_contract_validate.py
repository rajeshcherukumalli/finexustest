"""Tests for contract-grounded testcase validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.contract import load_contract
from lib.contract_validate import enforce_plan_module, validate_flow, validate_element_ref

FIXTURE = Path(__file__).parent / "fixtures" / "nav_contract.json"


@pytest.fixture
def contract():
    return load_contract(FIXTURE)


def test_enforce_plan_module_overrides_llm():
    flow = {"module": "content", "cases": []}
    meta = {"module": "navigation", "user_intent": "verify nav links"}
    out = enforce_plan_module(flow, meta)
    assert out["module"] == "navigation"


def test_rejects_invented_element_id(contract):
    ref = {"element_id": "fake_link", "action": "click", "page_id": "home"}
    fixed, err = validate_element_ref(ref, contract)
    assert fixed is None
    assert "unknown element_id" in (err or "")


def test_rewrites_nav_from_home_navigation(contract):
    flow = {
        "module": "content",
        "flow_id": "plan-test",
        "cases": [{
            "id": "plan-test-H1",
            "title": "Nav smoke",
            "nav_links": [{"element_id": "invented", "label": "Bad"}],
            "element_refs": [{"element_id": "invented", "page_id": "home"}],
        }],
    }
    meta = {"module": "navigation", "user_intent": "verify all header nav links"}
    out, warnings = validate_flow(flow, contract, meta)
    assert out["module"] == "navigation"
    case = out["cases"][0]
    assert len(case["nav_links"]) == 3
    ids = {n["element_id"] for n in case["nav_links"]}
    assert ids == {"help_link", "privacy_link", "faq_hash"}
    assert case["nav_links"][0].get("assert")


def test_multi_case_normalizes_ids(contract):
    flow = {
        "module": "navigation",
        "flow_id": "plan-abc",
        "cases": [
            {"title": "Help only", "nav_links": [{"element_id": "help_link", "label": "Help"}]},
            {"title": "Privacy only", "nav_links": [{"element_id": "privacy_link", "label": "Privacy policy"}]},
        ],
    }
    meta = {"module": "navigation", "user_intent": "nav links"}
    out, _ = validate_flow(flow, contract, meta)
    assert out["cases"][0]["id"] == "plan-abc-H1"
    assert out["cases"][1]["id"] == "plan-abc-H2"
    assert len(out["cases"][0]["nav_links"]) == 1
    assert out["cases"][0]["nav_links"][0]["element_id"] == "help_link"


def test_validate_prefers_home_header_for_assets_click(contract):
    ref = {"element_id": "assets_btn", "action": "click", "page_id": "assets_section"}
    fixed, err = validate_element_ref(ref, contract)
    assert err is None
    assert fixed["page_id"] == "home"
    assert fixed["element_id"] == "assets_btn"


def test_content_flow_strips_spurious_nav_links(contract):
    """LLM sometimes copies home_navigation into content cases — validator must not rewrite element_refs."""
    flow = {
        "module": "content",
        "flow_id": "plan-assets",
        "cases": [{
            "id": "plan-assets-H1",
            "title": "Search Pashu on assets page",
            "nav_links": [{"element_id": "help_link", "label": "Help", "route": "/help"}],
            "element_refs": [
                {"element_id": "assets_btn", "action": "click", "page_id": "home"},
                {"element_id": "search_assets", "action": "fill", "page_id": "assets_section", "value": "Pashu"},
            ],
        }],
    }
    meta = {"module": "content", "user_intent": "Go to assets page and search for Pashu"}
    out, warnings = validate_flow(flow, contract, meta)
    case = out["cases"][0]
    assert out["module"] == "content"
    assert not case.get("nav_links")
    assert any(w for w in warnings if "removed nav_links" in w)
    ids = {r["element_id"] for r in case["element_refs"]}
    assert ids == {"assets_btn", "search_assets"}
    assert case["element_refs"][1].get("action") == "fill"


def test_content_flow_drops_home_nav_element_refs(contract):
    flow = {
        "module": "content",
        "flow_id": "plan-bad",
        "cases": [{
            "id": "plan-bad-H1",
            "title": "Assets search",
            "nav_links": [{"element_id": "help_link"}],
            "element_refs": [
                {"element_id": "help_link", "action": "click", "page_id": "home"},
                {"element_id": "privacy_link", "action": "click", "page_id": "home"},
            ],
        }],
    }
    meta = {"module": "content", "user_intent": "Go to assets page and search for Pashu"}
    out, warnings = validate_flow(flow, contract, meta)
    assert out["cases"][0]["element_refs"] == []
    assert any("dropped" in w and "home_navigation" in w for w in warnings)
    assert any("no content element_refs" in w for w in warnings)


def test_slice_for_case_includes_home_navigation(contract):
    case = {
        "nav_links": [{"element_id": "help_link"}],
        "element_refs": [{"element_id": "help_link", "page_id": "home"}],
    }
    slice_data = contract.slice_for_case(case)
    assert "home_navigation" in slice_data
    assert any(e["element_id"] == "help_link" for p in slice_data["pages"] for e in p["elements"])
