from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    AllureReportInfoResponse,
    AppDetailResponse,
    AppListResponse,
    FileContentResponse,
    FileListResponse,
    GenerateAllureReportResponse,
    PlaywrightReportInfoResponse,
)
from app.services import artifacts
from lib.allure_report import generate_allure_report

router = APIRouter(prefix="/api/apps", tags=["apps"])


@router.get("", response_model=AppListResponse)
def list_apps() -> AppListResponse:
    return AppListResponse(apps=artifacts.list_apps())


@router.get("/{slug}", response_model=AppDetailResponse)
def get_app(slug: str) -> AppDetailResponse:
    return artifacts.get_app_detail(slug)


@router.get("/{slug}/files", response_model=FileListResponse)
def list_files(
    slug: str,
    path: str = Query(default="", description="Relative path within app output"),
    recursive: bool = Query(default=False),
) -> FileListResponse:
    entries = artifacts.list_files(slug, rel_path=path, recursive=recursive)
    return FileListResponse(path=path, entries=entries)


@router.get("/{slug}/files/content", response_model=FileContentResponse)
def read_file_content(slug: str, path: str = Query(...)) -> FileContentResponse:
    content, language = artifacts.read_file_content(slug, path)
    return FileContentResponse(path=path, content=content, language=language)


@router.get("/{slug}/files/download")
def download_file(slug: str, path: str = Query(...)):
    return artifacts.download_file(slug, path)


@router.get("/{slug}/playwright-report/info", response_model=PlaywrightReportInfoResponse)
def playwright_report_info(slug: str) -> PlaywrightReportInfoResponse:
    info = artifacts.playwright_report_info(slug)
    return PlaywrightReportInfoResponse(**info)


@router.get("/{slug}/playwright-report")
def playwright_report_index(slug: str):
    return artifacts.serve_playwright_report(slug, "")


@router.get("/{slug}/playwright-report/{path:path}")
def playwright_report_file(slug: str, path: str):
    return artifacts.serve_playwright_report(slug, path)


@router.get("/{slug}/allure-report/info", response_model=AllureReportInfoResponse)
def allure_report_info(slug: str) -> AllureReportInfoResponse:
    info = artifacts.allure_report_info(slug)
    return AllureReportInfoResponse(**info)


@router.post("/{slug}/allure-report/generate", response_model=GenerateAllureReportResponse)
def allure_report_generate(slug: str) -> GenerateAllureReportResponse:
    try:
        result = generate_allure_report(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GenerateAllureReportResponse(**result)


@router.get("/{slug}/allure-report")
def allure_report_index(slug: str):
    return artifacts.serve_allure_report(slug, "")


@router.get("/{slug}/allure-report/{path:path}")
def allure_report_file(slug: str, path: str):
    return artifacts.serve_allure_report(slug, path)
