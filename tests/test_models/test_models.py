"""Tests for ORM models."""

import hashlib
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.models.auth import AccessToken
from engram.models.identity import Belief, IdentityProfile
from engram.models.memory import Memory, Person, Topic


@pytest.mark.asyncio
async def test_create_memory(db_session: AsyncSession):
    """Test creating a Memory record and reading it back."""
    memory = Memory(
        content="The user loves hiking in the mountains.",
        source="chat",
        importance_score=0.8,
        confidence=0.9,
    )
    db_session.add(memory)
    await db_session.flush()

    result = await db_session.execute(select(Memory).where(Memory.id == memory.id))
    fetched = result.scalar_one()

    assert fetched.content == "The user loves hiking in the mountains."
    assert fetched.source == "chat"
    assert fetched.importance_score == pytest.approx(0.8)
    assert fetched.confidence == pytest.approx(0.9)
    assert fetched.visibility == "private"
    assert fetched.status == "active"
    assert fetched.reinforcement_count == 0
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_memory_with_topics_and_people(db_session: AsyncSession):
    """Test M2M relationships between Memory, Topic, and Person."""
    topic = Topic(name="hiking")
    person = Person(name="Alice", relationship_type="friend")
    memory = Memory(
        content="Went hiking with Alice last weekend.",
        source="journal",
    )
    memory.topics.append(topic)
    memory.people.append(person)
    db_session.add(memory)
    await db_session.flush()

    result = await db_session.execute(select(Memory).where(Memory.id == memory.id))
    fetched = result.scalar_one()

    assert len(fetched.topics) == 1
    assert fetched.topics[0].name == "hiking"
    assert len(fetched.people) == 1
    assert fetched.people[0].name == "Alice"


@pytest.mark.asyncio
async def test_memory_parent_child(db_session: AsyncSession):
    """Test self-referential parent/child relationship on Memory."""
    parent = Memory(content="Parent memory")
    child = Memory(content="Child memory", parent=parent)
    db_session.add_all([parent, child])
    await db_session.flush()

    result = await db_session.execute(select(Memory).where(Memory.id == parent.id))
    fetched_parent = result.scalar_one()
    assert len(fetched_parent.children) == 1
    assert fetched_parent.children[0].content == "Child memory"


@pytest.mark.asyncio
async def test_create_identity_profile_with_beliefs(db_session: AsyncSession):
    """Test creating an IdentityProfile with associated Beliefs."""
    profile = IdentityProfile(
        name="primary",
        description="Main identity profile",
    )
    belief = Belief(
        profile=profile,
        topic="climate change",
        stance="Deeply concerned about environmental impact",
        confidence=0.95,
        source="conversation",
        first_seen=datetime(2024, 1, 15),
    )
    db_session.add_all([profile, belief])
    await db_session.flush()

    result = await db_session.execute(
        select(IdentityProfile).where(IdentityProfile.id == profile.id)
    )
    fetched = result.scalar_one()

    assert fetched.name == "primary"
    assert len(fetched.beliefs) == 1
    assert fetched.beliefs[0].topic == "climate change"
    assert fetched.beliefs[0].confidence == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_create_access_token(db_session: AsyncSession):
    """Test creating an AccessToken record."""
    raw_token = uuid.uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    token = AccessToken(
        name="my-api-token",
        token_hash=token_hash,
        access_level="admin",
    )
    db_session.add(token)
    await db_session.flush()

    result = await db_session.execute(
        select(AccessToken).where(AccessToken.token_hash == token_hash)
    )
    fetched = result.scalar_one()

    assert fetched.name == "my-api-token"
    assert fetched.access_level == "admin"
    assert fetched.created_at is not None
    assert fetched.expires_at is None
    assert fetched.revoked_at is None


@pytest.mark.asyncio
async def test_encryption_helpers():
    """Test encrypt/decrypt roundtrip."""
    from cryptography.fernet import Fernet

    from engram.config import settings
    from engram.encryption import decrypt, encrypt

    # Temporarily set a key for testing
    original = settings.engram_encryption_key
    settings.engram_encryption_key = Fernet.generate_key().decode()

    try:
        plaintext = "super-secret-credentials"
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext
    finally:
        settings.engram_encryption_key = original
