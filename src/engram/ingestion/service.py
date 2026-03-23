"""Ingestion orchestration and job management."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.models.connector import DataExport, IngestionJob


async def create_job(session: AsyncSession, source_type: str) -> IngestionJob:
    """Create a new ingestion job with status 'pending'."""
    job = IngestionJob(source_type=source_type, status="pending")
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> IngestionJob | None:
    """Return an ingestion job by ID, or None if not found."""
    result = await session.execute(
        select(IngestionJob).where(IngestionJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def ingest_file(
    session: AsyncSession, content: bytes, filename: str
) -> IngestionJob:
    """Save an uploaded file to a temp directory and create a tracking job.

    The actual parsing/processing pipeline will be wired up in later tasks.
    For now, the file is persisted and the job is created with status 'pending'.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="engram_ingest_"))
    dest = temp_dir / filename
    dest.write_bytes(content)

    job = await create_job(session, source_type="file")
    return job


async def register_export(
    session: AsyncSession, platform: str, export_path: str
) -> DataExport:
    """Register a data export directory for a given platform."""
    export = DataExport(platform=platform, export_path=export_path, status="pending")
    session.add(export)
    await session.flush()
    await session.refresh(export)
    return export


async def list_exports(session: AsyncSession) -> list[DataExport]:
    """List all registered data exports."""
    result = await session.execute(select(DataExport))
    return list(result.scalars().all())
