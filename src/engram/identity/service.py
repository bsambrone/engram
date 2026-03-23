"""Identity service — higher-level identity operations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository


class IdentityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IdentityRepository(session)

    async def get_or_create_default_profile(self):
        """Return the first profile, or create one named 'default'."""
        profile = await self.repo.get_default_profile()
        if profile is not None:
            return profile
        return await self.repo.create_profile(name="default")

    async def get_full_identity(
        self,
        profile_id: uuid.UUID,
        as_of_date: datetime | None = None,
    ) -> dict:
        """Return a dict with beliefs, preferences, and style for a profile.

        If as_of_date is provided, returns the identity as it was on that date.
        """
        beliefs = await self.repo.list_beliefs(profile_id, as_of_date=as_of_date)
        preferences = await self.repo.list_preferences(profile_id, as_of_date=as_of_date)
        style = await self.repo.get_style(profile_id, as_of_date=as_of_date)

        return {
            "beliefs": [
                {
                    "id": str(b.id),
                    "topic": b.topic,
                    "stance": b.stance,
                    "nuance": b.nuance,
                    "confidence": b.confidence,
                    "source": b.source,
                    "valid_from": b.valid_from.isoformat() if b.valid_from else None,
                    "valid_until": b.valid_until.isoformat() if b.valid_until else None,
                }
                for b in beliefs
            ],
            "preferences": [
                {
                    "id": str(p.id),
                    "category": p.category,
                    "value": p.value,
                    "strength": p.strength,
                    "source": p.source,
                    "valid_from": p.valid_from.isoformat() if p.valid_from else None,
                    "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                }
                for p in preferences
            ],
            "style": (
                {
                    "tone": style.tone,
                    "humor_level": style.humor_level,
                    "verbosity": style.verbosity,
                    "formality": style.formality,
                    "vocabulary_notes": style.vocabulary_notes,
                    "communication_patterns": style.communication_patterns,
                    "source": style.source,
                }
                if style
                else None
            ),
        }

    async def take_snapshot(self, profile_id: uuid.UUID, label: str | None = None):
        """Serialize the current identity state and store as a snapshot."""
        identity = await self.get_full_identity(profile_id)
        return await self.repo.create_snapshot(
            profile_id=profile_id, snapshot_data=identity, label=label
        )
