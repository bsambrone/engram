"""Tests for identity repository CRUD operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository


async def test_create_and_get_profile(db_session: AsyncSession):
    """Create a profile, then retrieve it by ID."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="test-user", description="A test profile")
    assert profile.name == "test-user"
    assert profile.description == "A test profile"
    assert profile.id is not None

    fetched = await repo.get_profile(profile.id)
    assert fetched is not None
    assert fetched.id == profile.id
    assert fetched.name == "test-user"


async def test_get_default_profile(db_session: AsyncSession):
    """get_default_profile returns first created profile."""
    repo = IdentityRepository(db_session)
    p1 = await repo.create_profile(name="first")
    await repo.create_profile(name="second")

    default = await repo.get_default_profile()
    assert default is not None
    assert default.id == p1.id


async def test_update_profile(db_session: AsyncSession):
    """Update a profile's name and description."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="original")
    updated = await repo.update_profile(profile.id, name="updated", description="new desc")
    assert updated is not None
    assert updated.name == "updated"
    assert updated.description == "new desc"


async def test_create_list_update_delete_beliefs(db_session: AsyncSession):
    """Full CRUD lifecycle for beliefs."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="belief-test")

    # Create
    belief = await repo.create_belief(
        profile.id, topic="climate", stance="concerned", confidence=0.9, source="user"
    )
    assert belief.topic == "climate"
    assert belief.source == "user"

    # List (all)
    beliefs = await repo.list_beliefs(profile.id)
    assert len(beliefs) == 1
    assert beliefs[0].id == belief.id

    # List with topic filter
    await repo.create_belief(profile.id, topic="tech", stance="optimistic", source="user")
    filtered = await repo.list_beliefs(profile.id, topic="climate")
    assert len(filtered) == 1
    assert filtered[0].topic == "climate"

    all_beliefs = await repo.list_beliefs(profile.id)
    assert len(all_beliefs) == 2

    # Update
    updated = await repo.update_belief(belief.id, stance="very concerned")
    assert updated is not None
    assert updated.stance == "very concerned"

    # Delete
    deleted = await repo.delete_belief(belief.id)
    assert deleted is True
    remaining = await repo.list_beliefs(profile.id)
    assert len(remaining) == 1

    # Delete non-existent
    deleted_again = await repo.delete_belief(belief.id)
    assert deleted_again is False


async def test_create_list_preferences(db_session: AsyncSession):
    """Create and list preferences."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="pref-test")

    pref = await repo.create_preference(
        profile.id, category="food", value="Italian", strength=0.8, source="user"
    )
    assert pref.category == "food"
    assert pref.value == "Italian"

    prefs = await repo.list_preferences(profile.id)
    assert len(prefs) == 1
    assert prefs[0].id == pref.id


async def test_update_delete_preferences(db_session: AsyncSession):
    """Update and delete preferences."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="pref-ud")

    pref = await repo.create_preference(
        profile.id, category="music", value="jazz", source="user"
    )
    updated = await repo.update_preference(pref.id, value="blues")
    assert updated is not None
    assert updated.value == "blues"

    deleted = await repo.delete_preference(pref.id)
    assert deleted is True


async def test_upsert_style(db_session: AsyncSession):
    """Upsert creates then updates style."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="style-test")

    # First upsert creates
    style = await repo.upsert_style(profile.id, tone="casual", humor_level=0.7, source="user")
    assert style.tone == "casual"
    assert style.humor_level == 0.7

    # Second upsert updates
    style2 = await repo.upsert_style(profile.id, tone="formal", formality=0.9)
    assert style2.id == style.id
    assert style2.tone == "formal"
    assert style2.formality == 0.9

    # Get style
    fetched = await repo.get_style(profile.id)
    assert fetched is not None
    assert fetched.tone == "formal"


async def test_create_list_get_snapshots(db_session: AsyncSession):
    """Create, list, and get snapshots."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="snap-test")

    snapshot_data = {"beliefs": [], "preferences": [], "style": None}
    snap = await repo.create_snapshot(profile.id, snapshot_data, label="v1")
    assert snap.label == "v1"
    assert snap.snapshot_data == snapshot_data
    assert snap.profile_id == profile.id

    # Create another
    await repo.create_snapshot(profile.id, {"beliefs": [{"topic": "test"}]}, label="v2")

    # List
    snapshots = await repo.list_snapshots(profile.id)
    assert len(snapshots) == 2
    labels = {s.label for s in snapshots}
    assert labels == {"v1", "v2"}

    # Get by ID
    fetched = await repo.get_snapshot(snap.id)
    assert fetched is not None
    assert fetched.id == snap.id
    assert fetched.label == "v1"
