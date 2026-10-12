"""Output path helpers."""

import os
from pathlib import Path

PIPELINE_VERSION = "1.0.0"

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def data_root() -> Path:
    """Persistent data directory (output, contracts, jobs)."""
    if env := os.getenv("QA_DATA_ROOT"):
        return Path(env)
    # Local: qa-automation/data — Docker: /data (backend parent is /)
    return _BACKEND_DIR.parent / "data"


def contracts_dir() -> Path:
    path = data_root() / "contracts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def jobs_dir() -> Path:
    path = data_root() / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_output_dir(app_slug: str) -> Path:
    return data_root() / "output" / app_slug


def ensure_app_dirs(app_slug: str) -> Path:
    root = app_output_dir(app_slug)
    for sub in (
        "tests/testplan",
        "tests/testcases",
        "tests/scripts/e2e",
        "tests/scripts/pages",
        "tests/scripts/helpers",
        "tests/scripts/fixtures/auth",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root
