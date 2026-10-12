from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.models.schemas import AppDetailResponse, AppSummary, FileEntry
from lib.paths import app_output_dir, data_root
from lib.workspace import sync_contract_artifact

SKIP_DIRS = {"node_modules", ".git", "test-results", "__pycache__"}
TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".ts", ".txt", ".example", ".spec.ts"}
LANGUAGE_MAP = {
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".ts": "typescript",
    ".txt": "text",
}

REPORT_MIME_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

PLAYWRIGHT_REPORT_DIR = "playwright-report"
PLAYWRIGHT_REPORT_INDEX = f"{PLAYWRIGHT_REPORT_DIR}/index.html"
ALLURE_REPORT_DIR = "allure-report"
ALLURE_REPORT_INDEX = f"{ALLURE_REPORT_DIR}/index.html"


def _safe_path(app_slug: str, rel_path: str = "") -> Path:
    root = app_output_dir(app_slug).resolve()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"App not found: {app_slug}")

    target = (root / rel_path).resolve() if rel_path else root
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def list_apps() -> list[AppSummary]:
    output_root = data_root() / "output"
    if not output_root.exists():
        return []

    apps: list[AppSummary] = []
    for app_dir in sorted(output_root.iterdir()):
        if not app_dir.is_dir():
            continue
        manifest = _read_manifest(app_dir)
        apps.append(
            AppSummary(
                slug=app_dir.name,
                manifest=manifest,
                generated_at=manifest.get("generated_at") if manifest else None,
                flows_count=len(manifest.get("flows_generated", [])) if manifest else 0,
            )
        )
    return apps


def _read_manifest(app_dir: Path) -> dict | None:
    manifest_path = app_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def get_app_detail(app_slug: str) -> AppDetailResponse:
    sync_contract_artifact(app_slug)
    root = app_output_dir(app_slug)
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"App not found: {app_slug}")

    manifest = _read_manifest(root)
    file_count = sum(1 for _ in root.rglob("*") if _.is_file() and "node_modules" not in _.parts)
    return AppDetailResponse(slug=app_slug, manifest=manifest, file_count=file_count)


def list_files(app_slug: str, rel_path: str = "", recursive: bool = False) -> list[FileEntry]:
    sync_contract_artifact(app_slug)
    target = _safe_path(app_slug, rel_path)
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries: list[FileEntry] = []
    if recursive:
        for item in sorted(target.rglob("*")):
            if any(part in SKIP_DIRS for part in item.parts):
                continue
            if item == target:
                continue
            rel = str(item.relative_to(app_output_dir(app_slug)))
            entries.append(
                FileEntry(
                    path=rel,
                    name=item.name,
                    is_dir=item.is_dir(),
                    size=item.stat().st_size if item.is_file() else None,
                )
            )
    else:
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in SKIP_DIRS:
                continue
            rel = str(item.relative_to(app_output_dir(app_slug)))
            entries.append(
                FileEntry(
                    path=rel,
                    name=item.name,
                    is_dir=item.is_dir(),
                    size=item.stat().st_size if item.is_file() else None,
                )
            )
    return entries


def read_file_content(app_slug: str, rel_path: str) -> tuple[str, str]:
    target = _safe_path(app_slug, rel_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = target.suffix
    if target.name.endswith(".spec.ts"):
        suffix = ".ts"
    if suffix not in TEXT_EXTENSIONS and not target.name.endswith(".spec.ts"):
        raise HTTPException(status_code=400, detail="File type not viewable")

    content = target.read_text(encoding="utf-8", errors="replace")
    language = LANGUAGE_MAP.get(suffix, "text")
    return content, language


def download_file(app_slug: str, rel_path: str) -> StreamingResponse:
    target = _safe_path(app_slug, rel_path)

    if target.is_file():
        data = target.read_bytes()
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
        )

    if target.is_dir():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in target.rglob("*"):
                if file_path.is_file() and "node_modules" not in file_path.parts:
                    arcname = str(file_path.relative_to(target))
                    zf.write(file_path, arcname)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{target.name}.zip"'},
        )

    raise HTTPException(status_code=404, detail="Path not found")


def _report_media_type(path: Path) -> str:
    return REPORT_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


def playwright_report_info(app_slug: str) -> dict:
    index = _safe_path(app_slug, PLAYWRIGHT_REPORT_INDEX)
    exists = index.is_file()
    return {
        "exists": exists,
        "index_path": PLAYWRIGHT_REPORT_INDEX if exists else None,
    }


def serve_playwright_report(app_slug: str, subpath: str = "") -> FileResponse:
    """Serve Playwright HTML report files inline for iframe viewing."""
    return _serve_static_report(app_slug, PLAYWRIGHT_REPORT_DIR, PLAYWRIGHT_REPORT_INDEX, subpath)


def _resolve_static_report_file(app_slug: str, report_dir: str, subpath: str = "") -> Path:
    rel = f"{report_dir}/{subpath}" if subpath else f"{report_dir}/index.html"
    target = _safe_path(app_slug, rel)
    if target.is_dir():
        target = target / "index.html"
        if not str(target.resolve()).startswith(str(app_output_dir(app_slug).resolve())):
            raise HTTPException(status_code=400, detail="Invalid path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Report file not found")
    return target


def _serve_static_report(
    app_slug: str,
    report_dir: str,
    default_index: str,
    subpath: str = "",
) -> FileResponse:
    if not subpath or subpath.endswith("/"):
        subpath = (subpath.rstrip("/") + "/index.html") if subpath else "index.html"
    target = _resolve_static_report_file(app_slug, report_dir, subpath)
    media_type = _report_media_type(target)
    if media_type == "text/html":
        media_type = "text/html; charset=utf-8"
    return FileResponse(
        path=target,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


def allure_report_info(app_slug: str) -> dict:
    from lib.allure_report import allure_report_info_dict

    return allure_report_info_dict(app_slug)


def serve_allure_report(app_slug: str, subpath: str = "") -> FileResponse:
    """Serve generated Allure HTML report inline for iframe viewing."""
    return _serve_static_report(app_slug, ALLURE_REPORT_DIR, ALLURE_REPORT_INDEX, subpath)
