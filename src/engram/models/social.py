"""Social models — relationships, locations, and life events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from engram.models.base import Base, TimestampMixin, UUIDMixin


class Relationship(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "relationships"

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    connected_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    interaction_score: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0.0"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Location(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    first_visited: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_visited: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LifeEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "life_events"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    people: Mapped[str | None] = mapped_column(Text, nullable=True)
