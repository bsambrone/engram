"""Sources API routes — owner-only."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.memory.repository import MemoryRepository
from engram.models.auth import AccessToken

router = APIRouter(prefix="/sources", tags=["sources"])


# ---- Pydantic schemas -------------------------------------------------------


class VisibilityUpdate(BaseModel):
    source_ref: str
    visibility: str


class BulkVisibilityUpdate(BaseModel):
    updates: list[VisibilityUpdate]


class SourceDelete(BaseModel):
    source_ref: str


# ---- Routes -----------------------------------------------------------------


@router.get("")
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List sources with counts and visibility breakdown."""
    repo = MemoryRepository(session)
    sources = await repo.get_sources()
    return sources


@router.put("/visibility")
async def update_visibility(
    body: VisibilityUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Change visibility for all memories from a source_ref."""
    repo = MemoryRepository(session)
    count = await repo.update_visibility_by_source_ref(body.source_ref, body.visibility)
    return {"updated": count, "source_ref": body.source_ref, "visibility": body.visibility}


@router.post("/bulk")
async def bulk_visibility(
    body: BulkVisibilityUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Bulk visibility changes for multiple source_refs."""
    repo = MemoryRepository(session)
    results = []
    for update in body.updates:
        count = await repo.update_visibility_by_source_ref(
            update.source_ref, update.visibility
        )
        results.append(
            {"source_ref": update.source_ref, "visibility": update.visibility, "updated": count}
        )
    return results


@router.delete("")
async def delete_source(
    body: SourceDelete,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Delete a source and all its memories."""
    repo = MemoryRepository(session)
    count = await repo.delete_by_source_ref(body.source_ref)
    return {"deleted": count, "source_ref": body.source_ref}
