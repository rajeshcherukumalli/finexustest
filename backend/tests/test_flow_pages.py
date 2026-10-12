"""Tests for deterministic Playwright execution page resolution."""

from __future__ import annotations

from pathlib import Path

from lib.contract import load_contract
from lib.contract_slimmer import slim_contract_for_intent
from lib.flow_pages import (
    build_execution_slice,
    canonical_ui_pages,
    resolve_flow_page_ids,
)

FIXTURE = Path(__file__).parent / "fixtures" / "nav_contract.json"


def _slim_and_contract():
    contract = load_contract(FIXTURE)
    _, slim = slim_contract_for_intent(contract, "Go to assets page and search for equipment")
    return contract, slim


def test_content_flow_resolves_home_and_assets():
    contract, slim = _slim_and_contract()
    flow = {
        "module": "content",
        "ui_pages": ["HomePage", "AssetsSectionPage"],
        "cases": [
            {
                "id": "plan-H1",
                "element_refs": [
                    {"element_id": "assets_btn", "action": "click", "page_id": "home"},
                    {"element_id": "search_assets", "action": "fill", "page_id": "assets_section"},
                ],
            }
        ],
    }
    plan_meta = {"page_sequence": "home,assets_section"}

    page_ids, _ = resolve_flow_page_ids(flow, slim, plan_meta, contract)
    assert page_ids == ["home", "assets_section"]

    execution = build_execution_slice(contract, slim, flow, plan_meta)
    assert execution["page_sequence"] == ["home", "assets_section"]
    assert {p["page_id"] for p in execution["pages"]} == {"home", "assets_section"}

    home = next(p for p in execution["pages"] if p["page_id"] == "home")
    assert {e["element_id"] for e in home["elements"]} == {"assets_btn"}

    assets = next(p for p in execution["pages"] if p["page_id"] == "assets_section")
    assert {e["element_id"] for e in assets["elements"]} == {"search_assets"}


def test_bad_ui_pages_still_resolve_via_element_target_path():
    contract, slim = _slim_and_contract()
    flow = {
        "module": "content",
        "ui_pages": ["HomePage", "WrongAssetsPageName"],
        "cases": [
            {
                "id": "plan-H1",
                "element_refs": [
                    {"element_id": "assets_btn", "action": "click", "page_id": "home"},
                ],
            }
        ],
    }
    plan_meta = {"page_sequence": "home,assets_section"}

    page_ids, warnings = resolve_flow_page_ids(flow, slim, plan_meta, contract)
    assert page_ids == ["home", "assets_section"]
    assert any("WrongAssetsPageName" in w for w in warnings)

    execution = build_execution_slice(contract, slim, flow, plan_meta)
    assert canonical_ui_pages(execution["page_sequence"]) == ["HomePage", "AssetsSectionPage"]


def test_nav_flow_includes_home_and_nav_targets_in_slim():
    contract = load_contract(FIXTURE)
    _, slim = slim_contract_for_intent(contract, "Verify all header navigation links work")
    slim["pages"].append(
        {
            "page_id": "help",
            "path": "/help",
            "page_type": "content",
            "elements": [
                {
                    "element_id": "help_link",
                    "role": "link",
                    "label": "Help",
                    "target_path": "/help",
                    "selectors": {"playwright": "page.getByRole('link', { name: 'Help' })"},
                }
            ],
            "forms": [],
        }
    )
    slim["route_index"] = list(slim.get("route_index", [])) + [
        {"page_id": "help", "path": "/help", "page_type": "content"},
    ]

    flow = {
        "module": "navigation",
        "ui_pages": ["HomePage"],
        "cases": [
            {
                "id": "plan-H1",
                "nav_links": [
                    {
                        "label": "Help",
                        "route": "/help",
                        "element_id": "help_link",
                    }
                ],
            }
        ],
    }
    plan_meta = {"page_sequence": "home"}

    page_ids, _ = resolve_flow_page_ids(flow, slim, plan_meta, contract)
    assert page_ids == ["home", "help"]

    execution = build_execution_slice(contract, slim, flow, plan_meta)
    assert "home_navigation" in execution


def test_page_sequence_order_preserved():
    contract, slim = _slim_and_contract()
    flow = {
        "module": "content",
        "ui_pages": ["AssetsSectionPage", "HomePage"],
        "cases": [
            {
                "id": "plan-H1",
                "element_refs": [
                    {"element_id": "search_assets", "action": "fill", "page_id": "assets_section"},
                    {"element_id": "assets_btn", "action": "click", "page_id": "home"},
                ],
            }
        ],
    }
    plan_meta = {"page_sequence": "home,assets_section"}

    page_ids, _ = resolve_flow_page_ids(flow, slim, plan_meta, contract)
    assert page_ids == ["home", "assets_section"]
