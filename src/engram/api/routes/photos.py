"""Photo API routes — upload, list, get, update, delete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.models.auth import AccessToken
from engram.photos.repository import PhotoRepository
from engram.photos.service import PhotoService

router = APIRouter(prefix="/photos", tags=["photos"])


# ---- Pydantic schemas -------------------------------------------------------


class PhotoOut(BaseModel):
    id: uuid.UUID
    file_path: str
    source: str | None = None
    source_ref: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_reference: bool = False

    model_config = {"from_attributes": True}


class PhotoUpdate(BaseModel):
    description: str | None = None
    tags: list[str] | None = None
    is_reference: bool | None = None


class UploadResponse(BaseModel):
    id: str
    file_path: str
    source: str | None = None
    is_reference: bool = False


# ---- Routes ------------------------------------------------------------------


@router.post("/upload", response_model=UploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    source: str | None = Query(None),
    is_reference: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Upload a photo file."""
    content = await file.read()
    service = PhotoService(session)
    result = await service.upload_photo(
        file_content=content,
        filename=file.filename or "upload.jpg",
        source=source,
        is_reference=is_reference,
    )
    await session.commit()
    return UploadResponse(**result)


@router.get("", response_model=list[PhotoOut])
async def list_photos(
    is_reference: bool | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List photos with optional filtering."""
    repo = PhotoRepository(session)
    photos = await repo.list_photos(is_reference=is_reference)
    return [PhotoOut.model_validate(p) for p in photos]


@router.get("/{photo_id}", response_model=PhotoOut)
async def get_photo(
    photo_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get a single photo by ID."""
    repo = PhotoRepository(session)
    photo = await repo.get_by_id(photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return PhotoOut.model_validate(photo)


@router.put("/{photo_id}", response_model=PhotoOut)
async def update_photo(
    photo_id: uuid.UUID,
    body: PhotoUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Update photo metadata."""
    repo = PhotoRepository(session)
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    photo = await repo.update(photo_id, **update_data)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    await session.commit()
    return PhotoOut.model_validate(photo)


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Delete a photo record."""
    repo = PhotoRepository(session)
    deleted = await repo.delete(photo_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Photo not found")
    await session.commit()
    return {"detail": "Photo deleted"}
