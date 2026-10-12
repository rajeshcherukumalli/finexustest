"""Tests for deterministic intent-driven plan generation."""

from __future__ import annotations

from pathlib import Path

from generators.test_plan_generator import generate_test_plan_for_intent
from lib.contract import load_contract


FIXTURE = Path(__file__).parent / "fixtures" / "nav_contract.json"


def test_generate_test_plan_for_intent_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_AUTOMATION_DATA", str(tmp_path / "data"))
    contract = load_contract(FIXTURE)

    plan_id, plan_path = generate_test_plan_for_intent(
        contract,
        "demo_app",
        "Open Blog and confirm article or list content is visible",
    )

    text = plan_path.read_text(encoding="utf-8")
    assert plan_id in plan_path.name
    assert "## Module purpose" in text
    assert "## Actors" in text
    assert "## Page sequence" in text
    assert "## Flows to test" in text
    assert "## Key assertions" in text
    assert "## Per-flow notes" in text
    assert "| Flow ID | Description | Priority |" in text
    assert "module: content" in text
    assert "home - /" in text
    assert "blog - /blog" in text
    assert "about - /about" not in text
    assert "The URL should match the expected route: `/blog`." in text
    assert "blog_3" in text
    assert "generic" not in text.lower()


def test_generate_test_plan_stops_at_resolved_journey(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_AUTOMATION_DATA", str(tmp_path / "data"))
    contract = load_contract(FIXTURE)

    _, plan_path = generate_test_plan_for_intent(
        contract,
        "demo_app",
        'Go to homepage and click on "Launch your career"',
    )

    text = plan_path.read_text(encoding="utf-8")
    assert "module: navigation" in text
    assert "home - /" in text
    assert "coaching - /coaching" in text
    assert "ai_augmented_professional" not in text
    assert "The URL should match the expected route: `/coaching`." in text
    assert "coaching_3" in text
