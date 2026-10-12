"""
Test Plan Generator
-------------------
Contract JSON → Markdown test plans per module.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from lib.contract import DEFAULT_MODULES, Contract, load_contract
from lib.contract_slimmer import slim_contract_for_intent
from lib.llm import LLMClient
from lib.paths import ensure_app_dirs
from lib.prompts import build_test_plan_messages, test_plan_prompt
from lib.workspace import add_plan, new_plan_id

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def slice_for_intent(contract: Contract, user_intent: str) -> tuple[str, dict]:
    return slim_contract_for_intent(contract, user_intent)


def load_plan_contract_slice(app_root: Path, plan_meta: dict) -> dict | None:
    """Load persisted slim contract metadata written during plan generation."""
    rel = plan_meta.get("contract_slice_path", "").strip()
    if not rel:
        return None
    path = app_root / rel
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def generate_test_plan_for_intent(
    contract: Contract,
    app_slug: str,
    user_intent: str,
    llm: LLMClient | None = None,
) -> tuple[str, Path]:
    llm = llm or LLMClient()
    root = ensure_app_dirs(app_slug)
    plan_dir = root / "tests" / "testplan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    plan_id = new_plan_id()
    module, slice_data = slice_for_intent(contract, user_intent)

    slice_rel = f"tests/testplan/{plan_id}.contract-slice.json"
    slice_path = root / slice_rel
    slice_path.write_text(json.dumps(slice_data, indent=2), encoding="utf-8")

    log.info(
        "Generating intent-driven plan %s (module=%s, pages=%s)",
        plan_id,
        module,
        slice_data.get("page_sequence", []),
    )
    messages = build_test_plan_messages(user_intent, slice_data, plan_id, module)
    markdown = llm.complete_messages(messages, temperature=0.2, max_tokens=2500)

    created_at = datetime.now(timezone.utc).isoformat()
    rel_path = f"tests/testplan/{plan_id}.md"
    out_path = root / rel_path
    page_sequence = ",".join(slice_data.get("page_sequence", []))
    frontmatter = (
        f"---\n"
        f"plan_id: {plan_id}\n"
        f"user_intent: {user_intent}\n"
        f"module: {module}\n"
        f"page_sequence: {page_sequence}\n"
        f"contract_slice_path: {slice_rel}\n"
        f"created_at: {created_at}\n"
        f"---\n\n"
    )
    header = f"# Test plan: {plan_id}\n\n"
    header += f"<!-- generated from {contract.path.name} | app: {contract.app_name} -->\n\n"
    out_path.write_text(frontmatter + header + markdown.strip() + "\n", encoding="utf-8")
    add_plan(app_slug, plan_id, user_intent, rel_path)
    log.info("  Written: %s", out_path)
    return plan_id, out_path


def generate_test_plans(
    contract: Contract,
    app_slug: str,
    modules: list[str] | None = None,
    llm: LLMClient | None = None,
) -> list[Path]:
    modules = modules or list(DEFAULT_MODULES)
    llm = llm or LLMClient()
    root = ensure_app_dirs(app_slug)
    plan_dir = root / "tests" / "testplan"
    written: list[Path] = []

    for module in modules:
        slice_data = contract.slice_for_module(module)
        if not slice_data.get("pages"):
            log.warning("No pages for module %s — skipping", module)
            continue

        log.info("Generating test plan for module: %s", module)
        prompt = test_plan_prompt(module, slice_data)
        markdown = llm.complete(prompt, temperature=0.2, max_tokens=2500)

        out_path = plan_dir / f"{module}.md"
        header = f"# Test plan: {module}\n\n"
        header += f"<!-- generated from {contract.path.name} | app: {contract.app_name} -->\n\n"
        out_path.write_text(header + markdown.strip() + "\n", encoding="utf-8")
        written.append(out_path)
        log.info("  Written: %s", out_path)

    return written


def main():
    parser = argparse.ArgumentParser(description="Generate Markdown test plans from UI contract")
    parser.add_argument("--contract", required=True, help="Path to UI action contract JSON")
    parser.add_argument("--app", required=True, help="App slug for output/{app}/")
    parser.add_argument(
        "--modules",
        default=",".join(DEFAULT_MODULES),
        help="Comma-separated modules (auth,navigation,content)",
    )
    args = parser.parse_args()

    contract = load_contract(args.contract)
    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    paths = generate_test_plans(contract, args.app, modules)
    print(f"\nDone! {len(paths)} test plan(s) written.")


if __name__ == "__main__":
    main()
