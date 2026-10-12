#!/usr/bin/env python3
"""
QA Automation Pipeline
----------------------
Contract → test plans → YAML testcases → Playwright E2E specs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from generators.spec_generator import generate_all_specs, scaffold_app
from generators.test_plan_generator import generate_test_plans
from generators.testcase_generator import generate_all_testcases
from lib.contract import DEFAULT_MODULES, load_contract
from lib.llm import LLMClient
from lib.paths import PIPELINE_VERSION, app_output_dir, contracts_dir, ensure_app_dirs
from lib.scraper_credentials import load_scraper_credentials
from scraper import scrape_website

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _contract_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def write_manifest(
    app_slug: str,
    contract_path: Path,
    contract,
    steps_run: list[str],
    modules: list[str],
    flow_ids: list[str],
) -> Path:
    root = app_output_dir(app_slug)
    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_slug": app_slug,
        "contract_path": str(contract_path),
        "contract_hash": _contract_hash(contract_path),
        "contract_scraped_at": contract.scraped_at,
        "application": contract.raw.get("application", {}),
        "steps_run": steps_run,
        "modules": modules,
        "flows_generated": flow_ids,
    }
    out = root / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("Manifest written: %s", out)
    return out


def _workspace_seed_paths(app_slug: str) -> list[str]:
    """Read per-app seed paths from workspace.json."""
    try:
        from lib.workspace import load_workspace

        seeds = load_workspace(app_slug).get("seed_paths") or []
        return [s for s in seeds if isinstance(s, str) and s.strip()]
    except Exception:
        return []


def run_pipeline(
    contract_path: str,
    app_slug: str,
    steps: list[str],
    modules: list[str] | None = None,
    scrape_url: str | None = None,
    max_pages: int = 20,
    headed: bool = False,
    seed_paths: list[str] | None = None,
    interact: bool = True,
    merge: bool = True,
) -> dict:
    modules = modules or list(DEFAULT_MODULES)
    steps_run: list[str] = []

    if "scrape" in steps:
        seeds = list(seed_paths) if seed_paths else _workspace_seed_paths(app_slug)
        log.info("Step scrape: crawling %s (seeds: %s)", scrape_url, seeds or "none")
        contract_path = scrape_website(
            base_url=scrape_url,
            output_path=contract_path,
            max_pages=max_pages,
            credentials=load_scraper_credentials(),
            headed=headed,
            seed_paths=seeds,
            interact=interact,
            merge=merge,
        )
        steps_run.append("scrape")

    contract = load_contract(contract_path)
    ensure_app_dirs(app_slug)
    llm = LLMClient()

    if "plan" in steps:
        log.info("Step plan: generating test plans")
        generate_test_plans(contract, app_slug, modules, llm=llm)
        steps_run.append("plan")

    if "yaml" in steps:
        log.info("Step yaml: generating testcases")
        generate_all_testcases(contract, app_slug, llm=llm)
        steps_run.append("yaml")

    flow_ids: list[str] = []
    if "spec" in steps:
        log.info("Step spec: generating E2E specs and POMs")
        scaffold_app(app_output_dir(app_slug), contract)
        generate_all_specs(contract, app_slug, llm=llm)
        steps_run.append("spec")

    testcase_dir = app_output_dir(app_slug) / "tests" / "testcases"
    for yaml_path in sorted(testcase_dir.rglob("*.yaml")):
        import yaml

        try:
            with yaml_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            log.warning("Skipping malformed testcase YAML %s: %s", yaml_path, e)
            continue
        fid = data.get("flow_id")
        if fid:
            flow_ids.append(fid)

    manifest_path = write_manifest(
        app_slug,
        Path(contract_path),
        contract,
        steps_run,
        modules,
        sorted(set(flow_ids)),
    )

    return {
        "manifest": str(manifest_path),
        "steps_run": steps_run,
        "flows": sorted(set(flow_ids)),
    }


def main():
    parser = argparse.ArgumentParser(description="Run QA automation pipeline")
    parser.add_argument("--contract", help="Path to UI contract JSON")
    parser.add_argument("--app", required=True, help="App slug for output/{app}/")
    parser.add_argument(
        "--steps",
        default="plan,yaml,spec",
        help="Comma-separated: scrape,plan,yaml,spec (or all)",
    )
    parser.add_argument("--modules", default=",".join(DEFAULT_MODULES))
    parser.add_argument("--url", help="Base URL to scrape (enables scrape step)")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument(
        "--seed-paths",
        default="",
        help="Comma-separated extra entry paths (falls back to workspace.json seed_paths)",
    )
    parser.add_argument("--no-interact", action="store_true", help="Skip dropdown/menu interaction pass")
    parser.add_argument("--no-merge", action="store_true", help="Overwrite contract instead of merging")
    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    if "all" in steps:
        steps = ["plan", "yaml", "spec"]
    if args.url and "scrape" not in steps and steps != ["scrape"]:
        steps = ["scrape"] + steps

    contract_path = args.contract or str(contracts_dir() / f"{args.app}-contract.json")
    if "scrape" in steps and not args.url:
        parser.error("--url is required when scrape step is enabled")

    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    result = run_pipeline(
        contract_path=contract_path,
        app_slug=args.app,
        steps=steps,
        modules=modules,
        scrape_url=args.url,
        max_pages=args.max_pages,
        seed_paths=[s.strip() for s in args.seed_paths.split(",") if s.strip()],
        interact=not args.no_interact,
        merge=not args.no_merge,
    )

    print("\nPipeline complete.")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
