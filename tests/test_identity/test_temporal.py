"""Tests for the temporal identity system — evolving beliefs, as-of-date queries, timelines."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService

# ---- Belief temporal queries --------------------------------------------------


async def test_list_beliefs_current_only(db_session: AsyncSession):
    """list_beliefs with no as_of_date returns only current (valid_until=NULL) beliefs."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="temporal-current")

    # Create an archived belief (valid_until is set)
    past = datetime(2025, 1, 1)
    now = datetime(2025, 6, 1)
    await repo.create_belief(
        profile.id,
        topic="climate",
        stance="skeptical",
        source="inferred",
        valid_from=past,
        valid_until=now,
    )
    # Create a current belief (valid_until is NULL)
    await repo.create_belief(
        profile.id,
        topic="climate",
        stance="concerned",
        source="inferred",
        valid_from=now,
        valid_until=None,
    )

    current = await repo.list_beliefs(profile.id)
    assert len(current) == 1
    assert current[0].stance == "concerned"


async def test_list_beliefs_as_of_date(db_session: AsyncSession):
    """list_beliefs with as_of_date returns beliefs active on that date."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="temporal-asof")

    t1 = datetime(2025, 1, 1)
    t2 = datetime(2025, 6, 1)

    # Version 1: active from t1 to t2
    await repo.create_belief(
        profile.id,
        topic="AI",
        stance="cautious",
        source="inferred",
        valid_from=t1,
        valid_until=t2,
    )
    # Version 2: active from t2 onwards
    await repo.create_belief(
        profile.id,
        topic="AI",
        stance="optimistic",
        source="inferred",
        valid_from=t2,
        valid_until=None,
    )

    # Query as of March 2025: should get v1
    march = datetime(2025, 3, 15)
    beliefs_march = await repo.list_beliefs(profile.id, as_of_date=march)
    assert len(beliefs_march) == 1
    assert beliefs_march[0].stance == "cautious"

    # Query as of August 2025: should get v2
    august = datetime(2025, 8, 15)
    beliefs_august = await repo.list_beliefs(profile.id, as_of_date=august)
    assert len(beliefs_august) == 1
    assert beliefs_august[0].stance == "optimistic"


async def test_list_beliefs_as_of_date_pre_temporal(db_session: AsyncSession):
    """Beliefs with NULL valid_from/valid_until (pre-temporal records) appear in as-of queries."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="temporal-legacy")

    # Legacy belief with no temporal fields
    await repo.create_belief(
        profile.id,
        topic="ethics",
        stance="utilitarian",
        source="user",
    )

    # As-of query should still include this belief (NULL valid_from is treated as always valid)
    result = await repo.list_beliefs(profile.id, as_of_date=datetime(2025, 6, 1))
    assert len(result) == 1
    assert result[0].stance == "utilitarian"


# ---- Belief evolve -----------------------------------------------------------


async def test_evolve_belief(db_session: AsyncSession):
    """evolve_belief archives old and creates new version."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="temporal-evolve")

    original = await repo.create_belief(
        profile.id,
        topic="remote-work",
        stance="against",
        confidence=0.7,
        source="inferred",
        valid_from=datetime(2024, 1, 1),
        valid_until=None,
    )

    new = await repo.evolve_belief(
        original.id,
        new_stance="in-favor",
        new_confidence=0.9,
    )

    # Old belief should be archived
    old = await repo.get_belief(original.id)
    assert old is not None
    assert old.valid_until is not None

    # New belief should be current
    assert new.stance == "in-favor"
    assert new.confidence == 0.9
    assert new.valid_from is not None
    assert new.valid_until is None
    assert new.topic == "remote-work"
    assert new.source == "inferred"

    # Current list should only show the new one
    current = await repo.list_beliefs(profile.id)
    assert len(current) == 1
    assert current[0].id == new.id


async def test_evolve_belief_preserves_unchanged_fields(db_session: AsyncSession):
    """evolve_belief preserves fields that are not explicitly changed."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="temporal-preserve")

    original = await repo.create_belief(
        profile.id,
        topic="testing",
        stance="important",
        nuance="unit tests are essential",
        confidence=0.8,
        source="inferred",
        valid_from=datetime(2024, 6, 1),
    )

    # Only change stance, leave nuance and confidence
    new = await repo.evolve_belief(original.id, new_stance="critical")
    assert new.stance == "critical"
    assert new.nuance == "unit tests are essential"
    assert new.confidence == 0.8


