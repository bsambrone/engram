"""Ingest API routes — owner-only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.ingestion import service as ingestion_service
from engram.models.auth import AccessToken

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
