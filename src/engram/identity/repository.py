"""Identity repository — CRUD operations for all identity tables."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.models.identity import (
    Belief,
    IdentityProfile,
    IdentitySnapshot,
    Preference,
    StyleProfile,
)


class IdentityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- Profile ----------------------------------------------------------------

    async def create_profile(self, name: str, description: str | None = None) -> IdentityProfile:
        profile = IdentityProfile(name=name, description=description)
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def get_profile(self, profile_id: uuid.UUID) -> IdentityProfile | None:
        result = await self.session.execute(
            select(IdentityProfile).where(IdentityProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_default_profile(self) -> IdentityProfile | None:
        result = await self.session.execute(
            select(IdentityProfile).order_by(IdentityProfile.created_at).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_profile(
        self, profile_id: uuid.UUID, **kwargs: object
    ) -> IdentityProfile | None:
        profile = await self.get_profile(profile_id)
        if profile is None:
            return None
        for key, value in kwargs.items():
            setattr(profile, key, value)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    # ---- Beliefs ----------------------------------------------------------------

    async def create_belief(self, profile_id: uuid.UUID, **kwargs: object) -> Belief:
        belief = Belief(profile_id=profile_id, **kwargs)
        self.session.add(belief)
        await self.session.flush()
        await self.session.refresh(belief)
        return belief

    async def list_beliefs(
        self, profile_id: uuid.UUID, topic: str | None = None
    ) -> list[Belief]:
        stmt = select(Belief).where(Belief.profile_id == profile_id)
        if topic:
            stmt = stmt.where(Belief.topic == topic)
        stmt = stmt.order_by(Belief.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_belief(self, belief_id: uuid.UUID) -> Belief | None:
        result = await self.session.execute(select(Belief).where(Belief.id == belief_id))
        return result.scalar_one_or_none()

    async def update_belief(self, belief_id: uuid.UUID, **kwargs: object) -> Belief | None:
        belief = await self.get_belief(belief_id)
        if belief is None:
            return None
        for key, value in kwargs.items():
            setattr(belief, key, value)
        await self.session.flush()
        await self.session.refresh(belief)
        return belief

    async def delete_belief(self, belief_id: uuid.UUID) -> bool:
        belief = await self.get_belief(belief_id)
        if belief is None:
            return False
        await self.session.delete(belief)
        await self.session.flush()
        return True

    # ---- Preferences ------------------------------------------------------------

    async def create_preference(self, profile_id: uuid.UUID, **kwargs: object) -> Preference:
        pref = Preference(profile_id=profile_id, **kwargs)
        self.session.add(pref)
        await self.session.flush()
        await self.session.refresh(pref)
        return pref

    async def list_preferences(self, profile_id: uuid.UUID) -> list[Preference]:
        result = await self.session.execute(
            select(Preference)
            .where(Preference.profile_id == profile_id)
            .order_by(Preference.created_at)
        )
        return list(result.scalars().all())

    async def get_preference(self, preference_id: uuid.UUID) -> Preference | None:
        result = await self.session.execute(
            select(Preference).where(Preference.id == preference_id)
        )
        return result.scalar_one_or_none()

    async def update_preference(
        self, preference_id: uuid.UUID, **kwargs: object
    ) -> Preference | None:
        pref = await self.get_preference(preference_id)
        if pref is None:
            return None
        for key, value in kwargs.items():
            setattr(pref, key, value)
        await self.session.flush()
        await self.session.refresh(pref)
        return pref

    async def delete_preference(self, preference_id: uuid.UUID) -> bool:
        pref = await self.get_preference(preference_id)
        if pref is None:
            return False
        await self.session.delete(pref)
        await self.session.flush()
        return True

    # ---- Style ------------------------------------------------------------------

    async def upsert_style(self, profile_id: uuid.UUID, **kwargs: object) -> StyleProfile:
        result = await self.session.execute(
            select(StyleProfile).where(StyleProfile.profile_id == profile_id)
        )
        style = result.scalar_one_or_none()
        if style is None:
            style = StyleProfile(profile_id=profile_id, **kwargs)
            self.session.add(style)
        else:
            for key, value in kwargs.items():
                setattr(style, key, value)
        await self.session.flush()
        await self.session.refresh(style)
        return style

    async def get_style(self, profile_id: uuid.UUID) -> StyleProfile | None:
        result = await self.session.execute(
            select(StyleProfile).where(StyleProfile.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    # ---- Snapshots --------------------------------------------------------------

    async def create_snapshot(
        self, profile_id: uuid.UUID, snapshot_data: dict, label: str | None = None
    ) -> IdentitySnapshot:
        snapshot = IdentitySnapshot(
            profile_id=profile_id, snapshot_data=snapshot_data, label=label
        )
        self.session.add(snapshot)
        await self.session.flush()
        await self.session.refresh(snapshot)
        return snapshot

    async def list_snapshots(self, profile_id: uuid.UUID) -> list[IdentitySnapshot]:
        result = await self.session.execute(
            select(IdentitySnapshot)
            .where(IdentitySnapshot.profile_id == profile_id)
            .order_by(IdentitySnapshot.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_snapshot(self, snapshot_id: uuid.UUID) -> IdentitySnapshot | None:
        result = await self.session.execute(
            select(IdentitySnapshot).where(IdentitySnapshot.id == snapshot_id)
        )
        return result.scalar_one_or_none()