# ---- Preference temporal queries ---------------------------------------------


async def test_list_preferences_current_only(db_session: AsyncSession):
    """list_preferences with no as_of_date returns only current preferences."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="pref-temporal")

    past = datetime(2025, 1, 1)
    now = datetime(2025, 6, 1)

    await repo.create_preference(
        profile.id,
        category="food",
        value="Italian",
        source="inferred",
        valid_from=past,
        valid_until=now,
    )
    await repo.create_preference(
        profile.id,
        category="food",
        value="Japanese",
        source="inferred",
        valid_from=now,
        valid_until=None,
    )

    current = await repo.list_preferences(profile.id)
    assert len(current) == 1
    assert current[0].value == "Japanese"


async def test_list_preferences_as_of_date(db_session: AsyncSession):
    """list_preferences with as_of_date returns preferences active on that date."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="pref-asof")

    t1 = datetime(2025, 1, 1)
    t2 = datetime(2025, 6, 1)

    await repo.create_preference(
        profile.id,
        category="music",
        value="jazz",
        source="inferred",
        valid_from=t1,
        valid_until=t2,
    )
    await repo.create_preference(
        profile.id,
        category="music",
        value="classical",
        source="inferred",
        valid_from=t2,
        valid_until=None,
    )

    prefs_march = await repo.list_preferences(profile.id, as_of_date=datetime(2025, 3, 1))
    assert len(prefs_march) == 1
    assert prefs_march[0].value == "jazz"


# ---- Preference evolve -------------------------------------------------------


async def test_evolve_preference(db_session: AsyncSession):
    """evolve_preference archives old and creates new version."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="pref-evolve")

    original = await repo.create_preference(
        profile.id,
        category="language",
        value="Python",
        strength=0.8,
        source="inferred",
        valid_from=datetime(2024, 1, 1),
    )

    new = await repo.evolve_preference(
        original.id,
        new_value="Rust",
        new_strength=0.9,
    )

    old = await repo.get_preference(original.id)
    assert old is not None
    assert old.valid_until is not None

    assert new.value == "Rust"
    assert new.strength == 0.9
    assert new.valid_from is not None
    assert new.valid_until is None

    current = await repo.list_preferences(profile.id)
    assert len(current) == 1
    assert current[0].id == new.id


# ---- Style temporal queries --------------------------------------------------


async def test_get_style_current_only(db_session: AsyncSession):
    """get_style with no as_of_date returns only current (valid_until=NULL) style."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="style-temporal")

    # Create a current style
    style = await repo.upsert_style(profile.id, tone="casual", source="inferred")
    assert style is not None

    current = await repo.get_style(profile.id)
    assert current is not None
    assert current.tone == "casual"


# ---- Belief timeline ---------------------------------------------------------


