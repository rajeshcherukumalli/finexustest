from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend root is on sys.path for pipeline imports
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT.parent / ".env")
load_dotenv()

from app.api.routes import apps, jobs, workspace  # noqa: E402
from app.models.schemas import HealthResponse  # noqa: E402
from lib.paths import data_root  # noqa: E402

app = FastAPI(title="QA Automation API", version="1.0.0")

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(apps.router)
app.include_router(workspace.router)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    import shutil
    return HealthResponse(
        status="ok",
        claude_configured=bool(shutil.which("claude")),
        data_root=str(data_root()),
    )
