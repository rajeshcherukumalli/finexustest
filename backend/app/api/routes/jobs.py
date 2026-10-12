from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    JobListResponse,
    JobResponse,
    LogResponse,
    PipelineJobRequest,
    ScrapeJobRequest,
)
from app.services import job_runner

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/scrape", response_model=JobResponse, status_code=202)
def create_scrape_job(request: ScrapeJobRequest) -> JobResponse:
    try:
        return job_runner.start_scrape_job(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/pipeline", response_model=JobResponse, status_code=202)
def create_pipeline_job(request: PipelineJobRequest) -> JobResponse:
    try:
        return job_runner.start_pipeline_job(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=JobListResponse)
def list_jobs(limit: int = 50) -> JobListResponse:
    return JobListResponse(jobs=job_runner.list_jobs(limit=limit))


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = job_runner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/logs", response_model=LogResponse)
def get_job_logs(job_id: str, offset: int = 0) -> LogResponse:
    job = job_runner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    content, new_offset, eof = job_runner.read_job_logs(job_id, offset=offset)
    return LogResponse(offset=new_offset, content=content, eof=eof)
