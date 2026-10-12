from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AllureJobRequest,
    ContractInfoResponse,
    PlanJobRequest,
    RunSpecJobRequest,
    SpecJobRequest,
    TestcaseJobRequest,
    WorkspaceResponse,
)
from app.services import job_runner
from lib.contract import load_contract
from lib.paths import ensure_app_dirs
from lib.workspace import (
    ensure_workspace,
    resolve_contract_path,
    sync_contract_artifact,
    sync_plans_from_disk,
)

router = APIRouter(prefix="/api/apps", tags=["workspace"])


def _contract_info(app_slug: str) -> ContractInfoResponse:
    path = resolve_contract_path(app_slug)
    if not path.exists():
        return ContractInfoResponse(
            app_slug=app_slug,
            contract_path=str(path),
            exists=False,
        )
    contract = load_contract(path)
    return ContractInfoResponse(
        app_slug=app_slug,
        contract_path=str(path),
        exists=True,
        base_url=contract.base_url,
        app_name=contract.app_name,
        page_count=len(contract.pages),
        scraped_at=contract.scraped_at,
    )


@router.get("/{slug}/workspace", response_model=WorkspaceResponse)
def get_workspace(slug: str) -> WorkspaceResponse:
    ensure_app_dirs(slug)
    sync_contract_artifact(slug)
    ws = sync_plans_from_disk(slug)
    info = _contract_info(slug)
    return WorkspaceResponse(
        app_slug=slug,
        contract_path=ws.get("contract_path"),
        contract_exists=info.exists,
        base_url=info.base_url,
        page_count=info.page_count,
        plans=ws.get("plans", []),
    )


@router.get("/{slug}/contract", response_model=ContractInfoResponse)
def get_contract(slug: str) -> ContractInfoResponse:
    return _contract_info(slug)


@router.post("/{slug}/generate/plan", status_code=202)
def generate_plan(slug: str, body: PlanJobRequest):
    if body.app_slug != slug:
        raise HTTPException(status_code=400, detail="app_slug mismatch")
    info = _contract_info(slug)
    if not info.exists:
        raise HTTPException(status_code=404, detail="Contract not found — extract contract first")
    if not body.user_intent.strip():
        raise HTTPException(status_code=400, detail="user_intent is required")
    try:
        return job_runner.start_job("plan", body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{slug}/generate/testcase", status_code=202)
def generate_testcase(slug: str, body: TestcaseJobRequest):
    if body.app_slug != slug:
        raise HTTPException(status_code=400, detail="app_slug mismatch")
    if not body.plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")
    try:
        return job_runner.start_job("testcase", body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{slug}/generate/spec", status_code=202)
def generate_spec(slug: str, body: SpecJobRequest):
    if body.app_slug != slug:
        raise HTTPException(status_code=400, detail="app_slug mismatch")
    if not body.plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")
    try:
        return job_runner.start_job("spec", body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{slug}/run/spec", status_code=202)
def run_spec(slug: str, body: RunSpecJobRequest):
    if body.app_slug != slug:
        raise HTTPException(status_code=400, detail="app_slug mismatch")
    if not body.plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")
    info = _contract_info(slug)
    if not info.exists:
        raise HTTPException(status_code=404, detail="Contract not found — extract contract first")
    try:
        return job_runner.start_job("run", body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{slug}/run/allure", status_code=202)
def run_allure(slug: str, body: AllureJobRequest):
    if body.app_slug != slug:
        raise HTTPException(status_code=400, detail="app_slug mismatch")
    info = _contract_info(slug)
    if not info.exists:
        raise HTTPException(status_code=404, detail="Contract not found — extract contract first")
    try:
        return job_runner.start_job("allure", body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
