"""Tests for identity service."""

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService


async def test_get_or_create_default_profile(db_session: AsyncSession):
    """Creates a default profile if none exists, returns it on second call."""
    service = IdentityService(db_session)

    # First call creates
    profile = await service.get_or_create_default_profile()
    assert profile.name == "default"
    assert profile.id is not None

    # Second call returns same profile
    profile2 = await service.get_or_create_default_profile()
    assert profile2.id == profile.id


async def test_get_full_identity(db_session: AsyncSession):
    """get_full_identity returns beliefs, preferences, and style."""
    service = IdentityService(db_session)
    repo = IdentityRepository(db_session)

    profile = await service.get_or_create_default_profile()

    # Add some data
    await repo.create_belief(profile.id, topic="ethics", stance="utilitarian", source="user")
    await repo.create_preference(profile.id, category="language", value="Python", source="user")
    await repo.upsert_style(profile.id, tone="direct", humor_level=0.3, source="user")

    identity = await service.get_full_identity(profile.id)

    assert "beliefs" in identity
    assert "preferences" in identity
    assert "style" in identity

    assert len(identity["beliefs"]) == 1
    assert identity["beliefs"][0]["topic"] == "ethics"
    assert identity["beliefs"][0]["stance"] == "utilitarian"

    assert len(identity["preferences"]) == 1
    assert identity["preferences"][0]["category"] == "language"
    assert identity["preferences"][0]["value"] == "Python"

    assert identity["style"] is not None
    assert identity["style"]["tone"] == "direct"
    assert identity["style"]["humor_level"] == 0.3


async def test_get_full_identity_empty(db_session: AsyncSession):
    """get_full_identity with no data returns empty lists and None style."""
    service = IdentityService(db_session)
    profile = await service.get_or_create_default_profile()

    identity = await service.get_full_identity(profile.id)
    assert identity["beliefs"] == []
    assert identity["preferences"] == []
    assert identity["style"] is None


async def test_take_snapshot(db_session: AsyncSession):
    """take_snapshot serializes current identity."""
    service = IdentityService(db_session)
    repo = IdentityRepository(db_session)

    profile = await service.get_or_create_default_profile()
    await repo.create_belief(profile.id, topic="tech", stance="pro-AI", source="user")

    snapshot = await service.take_snapshot(profile.id, label="snapshot-1")
    assert snapshot.label == "snapshot-1"
    assert snapshot.profile_id == profile.id
    assert "beliefs" in snapshot.snapshot_data
    assert len(snapshot.snapshot_data["beliefs"]) == 1
    assert snapshot.snapshot_data["beliefs"][0]["topic"] == "tech"
