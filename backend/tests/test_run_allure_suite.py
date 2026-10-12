"""Tests for headless full-suite Allure report pipeline."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib.paths import app_output_dir
from lib.playwright_run import run_allure_suite


@pytest.fixture
def allure_suite_app(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "allure_suite_app"
    root = app_output_dir(slug)
    spec_dir = root / "tests" / "scripts" / "e2e" / "auth"
    spec_dir.mkdir(parents=True)
    (spec_dir / "case.e2e.spec.ts").write_text("// spec", encoding="utf-8")
    (root / "package.json").write_text(
        '{"name":"qa","devDependencies":{"@playwright/test":"^1.60.0"}}',
        encoding="utf-8",
    )
    (root / "playwright.config.ts").write_text(
        "export default { testDir: './tests/scripts/e2e' }",
        encoding="utf-8",
    )
    contract_dest = tmp_path / "contracts" / f"{slug}-contract.json"
    contract_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(__file__).parent / "fixtures" / "nav_contract.json", contract_dest)
    return slug


def test_run_allure_suite_no_specs(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "empty_suite_app"
    root = app_output_dir(slug)
    root.mkdir(parents=True)
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "playwright.config.ts").write_text("export default {}", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="No Playwright specs"):
        run_allure_suite(slug, base_url="https://example.com")


def test_run_allure_suite_success_even_when_tests_fail(allure_suite_app):
    results_dir = app_output_dir(allure_suite_app) / "allure-results"
    report_index = app_output_dir(allure_suite_app) / "allure-report" / "index.html"

    def fake_run_command(cmd, cwd, log_line=None):
        if cmd[:3] == ["npx", "playwright", "test"]:
            results_dir.mkdir(parents=True, exist_ok=True)
            (results_dir / "result.json").write_text("{}", encoding="utf-8")
            return 1
        if cmd[:3] == ["npx", "allure", "generate"]:
            out_dir = Path(cwd) / "allure-report"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text("<html>Allure</html>", encoding="utf-8")
            return 0
        return 0

    with (
        patch("lib.playwright_run._run_command", side_effect=fake_run_command),
        patch("lib.playwright_run.ensure_node_deps"),
        patch("lib.playwright_run.ensure_allure_config", return_value=False),
        patch("lib.allure_report.subprocess.run") as mock_allure,
    ):
        def allure_subprocess(cmd, cwd, capture_output, text, check):
            out_dir = Path(cwd) / "allure-report"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text("<html>Allure</html>", encoding="utf-8")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        mock_allure.side_effect = allure_subprocess
        result = run_allure_suite(allure_suite_app, base_url="https://example.com")

    assert result["passed"] is False
    assert result["exit_code"] == 1
    assert result["artifact_path"] == "allure-report"
    assert result["report_path"] == "allure-report/index.html"
    assert report_index.is_file()


def test_run_allure_route_returns_job(allure_suite_app):
    client = TestClient(app)

    import time

    with patch("app.services.job_runner.run_allure_suite") as mock_run:
        mock_run.return_value = {
            "steps_run": ["allure"],
            "exit_code": 0,
            "passed": True,
            "report_path": "allure-report/index.html",
            "artifact_path": "allure-report",
            "allure_results_path": "allure-results",
        }
        res = client.post(
            f"/api/apps/{allure_suite_app}/run/allure",
            json={"app_slug": allure_suite_app},
        )
        assert res.status_code == 202
        job_id = res.json()["id"]
        assert res.json()["job_type"] == "allure"

        job = {}
        for _ in range(50):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.05)

    assert job["status"] == "completed"
    assert job["result"]["artifact_path"] == "allure-report"
