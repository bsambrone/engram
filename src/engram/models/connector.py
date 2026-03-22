"""Connector-related models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from engram.models.base import Base, TimestampMixin, UUIDMixin


class ConnectorConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "connector_configs"

    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    credentials: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    status: Mapped[str] = mapped_column(String(20), server_default="inactive")


class IngestionJob(UUIDMixin, Base):
    __tablename__ = "ingestion_jobs"

    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    items_processed: Mapped[int] = mapped_column(default=0, server_default="0")
    items_failed: Mapped[int] = mapped_column(default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
