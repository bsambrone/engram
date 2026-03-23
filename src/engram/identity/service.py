"""Identity service — higher-level identity operations."""

from __future__ import annotations

import uuid

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

    async def get_full_identity(self, profile_id: uuid.UUID) -> dict:
        """Return a dict with beliefs, preferences, and style for a profile."""
        beliefs = await self.repo.list_beliefs(profile_id)
        preferences = await self.repo.list_preferences(profile_id)
        style = await self.repo.get_style(profile_id)

        return {
            "beliefs": [
                {
                    "id": str(b.id),
                    "topic": b.topic,
                    "stance": b.stance,
                    "nuance": b.nuance,
                    "confidence": b.confidence,
                    "source": b.source,
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
