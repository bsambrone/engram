"""Identity-related models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engram.models.base import Base, TimestampMixin, UUIDMixin


class BeliefMemory(Base):
    __tablename__ = "belief_memories"

    belief_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("beliefs.id", ondelete="CASCADE"), primary_key=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )


class PreferenceMemory(Base):
    __tablename__ = "preference_memories"

    preference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("preferences.id", ondelete="CASCADE"), primary_key=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )


class IdentityProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "identity_profiles"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    beliefs: Mapped[list["Belief"]] = relationship(back_populates="profile")
    preferences: Mapped[list["Preference"]] = relationship(back_populates="profile")
    style_profile: Mapped["StyleProfile | None"] = relationship(
        back_populates="profile", uselist=False
    )


class Belief(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "beliefs"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_profiles.id", ondelete="CASCADE"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    stance: Mapped[str | None] = mapped_column(Text, nullable=True)
    nuance: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped["IdentityProfile"] = relationship(back_populates="beliefs")
    supporting_memories: Mapped[list["Memory"]] = relationship(  # noqa: F821
        secondary="belief_memories", viewonly=True
    )


class Preference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "preferences"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_profiles.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    strength: Mapped[float | None] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped["IdentityProfile"] = relationship(back_populates="preferences")
    supporting_memories: Mapped[list["Memory"]] = relationship(  # noqa: F821
        secondary="preference_memories", viewonly=True
    )


class StyleProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "style_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_profiles.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    humor_level: Mapped[float | None] = mapped_column(nullable=True)
    verbosity: Mapped[float | None] = mapped_column(nullable=True)
    formality: Mapped[float | None] = mapped_column(nullable=True)
    vocabulary_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped["IdentityProfile"] = relationship(back_populates="style_profile")


class IdentitySnapshot(UUIDMixin, Base):
    __tablename__ = "identity_snapshots"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_profiles.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
