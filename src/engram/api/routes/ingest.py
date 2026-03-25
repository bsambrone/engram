"""Ingest API routes — owner-only."""

from __future__ import annotations

import importlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.ingestion import service as ingestion_service
from engram.models.auth import AccessToken
from engram.models.connector import IngestionJob

router = APIRouter(prefix="/ingest", tags=["ingest"])


class ExportRequest(BaseModel):
    platform: str
    export_path: str


class ExportResponse(BaseModel):
    id: uuid.UUID
    platform: str
    export_path: str
    status: str

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: uuid.UUID
    source_type: str
    status: str

    model_config = {"from_attributes": True}


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(default=20, le=100),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List ingestion jobs, newest first."""
    stmt = select(IngestionJob).order_by(IngestionJob.created_at.desc())
    if status:
        stmt = stmt.where(IngestionJob.status == status)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "source_type": j.source_type,
            "status": j.status,
            "items_processed": j.items_processed,
            "items_failed": j.items_failed,
            "error_message": j.error_message if j.status == "failed" else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.post("/export/validate")
async def validate_export(
    body: ExportRequest,
    _owner: AccessToken = Depends(require_owner),
):
    """Validate an export path without registering it."""
    export_path = Path(body.export_path)

    # Get the right parser
    parsers = {
        "gmail": "engram.ingestion.parsers.gmail:GmailExportParser",
        "reddit": "engram.ingestion.parsers.reddit:RedditExportParser",
        "facebook": "engram.ingestion.parsers.facebook:FacebookExportParser",
        "instagram": "engram.ingestion.parsers.instagram:InstagramExportParser",
    }

    parser_ref = parsers.get(body.platform)
    if not parser_ref:
        return {"valid": False, "error": f"Unknown platform: {body.platform}"}

    # Import and instantiate parser
    module_path, class_name = parser_ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    parser_class = getattr(module, class_name)
    parser = parser_class()

    valid = parser.validate(export_path)
    return {"valid": valid, "platform": body.platform, "export_path": str(export_path)}


@router.post("/file", status_code=202, response_model=JobResponse)
async def upload_file(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Upload a file for ingestion. Returns the tracking job."""
    content = await file.read()
    filename = file.filename or "upload.bin"
    job = await ingestion_service.ingest_file(session, content, filename)
    return job


@router.post("/export", status_code=201, response_model=ExportResponse)
async def register_export(
    body: ExportRequest,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Register an export directory for a platform."""
    export = await ingestion_service.register_export(
        session, body.platform, body.export_path
    )
    return export


@router.get("/status", response_model=JobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get the status of an ingestion job."""
    job = await ingestion_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/exports", response_model=list[ExportResponse])
async def list_exports(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List all registered data exports."""
    exports = await ingestion_service.list_exports(session)
    return exports
