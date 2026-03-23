"""Tests for the memory service — store, reinforce, degrade, evolve."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.service import MemoryService


@pytest.fixture
def service(db_session: AsyncSession) -> MemoryService:
    return MemoryService(db_session)


def _dummy_embedding(seed: float = 0.1) -> list[float]:
    return [seed] * 1536


async def test_store_analyzed_chunk(service: MemoryService):
    """store_analyzed_chunk creates a memory and links topics/people."""
    memory_id = await service.store_analyzed_chunk(
        content="I love hiking in the mountains",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="journal.txt",
        authorship="user_authored",
        intent="sharing experience",
        meaning="values nature and outdoor activities",
        topics=["hiking", "nature"],
        people=["John"],
        importance_score=0.8,
    )
    assert isinstance(memory_id, uuid.UUID)

    # Verify the memory was created with links
    memory = await service.repo.get_by_id(memory_id)
    assert memory is not None
    assert memory.content == "I love hiking in the mountains"
    assert memory.intent == "sharing experience"
    assert len(memory.topics) == 2
    assert len(memory.people) == 1
    topic_names = {t.name for t in memory.topics}
    assert "hiking" in topic_names
    assert "nature" in topic_names
    assert memory.people[0].name == "John"


async def test_store_analyzed_chunk_no_topics_people(service: MemoryService):
    """store_analyzed_chunk works without topics or people."""
    memory_id = await service.store_analyzed_chunk(
        content="Simple memory",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="simple.txt",
        authorship="user_authored",
    )
    memory = await service.repo.get_by_id(memory_id)
    assert memory is not None
    assert memory.topics == []
    assert memory.people == []


async def test_reinforce_increases_score(service: MemoryService):
    """reinforce increments count and boosts importance."""
    memory_id = await service.store_analyzed_chunk(
        content="Reinforce me",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="reinforce.txt",
        authorship="user_authored",
        importance_score=0.5,
    )
    result = await service.reinforce(memory_id)
    assert result["reinforcement_count"] == 1
    assert result["importance_score"] == 0.55
    assert "last_reinforced_at" in result

    # Reinforce again
    result2 = await service.reinforce(memory_id)
    assert result2["reinforcement_count"] == 2
    assert result2["importance_score"] == pytest.approx(0.6)


async def test_reinforce_not_found(service: MemoryService):
    """reinforce returns error dict for non-existent memory."""
    result = await service.reinforce(uuid.uuid4())
    assert result == {"error": "not_found"}


async def test_degrade_lowers_confidence(service: MemoryService):
    """degrade lowers confidence by 0.2 each call."""
    memory_id = await service.store_analyzed_chunk(
        content="Degrade me",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="degrade.txt",
        authorship="user_authored",
    )
    result = await service.degrade(memory_id)
    assert result["confidence"] == 0.8
    assert result["status"] == "active"


async def test_degrade_marks_degraded_below_threshold(service: MemoryService):
    """degrade marks status as 'degraded' when confidence < 0.3."""
    memory_id = await service.store_analyzed_chunk(
        content="Will be degraded",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="degraded.txt",
        authorship="user_authored",
    )
    # Degrade 4 times: 1.0 -> 0.8 -> 0.6 -> 0.4 -> 0.2
    await service.degrade(memory_id)
    await service.degrade(memory_id)
    await service.degrade(memory_id)
    result = await service.degrade(memory_id)
    assert result["confidence"] == pytest.approx(0.2, abs=0.01)
    assert result["status"] == "degraded"


async def test_degrade_not_found(service: MemoryService):
    """degrade returns error dict for non-existent memory."""
    result = await service.degrade(uuid.uuid4())
    assert result == {"error": "not_found"}


async def test_evolve_creates_child(service: MemoryService):
    """evolve marks parent as 'evolved' and creates a child memory."""
    parent_id = await service.store_analyzed_chunk(
        content="Original belief",
        embedding=_dummy_embedding(),
        source="file",
        source_ref="evolve.txt",
        authorship="user_authored",
        meaning="initial meaning",
        topics=["philosophy"],
    )
    result = await service.evolve(parent_id, "Updated belief", "evolved meaning")
    assert result["parent_status"] == "evolved"
    assert result["parent_id"] == str(parent_id)
    child_id = uuid.UUID(result["child_id"])

    # Verify parent is evolved
    parent = await service.repo.get_by_id(parent_id)
    assert parent is not None
    assert parent.status == "evolved"

    # Verify child
    child = await service.repo.get_by_id(child_id)
    assert child is not None
    assert child.content == "Updated belief"
    assert child.meaning == "evolved meaning"
    assert child.parent_memory_id == parent_id
    assert child.status == "active"
    # Child should inherit topics
    assert len(child.topics) == 1
    assert child.topics[0].name == "philosophy"


async def test_evolve_not_found(service: MemoryService):
    """evolve returns error dict for non-existent memory."""
    result = await service.evolve(uuid.uuid4(), "new content")
    assert result == {"error": "not_found"}


async def test_get_stats(service: MemoryService):
    """get_stats delegates to repo and returns valid stats."""
    await service.store_analyzed_chunk(
        content="Stats test",
        embedding=_dummy_embedding(),
        source="test",
        source_ref="stats.txt",
        authorship="user_authored",
    )
    stats = await service.get_stats()
    assert stats["total_memories"] >= 1
    assert isinstance(stats["by_source"], dict)
    assert isinstance(stats["topic_count"], int)
    assert isinstance(stats["person_count"], int)
