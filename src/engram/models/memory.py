"""Memory-related models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engram.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass


class MemoryTopic(Base):
    __tablename__ = "memory_topics"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )


class MemoryPerson(Base):
    __tablename__ = "memory_people"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )


class Memory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memories"

    parent_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memories.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authorship: Mapped[str | None] = mapped_column(String(20), nullable=True)
    importance_score: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    reinforcement_count: Mapped[int] = mapped_column(default=0, server_default="0")
    last_reinforced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), server_default="active")
    status: Mapped[str] = mapped_column(String(20), server_default="active")

    # Self-referential relationships
    children: Mapped[list["Memory"]] = relationship(
        back_populates="parent", foreign_keys="[Memory.parent_memory_id]"
    )
    parent: Mapped["Memory | None"] = relationship(
        back_populates="children",
        remote_side="[Memory.id]",
        foreign_keys="[Memory.parent_memory_id]",
    )

    # Many-to-many relationships
    topics: Mapped[list["Topic"]] = relationship(
        secondary="memory_topics", back_populates="memories"
    )
    people: Mapped[list["Person"]] = relationship(
        secondary="memory_people", back_populates="memories"
    )


class Topic(UUIDMixin, Base):
    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    memories: Mapped[list["Memory"]] = relationship(
        secondary="memory_topics", back_populates="topics"
    )


class Person(UUIDMixin, Base):
    __tablename__ = "people"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    memories: Mapped[list["Memory"]] = relationship(
        secondary="memory_people", back_populates="people"
    )
