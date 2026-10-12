"""Allure report generation and config helpers for Playwright app output."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from lib.paths import app_output_dir

log = logging.getLogger(__name__)


def _run_command(cmd: list[str], cwd: Path) -> int:
    log.info("Running: %s (cwd=%s)", " ".join(cmd), cwd)
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if proc.stdout:
        log.info(proc.stdout.strip())
    if proc.stderr:
        log.warning(proc.stderr.strip())
    return int(proc.returncode or 0)

ALLURE_RESULTS_DIR = "allure-results"
ALLURE_REPORT_DIR = "allure-report"
ALLURE_REPORT_INDEX = f"{ALLURE_REPORT_DIR}/index.html"

ALLURE_DEPS = {
    "allure-playwright": "^3.0.0",
    "allure-commandline": "^2.34.0",
}


def allure_results_exist(app_root: Path) -> bool:
    results = app_root / ALLURE_RESULTS_DIR
    if not results.is_dir():
        return False
    return any(results.rglob("*"))


def allure_report_exists(app_root: Path) -> bool:
    return (app_root / ALLURE_REPORT_INDEX).is_file()


def ensure_allure_config(app_root: Path) -> bool:
    """Ensure package.json and playwright.config.ts include Allure. Returns True if changed."""
    changed = False

    package_json = app_root / "package.json"
    if package_json.exists():
        data = json.loads(package_json.read_text(encoding="utf-8"))
        deps = data.setdefault("devDependencies", {})
        for name, version in ALLURE_DEPS.items():
            if name not in deps:
                deps[name] = version
                changed = True
        if changed:
            package_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            log.info("Updated %s with Allure dependencies", package_json)

    config_path = app_root / "playwright.config.ts"
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        if "allure-playwright" not in text:
            needle = "['html', { open: 'never' }],"
            if needle in text:
                text = text.replace(
                    needle,
                    needle
                    + "\n    ['allure-playwright', { resultsDir: 'allure-results' }],",
                )
            elif "reporter:" in text and "['list']" in text:
                text = text.replace(
                    "reporter: [['list']",
                    "reporter: [['list'], ['allure-playwright', { resultsDir: 'allure-results' }]",
                )
            else:
                log.warning("Could not patch Allure reporter into %s", config_path)
                return changed
            config_path.write_text(text, encoding="utf-8")
            changed = True
            log.info("Patched Allure reporter into %s", config_path)

    return changed


def generate_allure_report(app_slug: str) -> dict:
    app_root = app_output_dir(app_slug)
    if not app_root.exists():
        raise FileNotFoundError(f"App not found: {app_slug}")

    ensure_allure_config(app_root)

    if not allure_results_exist(app_root):
        raise ValueError(
            "No Allure results found. Run Play first to collect allure-results."
        )

    code = _run_command(
        [
            "npx",
            "allure",
            "generate",
            ALLURE_RESULTS_DIR,
            "-o",
            ALLURE_REPORT_DIR,
            "--clean",
        ],
        app_root,
    )
    if code != 0:
        raise RuntimeError(f"allure generate failed with exit code {code}")

    if not allure_report_exists(app_root):
        raise RuntimeError("allure generate completed but allure-report/index.html is missing")

    return {
        "report_path": ALLURE_REPORT_INDEX,
        "results_path": ALLURE_RESULTS_DIR,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def allure_report_info_dict(app_slug: str) -> dict:
    app_root = app_output_dir(app_slug)
    if not app_root.exists():
        return {
            "exists": False,
            "results_exist": False,
            "index_path": None,
            "results_path": None,
        }
    index_exists = allure_report_exists(app_root)
    results_exist = allure_results_exist(app_root)
    return {
        "exists": index_exists,
        "results_exist": results_exist,
        "index_path": ALLURE_REPORT_INDEX if index_exists else None,
        "results_path": ALLURE_RESULTS_DIR if results_exist else None,
    }
