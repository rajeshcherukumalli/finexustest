"""Tests for intent-aware contract slimming."""

from __future__ import annotations

import json
from pathlib import Path

from lib.contract import load_contract
from lib.contract_slimmer import (
    infer_module_from_intent,
    resolve_target_pages,
    slim_contract_for_intent,
)

FIXTURE = Path(__file__).parent / "fixtures" / "nav_contract.json"
DFSQA_CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "output"
    / "dfsqa_v3"
    / "dfsqa_v3-contract.json"
)


def test_infer_module_from_intent():
    assert infer_module_from_intent("Verify login with OTP") == "auth"
    assert infer_module_from_intent("Check all header nav links") == "navigation"
    assert infer_module_from_intent("Go to assets page and search") == "content"


def test_slim_content_intent_keeps_relevant_pages():
    contract = load_contract(FIXTURE)
    module, slim = slim_contract_for_intent(
        contract,
        "Go to assets page and search for equipment",
    )

    assert module == "content"
    assert slim["page_sequence"] == ["home", "assets_section"]
    page_ids = {p["page_id"] for p in slim["pages"]}
    assert page_ids == {"home", "assets_section"}
    assert "help" not in page_ids
    assert "privacypolicy" not in page_ids

    home = next(p for p in slim["pages"] if p["page_id"] == "home")
    home_element_ids = {e["element_id"] for e in home["elements"]}
    assert "assets_btn" in home_element_ids
    assert len(home["elements"]) <= 25

    assets = next(p for p in slim["pages"] if p["page_id"] == "assets_section")
    assert any(e["element_id"] == "search_assets" for e in assets["elements"])


def test_slim_navigation_intent_includes_home_navigation():
    contract = load_contract(FIXTURE)
    module, slim = slim_contract_for_intent(
        contract,
        "Verify all header navigation links work",
    )

    assert module == "navigation"
    assert slim["page_sequence"] == ["home"]
    assert len(slim["home_navigation"]) == 3
    assert "home_navigation" in slim


def test_slim_navigation_intent_filters_specific_link():
    contract = load_contract(FIXTURE)
    module, slim = slim_contract_for_intent(contract, 'Click the "Help" link in the header')

    assert module == "navigation"
    nav_labels = {e["label"] for e in slim["home_navigation"]}
    assert nav_labels == {"Help"}


def test_slim_dfsqa_contract_is_much_smaller():
    if not DFSQA_CONTRACT.exists():
        return

    contract = load_contract(DFSQA_CONTRACT)
    full_size = len(json.dumps(contract.raw))

    _, slim = slim_contract_for_intent(
        contract,
        "Go to mandi price page and verify dashboard loads",
    )
    slim_size = len(json.dumps(slim))

    assert slim_size < full_size * 0.10
    assert slim["page_sequence"][0] == "home"
    assert "mandi" in slim["page_sequence"]
    assert len(slim["pages"]) <= 6


def test_resolve_target_pages_content_journey():
    contract = load_contract(FIXTURE)
    pages = resolve_target_pages(
        contract,
        "Open assets and search",
        "content",
    )
    assert pages[0] == "home"
    assert "assets_section" in pages
