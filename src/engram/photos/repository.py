"""Photo repository — CRUD operations for photos."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engram.models.photo import Photo


class PhotoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        file_path: str,
        source: str | None = None,
        source_ref: str | None = None,
        profile_id: uuid.UUID | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        is_reference: bool = False,
    ) -> Photo:
        """Create a new photo record."""
        photo = Photo(
            file_path=file_path,
            source=source,
            source_ref=source_ref,
            profile_id=profile_id,
            description=description,
            tags=tags,
            is_reference=is_reference,
        )
        self.session.add(photo)
        await self.session.flush()
        await self.session.refresh(photo)
        return photo

    async def get_by_id(self, photo_id: uuid.UUID) -> Photo | None:
        """Get a photo by ID with people relationship loaded."""
        result = await self.session.execute(
            select(Photo)
            .where(Photo.id == photo_id)
            .options(selectinload(Photo.people))
        )
        return result.scalar_one_or_none()

    async def list_photos(
        self,
        profile_id: uuid.UUID | None = None,
        is_reference: bool | None = None,
    ) -> list[Photo]:
        """List photos with optional filters."""
        stmt = select(Photo).order_by(Photo.created_at.desc())
        if profile_id is not None:
            stmt = stmt.where(Photo.profile_id == profile_id)
        if is_reference is not None:
            stmt = stmt.where(Photo.is_reference == is_reference)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, photo_id: uuid.UUID, **kwargs: object) -> Photo | None:
        """Partial update of a photo record."""
        photo = await self.get_by_id(photo_id)
        if photo is None:
            return None
        for key, value in kwargs.items():
            setattr(photo, key, value)
        await self.session.flush()
        await self.session.refresh(photo)
        return photo

    async def delete(self, photo_id: uuid.UUID) -> bool:
        """Delete a photo record (does not delete the file)."""
        photo = await self.get_by_id(photo_id)
        if photo is None:
            return False
        await self.session.delete(photo)
        await self.session.flush()
        return True

    async def get_reference_photos(self, profile_id: uuid.UUID) -> list[Photo]:
        """Get all reference photos for a profile."""
        result = await self.session.execute(
            select(Photo)
            .where(Photo.profile_id == profile_id, Photo.is_reference.is_(True))
            .order_by(Photo.created_at.desc())
        )
        return list(result.scalars().all())
