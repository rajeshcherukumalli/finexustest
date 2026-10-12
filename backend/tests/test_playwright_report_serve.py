"""Tests for Playwright HTML report static serving."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib.paths import app_output_dir


@pytest.fixture
def report_app(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "test_report_app"
    root = app_output_dir(slug)
    report_dir = root / "playwright-report" / "data"
    report_dir.mkdir(parents=True)
    (root / "playwright-report" / "index.html").write_text(
        "<html><body>Report</body></html>", encoding="utf-8"
    )
    (report_dir / "foo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return slug


def test_playwright_report_info_exists(report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{report_app}/playwright-report/info")
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is True
    assert data["index_path"] == "playwright-report/index.html"


def test_serve_report_index_html(report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{report_app}/playwright-report")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert res.headers.get("content-disposition", "").startswith("inline")
    assert "attachment" not in res.headers.get("content-disposition", "")
    assert "Report" in res.text


def test_serve_report_asset_png(report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{report_app}/playwright-report/data/foo.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_report_path_traversal_rejected(report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{report_app}/playwright-report/../package.json")
    assert res.status_code in (400, 404)


def test_report_missing_app():
    client = TestClient(app)
    res = client.get("/api/apps/nonexistent_app_xyz/playwright-report/info")
    assert res.status_code == 404


@pytest.fixture
def allure_report_app(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DATA_ROOT", str(tmp_path))
    slug = "test_allure_serve_app"
    root = app_output_dir(slug)
    asset_dir = root / "allure-report" / "data"
    asset_dir.mkdir(parents=True)
    (root / "allure-report" / "index.html").write_text(
        "<html><body>Allure report</body></html>", encoding="utf-8"
    )
    (asset_dir / "styles.css").write_text("body {}", encoding="utf-8")
    return slug


def test_allure_report_info_exists(allure_report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{allure_report_app}/allure-report/info")
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is True
    assert data["index_path"] == "allure-report/index.html"


def test_serve_allure_report_css(allure_report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{allure_report_app}/allure-report/data/styles.css")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/css")


def test_allure_report_path_traversal_rejected(allure_report_app):
    client = TestClient(app)
    res = client.get(f"/api/apps/{allure_report_app}/allure-report/../package.json")
    assert res.status_code in (400, 404)
