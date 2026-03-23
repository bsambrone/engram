"""Tests for the memory repository — CRUD, search, topics, stats."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.repository import MemoryRepository, _recency_score, _reinforcement_score


@pytest.fixture
def repo(db_session: AsyncSession) -> MemoryRepository:
    return MemoryRepository(db_session)


def _dummy_embedding(seed: float = 0.1) -> list[float]:
    """Generate a deterministic 1536-d embedding."""
    return [seed] * 1536


async def test_create_memory(repo: MemoryRepository):
    """Creating a memory returns a Memory with an ID."""
    memory = await repo.create(
        content="Test memory content",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="test.txt",
        authorship="user_authored",
        importance_score=0.7,
        confidence=1.0,
    )
    assert memory.id is not None
    assert isinstance(memory.id, uuid.UUID)
    assert memory.content == "Test memory content"
    assert memory.source == "file"
    assert memory.importance_score == 0.7


async def test_get_by_id(repo: MemoryRepository):
    """get_by_id returns the memory with topics and people loaded."""
    memory = await repo.create(
        content="Findable memory",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="find.txt",
    )
    found = await repo.get_by_id(memory.id)
    assert found is not None
    assert found.id == memory.id
    assert found.content == "Findable memory"
    # Relationships should be loaded (empty lists, but not lazy-load errors)
    assert found.topics == []
    assert found.people == []


async def test_get_by_id_not_found(repo: MemoryRepository):
    """get_by_id returns None for a non-existent ID."""
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


async def test_update_memory(repo: MemoryRepository):
    """update() partially updates a memory's fields."""
    memory = await repo.create(
        content="Original",
        embedding=_dummy_embedding(),
        visibility="active",
    )
    updated = await repo.update(memory.id, visibility="hidden", importance_score=0.9)
    assert updated is not None
    assert updated.visibility == "hidden"
    assert updated.importance_score == 0.9
    assert updated.content == "Original"


async def test_delete_memory(repo: MemoryRepository):
    """delete() removes a memory and returns True."""
    memory = await repo.create(content="To delete", embedding=_dummy_embedding())
    deleted = await repo.delete(memory.id)
    assert deleted is True
    assert await repo.get_by_id(memory.id) is None


async def test_delete_nonexistent(repo: MemoryRepository):
    """delete() returns False for a non-existent ID."""
    deleted = await repo.delete(uuid.uuid4())
    assert deleted is False


async def test_search_memories(repo: MemoryRepository):
    """search() returns memories ranked by composite score."""
    # Use very distinct embeddings to ensure reliable ranking
    emb_a = [0.99] * 768 + [0.01] * 768  # first half high, second half low
    emb_b = [0.01] * 768 + [0.99] * 768  # opposite pattern

    await repo.create(
        content="Unique search target alpha",
        embedding=emb_a,
        source="file",
        importance_score=0.8,
        confidence=1.0,
        status="active",
    )
    await repo.create(
        content="Unique search target beta",
        embedding=emb_b,
        source="file",
        importance_score=0.5,
        confidence=1.0,
        status="active",
    )

    # Search with embedding close to emb_a
    results = await repo.search(emb_a, limit=10)
    assert len(results) >= 1
    # The closest match to emb_a should be "alpha"
    contents = [m.content for m in results]
    assert "Unique search target alpha" in contents
    # Alpha should rank before beta
    alpha_idx = contents.index("Unique search target alpha")
    if "Unique search target beta" in contents:
        beta_idx = contents.index("Unique search target beta")
        assert alpha_idx < beta_idx


async def test_get_or_create_topic(repo: MemoryRepository):
    """get_or_create_topic finds existing or creates new."""
    topic1 = await repo.get_or_create_topic("testing")
    assert topic1.name == "testing"
    assert topic1.id is not None

    # Second call should return the same topic
    topic2 = await repo.get_or_create_topic("testing")
    assert topic2.id == topic1.id


async def test_get_or_create_person(repo: MemoryRepository):
    """get_or_create_person finds existing or creates new."""
    person1 = await repo.get_or_create_person("Alice")
    assert person1.name == "Alice"
    person2 = await repo.get_or_create_person("Alice")
    assert person2.id == person1.id


async def test_link_topics_to_memory(repo: MemoryRepository):
    """link_topics creates M2M associations."""
    memory = await repo.create(content="Linked memory", embedding=_dummy_embedding())
    topic = await repo.get_or_create_topic("linked-topic")
    await repo.link_topics(memory.id, [topic.id])

    # Re-fetch to verify the relationship
    found = await repo.get_by_id(memory.id)
    assert found is not None
    assert len(found.topics) == 1
    assert found.topics[0].name == "linked-topic"


async def test_link_people_to_memory(repo: MemoryRepository):
    """link_people creates M2M associations."""
    memory = await repo.create(content="People memory", embedding=_dummy_embedding())
    person = await repo.get_or_create_person("Bob")
    await repo.link_people(memory.id, [person.id])

    found = await repo.get_by_id(memory.id)
    assert found is not None
    assert len(found.people) == 1
    assert found.people[0].name == "Bob"


async def test_get_stats(repo: MemoryRepository):
    """get_stats returns counts by source, topic count, person count."""
    await repo.create(
        content="Stats memory",
        source="file",
        source_ref="stats.txt",
        status="active",
    )
    stats = await repo.get_stats()
    assert "total_memories" in stats
    assert "by_source" in stats
    assert "topic_count" in stats
    assert "person_count" in stats
    assert stats["total_memories"] >= 1


def test_recency_score_none():
    """_recency_score returns 0.5 for None timestamp."""
    assert _recency_score(None, 365) == 0.5


def test_reinforcement_score_capped():
    """_reinforcement_score caps at 1.0."""
    assert _reinforcement_score(0) == 0.0
    assert _reinforcement_score(5) == 0.5
    assert _reinforcement_score(10) == 1.0
    assert _reinforcement_score(20) == 1.0