async def test_get_belief_timeline(db_session: AsyncSession):
    """get_belief_timeline returns all versions ordered chronologically."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="timeline-test")

    t1 = datetime(2024, 1, 1)
    t2 = datetime(2024, 6, 1)
    t3 = datetime(2025, 1, 1)

    await repo.create_belief(
        profile.id,
        topic="coffee",
        stance="hates it",
        source="inferred",
        valid_from=t1,
        valid_until=t2,
    )
    await repo.create_belief(
        profile.id,
        topic="coffee",
        stance="tolerates it",
        source="inferred",
        valid_from=t2,
        valid_until=t3,
    )
    await repo.create_belief(
        profile.id,
        topic="coffee",
        stance="loves it",
        source="inferred",
        valid_from=t3,
        valid_until=None,
    )

    timeline = await repo.get_belief_timeline(profile.id, topic="coffee")
    assert len(timeline) == 3
    assert timeline[0].stance == "hates it"
    assert timeline[1].stance == "tolerates it"
    assert timeline[2].stance == "loves it"


async def test_get_belief_timeline_with_date_range(db_session: AsyncSession):
    """get_belief_timeline with start/end filters correctly."""
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="timeline-range")

    t1 = datetime(2024, 1, 1)
    t2 = datetime(2024, 6, 1)
    t3 = datetime(2025, 1, 1)

    await repo.create_belief(
        profile.id,
        topic="tea",
        stance="dislikes",
        source="inferred",
        valid_from=t1,
        valid_until=t2,
    )
    await repo.create_belief(
        profile.id,
        topic="tea",
        stance="neutral",
        source="inferred",
        valid_from=t2,
        valid_until=t3,
    )
    await repo.create_belief(
        profile.id,
        topic="tea",
        stance="enjoys",
        source="inferred",
        valid_from=t3,
        valid_until=None,
    )

    # Only beliefs active after 2024-04-01 and starting before 2024-08-01
    timeline = await repo.get_belief_timeline(
        profile.id,
        topic="tea",
        start=datetime(2024, 4, 1),
        end=datetime(2024, 8, 1),
    )
    assert len(timeline) == 2
    stances = [b.stance for b in timeline]
    assert "dislikes" in stances  # valid_until=t2 > start
    assert "neutral" in stances   # valid_from=t2 <= end


# ---- Service temporal integration --------------------------------------------


async def test_get_full_identity_as_of_date(db_session: AsyncSession):
    """get_full_identity with as_of_date returns identity as of that date."""
    service = IdentityService(db_session)
    repo = IdentityRepository(db_session)

    profile = await service.get_or_create_default_profile()

    t1 = datetime(2025, 1, 1)
    t2 = datetime(2025, 6, 1)

    await repo.create_belief(
        profile.id,
        topic="work",
        stance="office-first",
        source="inferred",
        valid_from=t1,
        valid_until=t2,
    )
    await repo.create_belief(
        profile.id,
        topic="work",
        stance="remote-first",
        source="inferred",
        valid_from=t2,
        valid_until=None,
    )

    # Identity as of March 2025
    identity_march = await service.get_full_identity(profile.id, as_of_date=datetime(2025, 3, 1))
    assert len(identity_march["beliefs"]) == 1
    assert identity_march["beliefs"][0]["stance"] == "office-first"

    # Identity as of September 2025
    identity_sept = await service.get_full_identity(profile.id, as_of_date=datetime(2025, 9, 1))
    assert len(identity_sept["beliefs"]) == 1
    assert identity_sept["beliefs"][0]["stance"] == "remote-first"


async def test_full_identity_includes_temporal_fields(db_session: AsyncSession):
    """get_full_identity includes valid_from and valid_until in its output."""
    service = IdentityService(db_session)
    repo = IdentityRepository(db_session)

    profile = await repo.create_profile(name="temporal-fields-test")

    now = datetime(2025, 6, 1)
    await repo.create_belief(
        profile.id,
        topic="testing",
        stance="important",
        source="inferred",
        valid_from=now,
        valid_until=None,
    )

    identity = await service.get_full_identity(profile.id)
    assert len(identity["beliefs"]) == 1
    belief = identity["beliefs"][0]
    assert "valid_from" in belief
    assert "valid_until" in belief
    assert belief["valid_from"] == now.isoformat()
    assert belief["valid_until"] is None


async def test_snapshot_after_evolve_captures_current_state(db_session: AsyncSession):
    """Taking a snapshot after evolving a belief captures only the current version."""
    service = IdentityService(db_session)
    repo = IdentityRepository(db_session)

    profile = await repo.create_profile(name="snapshot-evolve")

    original = await repo.create_belief(
        profile.id,
        topic="framework",
        stance="Django",
        confidence=0.7,
        source="inferred",
        valid_from=datetime(2024, 1, 1),
    )

    await repo.evolve_belief(original.id, new_stance="FastAPI", new_confidence=0.9)

    snapshot = await service.take_snapshot(profile.id, label="post-evolve")
    beliefs = snapshot.snapshot_data["beliefs"]
    assert len(beliefs) == 1
    assert beliefs[0]["stance"] == "FastAPI"
