"""
Test Case Generator
-----------------
Test plan Markdown + contract → YAML testcases per flow.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from lib.artifacts import testcase_path, testcase_rel
from lib.contract import Contract, load_contract, page_id_to_pom_name
from generators.test_plan_generator import load_plan_contract_slice
from lib.contract_slimmer import slim_contract_for_intent
from lib.contract_validate import validate_flow
from lib.llm import LLMClient
from lib.paths import ensure_app_dirs
from lib.prompts import build_testcase_messages
from lib.workspace import parse_plan_frontmatter, register_testcases

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _extract_flow_from_llm_result(result: Any) -> dict[str, Any] | None:
    """Accept flow wrapped as {flow}, {flows:[...]}, or at JSON root (per prompt)."""
    if isinstance(result, list):
        return result[0] if result and isinstance(result[0], dict) else None
    if not isinstance(result, dict):
        return None

    flow = result.get("flow")
    if isinstance(flow, dict):
        return flow

    flows = result.get("flows")
    if isinstance(flows, list) and flows:
        if len(flows) > 1:
            log.warning("LLM returned %d flows — using first only (1 plan = 1 testcase)", len(flows))
        if isinstance(flows[0], dict):
            return flows[0]

    testcase = result.get("testcase")
    if isinstance(testcase, dict):
        return testcase

    # Prompt asks for the flow object at the root (module, flow_id, cases, …).
    if result.get("cases") or result.get("flow_id"):
        return result

    return None


def _normalize_flow(flow: dict[str, Any], module: str, plan_id: str = "") -> dict[str, Any]:
    flow = dict(flow)
    flow["module"] = flow.get("module") or module
    flow.setdefault("type", ["e2e"])
    flow.setdefault("tags", ["regression"])
    flow.setdefault("actors", ["public"])
    flow.setdefault("environments", {"qa_ui": "${QA_UI_BASE_URL}"})

    ui_pages = flow.get("ui_pages") or []
    normalized_pages = []
    for name in ui_pages:
        if name.endswith("Page"):
            normalized_pages.append(name)
        else:
            normalized_pages.append(page_id_to_pom_name(name.replace("Page", "").lower()))
    flow["ui_pages"] = normalized_pages

    flow_id = flow.get("flow_id") or plan_id or "FLOW-01"
    cases = []
    for i, case in enumerate(flow.get("cases", [])):
        case = dict(case)
        if not case.get("id"):
            case["id"] = f"{flow_id}-H{i + 1}"
        case.setdefault("test_type", ["e2e"])
        case.setdefault("type", "happy_path")
        case.setdefault("tags", flow.get("tags", ["regression"]))
        cases.append(case)
    flow["cases"] = cases
    return flow


def generate_testcases_for_plan(
    contract: Contract,
    app_slug: str,
    plan_path: Path,
    llm: LLMClient | None = None,
    skip_overlap: bool = False,
    plan_id: str | None = None,
) -> list[Path]:
    llm = llm or LLMClient()
    root = ensure_app_dirs(app_slug)
    meta = parse_plan_frontmatter(plan_path)
    module = meta.get("module") or plan_path.stem
    user_intent = meta.get("user_intent", "")
    plan_id = plan_id or meta.get("plan_id") or plan_path.stem
    plan_text = plan_path.read_text(encoding="utf-8")

    slice_data = load_plan_contract_slice(root, meta)
    if slice_data is None and user_intent.strip():
        _, slice_data = slim_contract_for_intent(contract, user_intent)
    elif slice_data is None:
        slice_data = contract.slice_for_module(module)
        if not slice_data.get("pages"):
            slice_data = contract.trim_for_prompt()
    messages = build_testcase_messages(
        module, plan_text, slice_data, user_intent=user_intent, plan_id=plan_id
    )
    result = llm.complete_json_messages(messages, temperature=0.0, max_tokens=8000)

    flow = _extract_flow_from_llm_result(result)
    if not flow:
        preview = str(result)[:500] if result is not None else "(empty)"
        raise ValueError(
            f"LLM returned no flow for plan {plan_path}. Response preview: {preview}"
        )

    flow = _normalize_flow(flow, module, plan_id=plan_id)
    flow["flow_id"] = plan_id
    flow, warnings = validate_flow(flow, contract, meta)
    for warning in warnings:
        log.warning("  Validator: %s", warning)

    out_dir = root / "tests" / "testcases" / plan_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = testcase_path(root, plan_id)

    for old in out_dir.glob("*.yaml"):
        if old != out_path:
            old.unlink()
            log.info("  Removed extra testcase: %s", old.name)

    with out_path.open("w", encoding="utf-8") as f:
        yaml.dump(flow, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    log.info("  Written: %s", out_path)

    cases = flow.get("cases") or []
    title = cases[0].get("title", "") if cases else ""
    case_titles = [c.get("title", "") for c in cases if c.get("title")]

    register_testcases(
        app_slug,
        plan_id,
        [{
            "flow_id": plan_id,
            "path": testcase_rel(plan_id),
            "title": title,
            "case_count": str(len(cases)),
            "case_titles": " | ".join(case_titles[:5]),
        }],
    )

    return [out_path]


def generate_all_testcases(
    contract: Contract,
    app_slug: str,
    plan_dir: Path | None = None,
    llm: LLMClient | None = None,
) -> list[Path]:
    root = ensure_app_dirs(app_slug)
    plan_dir = plan_dir or (root / "tests" / "testplan")
    written: list[Path] = []
    for plan_path in sorted(plan_dir.glob("*.md")):
        log.info("Generating YAML from plan: %s", plan_path.name)
        written.extend(generate_testcases_for_plan(contract, app_slug, plan_path, llm=llm))
    return written


def main():
    parser = argparse.ArgumentParser(description="Generate YAML testcases from test plans + contract")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--plan", help="Single plan file (default: all in output/{app}/tests/testplan/)")
    parser.add_argument("--skip-overlap", action="store_true")
    args = parser.parse_args()

    contract = load_contract(args.contract)
    root = ensure_app_dirs(args.app)

    if args.plan:
        plan_path = Path(args.plan)
        if not plan_path.is_absolute():
            plan_path = root / plan_path
        paths = generate_testcases_for_plan(
            contract, args.app, plan_path, skip_overlap=args.skip_overlap
        )
    else:
        paths = generate_all_testcases(contract, args.app)

    print(f"\nDone! {len(paths)} YAML file(s) written.")


if __name__ == "__main__":
    main()
