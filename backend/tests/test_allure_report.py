"""Tests for Allure report generation and serving."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib.allure_report import generate_allure_report
from lib.paths import app_output_dir


@pytest.fixture
def allure_app(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "test_allure_app"
    root = app_output_dir(slug)
    results = root / "allure-results"
    results.mkdir(parents=True)
    (results / "result.json").write_text("{}", encoding="utf-8")
    return slug


def test_generate_fails_without_results(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "empty_allure_app"
    app_output_dir(slug).mkdir(parents=True)
    with pytest.raises(ValueError, match="No Allure results"):
        generate_allure_report(slug)


def test_generate_success_mock_subprocess(allure_app):
    report_index = app_output_dir(allure_app) / "allure-report" / "index.html"

    def fake_run(cmd, cwd, capture_output, text, check):
        out_dir = Path(cwd) / "allure-report"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text("<html>Allure</html>", encoding="utf-8")
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    with patch("lib.allure_report.subprocess.run", side_effect=fake_run):
        result = generate_allure_report(allure_app)

    assert result["report_path"] == "allure-report/index.html"
    assert result["results_path"] == "allure-results"
    assert report_index.is_file()


def test_allure_report_info_no_report(allure_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{allure_app}/allure-report/info")
    assert res.status_code == 200
    data = res.json()
    assert data["results_exist"] is True
    assert data["exists"] is False


def test_allure_report_generate_endpoint(allure_app):
    client = TestClient(app)

    def fake_run(cmd, cwd, capture_output, text, check):
        out_dir = Path(cwd) / "allure-report"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text("<html>Allure</html>", encoding="utf-8")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with patch("lib.allure_report.subprocess.run", side_effect=fake_run):
        res = client.post(f"/api/apps/{allure_app}/allure-report/generate")

    assert res.status_code == 200
    assert res.json()["report_path"] == "allure-report/index.html"


def test_allure_report_generate_missing_results(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "no_results_app"
    app_output_dir(slug).mkdir(parents=True)
    client = TestClient(app)
    res = client.post(f"/api/apps/{slug}/allure-report/generate")
    assert res.status_code == 400
    assert "Allure results" in res.json()["detail"]


def test_serve_allure_report_index(allure_app):
    root = app_output_dir(allure_app)
    report_dir = root / "allure-report"
    report_dir.mkdir(parents=True)
    (report_dir / "index.html").write_text("<html><body>Allure</body></html>", encoding="utf-8")

    client = TestClient(app)
    res = client.get(f"/api/apps/{allure_app}/allure-report")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "Allure" in res.text
