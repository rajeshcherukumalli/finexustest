from __future__ import annotations

import json
import logging
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import JobResponse, JobResult, JobType
from generators.spec_generator import generate_spec_for_plan
from generators.test_plan_generator import generate_test_plan_for_intent
from generators.testcase_generator import generate_testcases_for_plan
from lib.contract import load_contract
from lib.paths import app_output_dir, contracts_dir, ensure_app_dirs
from lib.artifacts import spec_rel
from lib.playwright_run import run_allure_suite, run_spec as run_playwright_spec
from lib.workspace import ensure_workspace, get_plan, resolve_contract_path
from pipeline import run_pipeline

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_active_job_id: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_dir(job_id: str) -> Path:
    from lib.paths import jobs_dir

    path = jobs_dir() / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_status(job_id: str) -> dict | None:
    status_path = _job_dir(job_id) / "status.json"
    if not status_path.exists():
        return None
    return json.loads(status_path.read_text(encoding="utf-8"))


def _write_status(job_id: str, data: dict) -> None:
    (_job_dir(job_id) / "status.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def _attach_job_logger(job_id: str) -> logging.Handler:
    log_path = _job_dir(job_id) / "job.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return handler


def _detach_job_logger(handler: logging.Handler) -> None:
    root = logging.getLogger()
    root.removeHandler(handler)
    handler.close()


def _contract_path_for_app(app_slug: str, filename: str | None = None) -> str:
    path = resolve_contract_path(app_slug, filename)
    if not path.exists():
        raise FileNotFoundError(f"Contract not found: {path}")
    return str(path)


def _run_scrape(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    filename = request.get("contract_filename") or f"{app_slug}-contract.json"
    contract_path = str(contracts_dir() / filename)
    result = run_pipeline(
        contract_path=contract_path,
        app_slug=app_slug,
        steps=["scrape"],
        scrape_url=request["url"],
        max_pages=request.get("max_pages", 20),
        headed=bool(request.get("headed", False)),
        seed_paths=request.get("seed_paths"),
        interact=request.get("interact", True),
        merge=request.get("merge", True),
    )
    ensure_workspace(app_slug, contract_path=contract_path)
    return {
        "steps_run": result["steps_run"],
        "manifest": result.get("manifest"),
        "artifact_path": contract_path,
    }


def _run_plan(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    contract_path = _contract_path_for_app(app_slug)
    contract = load_contract(contract_path)
    plan_id, plan_path = generate_test_plan_for_intent(
        contract, app_slug, request["user_intent"]
    )
    rel = str(plan_path.relative_to(app_output_dir(app_slug)))
    return {
        "steps_run": ["plan"],
        "plan_id": plan_id,
        "artifact_path": rel,
    }


def _run_testcase(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    plan_id = request["plan_id"]
    plan = get_plan(app_slug, plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")

    contract_path = _contract_path_for_app(app_slug)
    contract = load_contract(contract_path)
    plan_path = app_output_dir(app_slug) / plan["plan_path"]
    paths = generate_testcases_for_plan(
        contract, app_slug, plan_path, skip_overlap=True, plan_id=plan_id
    )
    return {
        "steps_run": ["yaml"],
        "plan_id": plan_id,
        "flows": [plan_id],
        "artifact_path": str(paths[0].relative_to(app_output_dir(app_slug))) if paths else None,
    }


def _run_allure(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    contract_path = _contract_path_for_app(app_slug)
    contract = load_contract(contract_path)
    return run_allure_suite(app_slug, base_url=contract.base_url)


def _run_playwright(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    plan_id = request["plan_id"]
    plan = get_plan(app_slug, plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")

    spec_path = request.get("spec_path")
    if not spec_path:
        specs = plan.get("specs") or []
        if specs:
            spec_path = specs[0].get("path")
        if not spec_path:
            spec_path = spec_rel(plan_id)

    contract_path = _contract_path_for_app(app_slug)
    contract = load_contract(contract_path)
    return run_playwright_spec(
        app_slug,
        spec_path,
        base_url=contract.base_url,
        plan_id=plan_id,
    )


def _run_spec(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    plan_id = request["plan_id"]
    plan = get_plan(app_slug, plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")

    contract_path = _contract_path_for_app(app_slug)
    contract = load_contract(contract_path)
    paths = generate_spec_for_plan(
        contract,
        app_slug,
        plan_id,
        use_llm_spec=bool(request.get("use_llm_spec")),
    )
    spec_paths = [p for p in paths if p.name.endswith(".e2e.spec.ts")]
    rel = str(spec_paths[0].relative_to(app_output_dir(app_slug))) if spec_paths else None
    return {
        "steps_run": ["spec"],
        "plan_id": plan_id,
        "flow_id": plan_id,
        "flows": [plan_id],
        "artifact_path": rel,
    }


def _run_pipeline(request: dict[str, Any]) -> dict[str, Any]:
    app_slug = request["app_slug"]
    filename = request.get("contract_filename") or f"{app_slug}-contract.json"
    contract_path = request.get("contract_path") or str(contracts_dir() / filename)
    steps = request.get("steps") or ["plan", "yaml", "spec"]
    if "all" in steps:
        steps = ["plan", "yaml", "spec"]
    if request.get("url") and "scrape" not in steps:
        steps = ["scrape"] + steps
    if "scrape" in steps and not request.get("url"):
        raise ValueError("url is required when scrape step is enabled")

    result = run_pipeline(
        contract_path=contract_path,
        app_slug=app_slug,
        steps=steps,
        modules=request.get("modules"),
        scrape_url=request.get("url"),
        max_pages=request.get("max_pages", 20),
        headed=bool(request.get("headed", False)),
        seed_paths=request.get("seed_paths"),
        interact=request.get("interact", True),
        merge=request.get("merge", True),
    )
    if "scrape" in steps:
        ensure_workspace(app_slug, contract_path=contract_path)
    return result


def _execute_job(job_type: JobType, request: dict[str, Any]) -> dict[str, Any]:
    handlers = {
        "scrape": _run_scrape,
        "plan": _run_plan,
        "testcase": _run_testcase,
        "spec": _run_spec,
        "run": _run_playwright,
        "allure": _run_allure,
        "pipeline": _run_pipeline,
    }
    return handlers[job_type](request)


def _run_job(job_id: str, job_type: JobType, request: dict[str, Any]) -> None:
    global _active_job_id
    handler = _attach_job_logger(job_id)
    try:
        data = _read_status(job_id) or {}
        data["status"] = "running"
        data["started_at"] = _utc_now()
        _write_status(job_id, data)

        result = _execute_job(job_type, request)

        data = _read_status(job_id) or {}
        data["status"] = "completed"
        data["finished_at"] = _utc_now()
        data["result"] = result
        _write_status(job_id, data)
        _log.info("Job %s completed", job_id)
    except Exception as exc:
        _log.error("Job %s failed: %s", job_id, exc)
        data = _read_status(job_id) or {}
        data["status"] = "failed"
        data["finished_at"] = _utc_now()
        data["error"] = str(exc)
        data["traceback"] = traceback.format_exc()
        _write_status(job_id, data)
    finally:
        _detach_job_logger(handler)
        with _lock:
            if _active_job_id == job_id:
                _active_job_id = None


def start_job(job_type: JobType, request: dict[str, Any]) -> JobResponse:
    global _active_job_id

    app_slug = request.get("app_slug", "unknown")

    with _lock:
        if _active_job_id is not None:
            active = _read_status(_active_job_id)
            if active and active.get("status") in ("queued", "running"):
                raise RuntimeError(
                    f"Job {_active_job_id} is already running. Wait for it to finish."
                )
            _active_job_id = None

        job_id = uuid.uuid4().hex[:12]
        _active_job_id = job_id

    status = {
        "id": job_id,
        "job_type": job_type,
        "status": "queued",
        "created_at": _utc_now(),
        "started_at": None,
        "finished_at": None,
        "app_slug": app_slug,
        "request": request,
        "result": None,
        "error": None,
    }
    _write_status(job_id, status)

    thread = threading.Thread(
        target=_run_job, args=(job_id, job_type, request), daemon=True
    )
    thread.start()

    return job_to_response(status)


def start_pipeline_job(request: Any) -> JobResponse:
    data = request.model_dump() if hasattr(request, "model_dump") else dict(request)
    return start_job("pipeline", data)


def start_scrape_job(request: Any) -> JobResponse:
    data = request.model_dump() if hasattr(request, "model_dump") else dict(request)
    data["steps"] = ["scrape"]
    return start_job("scrape", data)


def job_to_response(data: dict) -> JobResponse:
    result_data = data.get("result")
    result = None
    if result_data:
        result = JobResult(
            manifest=result_data.get("manifest"),
            steps_run=result_data.get("steps_run", []),
            flows=result_data.get("flows", []),
            artifact_path=result_data.get("artifact_path"),
            plan_id=result_data.get("plan_id"),
            flow_id=result_data.get("flow_id"),
            exit_code=result_data.get("exit_code"),
            passed=result_data.get("passed"),
            report_path=result_data.get("report_path"),
            allure_results_path=result_data.get("allure_results_path"),
        )
    return JobResponse(
        id=data["id"],
        job_type=data.get("job_type", "pipeline"),
        status=data["status"],
        created_at=data["created_at"],
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        app_slug=data["app_slug"],
        request=data.get("request", {}),
        result=result,
        error=data.get("error"),
    )


def get_job(job_id: str) -> JobResponse | None:
    data = _read_status(job_id)
    if not data:
        return None
    return job_to_response(data)


def list_jobs(limit: int = 50) -> list[JobResponse]:
    from lib.paths import jobs_dir

    root = jobs_dir()
    if not root.exists():
        return []

    jobs: list[JobResponse] = []
    for job_dir in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not job_dir.is_dir():
            continue
        data = _read_status(job_dir.name)
        if data:
            jobs.append(job_to_response(data))
        if len(jobs) >= limit:
            break
    return jobs


def read_job_logs(job_id: str, offset: int = 0) -> tuple[str, int, bool]:
    log_path = _job_dir(job_id) / "job.log"
    if not log_path.exists():
        return "", offset, True

    content = log_path.read_text(encoding="utf-8", errors="replace")
    if offset >= len(content):
        return "", offset, True
    return content[offset:], len(content), True
