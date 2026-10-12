"""Run generated Playwright TypeScript specs from app output directories."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from lib.allure_report import (
    ALLURE_REPORT_DIR,
    ALLURE_REPORT_INDEX,
    ALLURE_RESULTS_DIR,
    ensure_allure_config,
    generate_allure_report,
)
from lib.artifacts import spec_rel
from lib.paths import app_output_dir

log = logging.getLogger(__name__)

DEPS_MARKER = ".deps-installed"
ENV_QA_FILE = ".env.qa"


def headed_enabled() -> bool:
    return os.environ.get("PLAYWRIGHT_HEADED", "").lower() in ("1", "true", "yes")


def display_available() -> bool:
    return bool(os.environ.get("DISPLAY", "").strip())


HEADED_DOCKER_HINT = (
    "Headed browser requires a display. On Docker run:\n"
    "  xhost +local:docker\n"
    "  docker compose -f docker-compose.yml -f docker-compose.headed.yml up -d --build"
)


def resolve_scraper_headless(headed: bool) -> bool:
    """Return Playwright headless flag for scrape jobs (headed=False shows the browser)."""
    if not headed:
        return True
    if headed_enabled() or display_available():
        log.info("Scrape will run with a visible Chromium window")
        return False
    raise RuntimeError(HEADED_DOCKER_HINT)


def ensure_env_qa(app_root: Path, base_url: str) -> Path:
    env_path = app_root / ENV_QA_FILE
    line = f"QA_UI_BASE_URL={base_url.rstrip('/')}\n"
    if env_path.exists():
        current = env_path.read_text(encoding="utf-8")
        if line.strip() in current.replace("\r\n", "\n"):
            return env_path
    env_path.write_text(line, encoding="utf-8")
    log.info("Wrote %s", env_path)
    return env_path


def _needs_npm_install(app_root: Path) -> bool:
    package_json = app_root / "package.json"
    if not package_json.exists():
        return False
    marker = app_root / DEPS_MARKER
    node_modules = app_root / "node_modules"
    if not node_modules.exists():
        return True
    if not marker.exists():
        return True
    return package_json.stat().st_mtime > marker.stat().st_mtime


def _run_command(
    cmd: list[str],
    cwd: Path,
    *,
    log_line: Callable[[str], None] | None = None,
) -> int:
    log.info("Running: %s (cwd=%s)", " ".join(cmd), cwd)
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        stripped = line.rstrip("\n")
        if log_line:
            log_line(stripped)
        else:
            log.info(stripped)
    proc.wait()
    return int(proc.returncode or 0)


def ensure_node_deps(app_root: Path) -> None:
    package_json = app_root / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(
            f"No package.json in {app_root} — generate Playwright spec first"
        )

    if not _needs_npm_install(app_root):
        log.info("Node dependencies up to date in %s", app_root)
        return

    log.info("Installing npm dependencies in %s …", app_root)
    code = _run_command(["npm", "install"], app_root)
    if code != 0:
        raise RuntimeError(f"npm install failed with exit code {code}")

    log.info("Installing Playwright Chromium browser …")
    code = _run_command(["npx", "playwright", "install", "chromium"], app_root)
    if code != 0:
        raise RuntimeError(f"playwright install chromium failed with exit code {code}")

    (app_root / DEPS_MARKER).write_text("ok\n", encoding="utf-8")


def _discover_e2e_specs(app_root: Path) -> list[Path]:
    e2e_root = app_root / "tests" / "scripts" / "e2e"
    if not e2e_root.is_dir():
        return []
    return sorted(e2e_root.rglob("*.e2e.spec.ts"))


def _prepare_playwright_app(app_root: Path, base_url: str) -> None:
    for required in ("package.json", "playwright.config.ts"):
        if not (app_root / required).exists():
            raise FileNotFoundError(
                f"Missing {required} in {app_root} — generate Playwright spec first"
            )
    ensure_env_qa(app_root, base_url)
    if ensure_allure_config(app_root):
        (app_root / DEPS_MARKER).unlink(missing_ok=True)
    ensure_node_deps(app_root)


def _clear_allure_results(app_root: Path) -> None:
    results_dir = app_root / ALLURE_RESULTS_DIR
    if results_dir.exists():
        shutil.rmtree(results_dir)
        log.info("Cleared %s", results_dir)


def run_spec(
    app_slug: str,
    spec_rel_path: str,
    *,
    base_url: str,
    plan_id: str | None = None,
) -> dict:
    """Run a single Playwright spec; returns exit_code, passed, report_path."""
    if not headed_enabled():
        raise ValueError(
            "PLAYWRIGHT_HEADED is not enabled. For a visible browser on your desktop, run: "
            "xhost +local:docker && "
            "docker compose -f docker-compose.yml -f docker-compose.headed.yml up -d --build"
        )

    app_root = app_output_dir(app_slug)
    if plan_id and not spec_rel_path:
        spec_rel_path = spec_rel(plan_id)

    spec_path = app_root / spec_rel_path
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")

    _prepare_playwright_app(app_root, base_url)

    cmd = [
        "npx",
        "playwright",
        "test",
        spec_rel_path,
        "--headed",
    ]
    exit_code = _run_command(cmd, app_root)

    report_dir = app_root / "playwright-report"
    report_path = None
    index = report_dir / "index.html"
    if index.exists():
        report_path = str(index.relative_to(app_root))

    allure_results_path = None
    results_dir = app_root / ALLURE_RESULTS_DIR
    if results_dir.is_dir() and any(results_dir.rglob("*")):
        allure_results_path = ALLURE_RESULTS_DIR

    return {
        "steps_run": ["run"],
        "plan_id": plan_id,
        "artifact_path": spec_rel_path,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "report_path": report_path,
        "allure_results_path": allure_results_path,
    }


def run_allure_suite(app_slug: str, *, base_url: str) -> dict:
    """Run all E2E specs headless, generate Allure HTML, return download artifact path."""
    app_root = app_output_dir(app_slug)
    if not app_root.exists():
        raise FileNotFoundError(f"App not found: {app_slug}")

    specs = _discover_e2e_specs(app_root)
    if not specs:
        raise FileNotFoundError(
            f"No Playwright specs found under {app_root / 'tests/scripts/e2e'} — generate a spec first"
        )

    _prepare_playwright_app(app_root, base_url)
    _clear_allure_results(app_root)

    log.info("Running %d E2E spec(s) headless for Allure report", len(specs))
    exit_code = _run_command(["npx", "playwright", "test"], app_root)

    generate_allure_report(app_slug)

    return {
        "steps_run": ["allure"],
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "report_path": ALLURE_REPORT_INDEX,
        "artifact_path": ALLURE_REPORT_DIR,
        "allure_results_path": ALLURE_RESULTS_DIR,
    }
