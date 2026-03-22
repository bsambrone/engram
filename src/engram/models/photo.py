"""Photo models."""

from __future__ import annotations

import uuid

from sqlalchemy import ARRAY, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engram.models.base import Base, TimestampMixin, UUIDMixin


class PhotoPerson(Base):
    __tablename__ = "photo_people"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )


class Photo(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "photos"

    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_profiles.id"), nullable=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    is_reference: Mapped[bool] = mapped_column(default=False, server_default="false")

    people: Mapped[list["Person"]] = relationship(  # noqa: F821
        secondary="photo_people", viewonly=True
    )
