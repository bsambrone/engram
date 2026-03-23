"""Integration test: memory reinforcement, degradation, and evolution.

Exercises the full lifecycle of a memory through reinforcement (importance grows),
degradation (confidence drops, eventually marked "degraded"), and evolution
(parent marked "evolved", child created with new meaning).
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.service import MemoryService

EMBEDDING_DIM = 1536
DETERMINISTIC_EMBEDDING = [0.1] * EMBEDDING_DIM


@pytest.fixture
def service(db_session: AsyncSession) -> MemoryService:
    return MemoryService(db_session)


async def _create_memory(
    service: MemoryService,
    *,
    content: str = "Evolution test memory",
    importance_score: float = 0.5,
    topics: list[str] | None = None,
    people: list[str] | None = None,
) -> uuid.UUID:
    """Helper to create a memory with known fields."""
    return await service.store_analyzed_chunk(
        content=content,
        embedding=DETERMINISTIC_EMBEDDING,
        source="file",
        source_ref=f"evolution-{uuid.uuid4().hex[:8]}.txt",
        authorship="user_authored",
        importance_score=importance_score,
        meaning="original meaning",
        topics=topics or [],
        people=people or [],
    )


async def test_reinforce_increases_importance(service: MemoryService):
    """Single reinforcement increases importance by 0.05 and increments count."""
    memory_id = await _create_memory(service, importance_score=0.5)

    result = await service.reinforce(memory_id)

    assert result["reinforcement_count"] == 1
    assert result["importance_score"] == pytest.approx(0.55)
    assert "last_reinforced_at" in result

    # Verify in DB
    memory = await service.repo.get_by_id(memory_id)
    assert memory is not None
    assert memory.reinforcement_count == 1
    assert memory.importance_score == pytest.approx(0.55)
    assert memory.last_reinforced_at is not None


async def test_multiple_reinforcements(service: MemoryService):
    """Multiple reinforcements accumulate importance (capped at 1.0)."""
    memory_id = await _create_memory(service, importance_score=0.5)

    for i in range(1, 6):
        result = await service.reinforce(memory_id)
        assert result["reinforcement_count"] == i
        expected = min(0.5 + 0.05 * i, 1.0)
        assert result["importance_score"] == pytest.approx(expected)


async def test_reinforce_caps_at_one(service: MemoryService):
    """Importance score never exceeds 1.0 regardless of reinforcement count."""
    memory_id = await _create_memory(service, importance_score=0.95)

    result = await service.reinforce(memory_id)
    assert result["importance_score"] == 1.0

    result = await service.reinforce(memory_id)
    assert result["importance_score"] == 1.0


async def test_degrade_lowers_confidence(service: MemoryService):
    """Single degradation lowers confidence by 0.2."""
    memory_id = await _create_memory(service)

    # Memory starts with confidence 1.0 (set by store_analyzed_chunk)
    result = await service.degrade(memory_id)

    assert result["confidence"] == pytest.approx(0.8)
    assert result["status"] == "active"


async def test_degrade_marks_degraded_below_threshold(service: MemoryService):
    """Repeated degradation marks memory as 'degraded' when confidence < 0.3."""
    memory_id = await _create_memory(service)

    # Degrade: 1.0 -> 0.8 -> 0.6 -> 0.4 -> 0.2
    result1 = await service.degrade(memory_id)
    assert result1["confidence"] == pytest.approx(0.8)
    assert result1["status"] == "active"

    result2 = await service.degrade(memory_id)
    assert result2["confidence"] == pytest.approx(0.6)
    assert result2["status"] == "active"

    result3 = await service.degrade(memory_id)
    assert result3["confidence"] == pytest.approx(0.4)
    assert result3["status"] == "active"

    result4 = await service.degrade(memory_id)
    assert result4["confidence"] == pytest.approx(0.2)
    assert result4["status"] == "degraded"

    # Verify in DB
    memory = await service.repo.get_by_id(memory_id)
    assert memory is not None
    assert memory.confidence == pytest.approx(0.2)
    assert memory.status == "degraded"


async def test_degrade_confidence_floors_at_zero(service: MemoryService):
    """Confidence never goes below 0.0."""
    memory_id = await _create_memory(service)

    # Degrade 6 times: 1.0 -> 0.8 -> 0.6 -> 0.4 -> 0.2 -> 0.0 -> 0.0
    for _ in range(6):
        result = await service.degrade(memory_id)

    assert result["confidence"] == pytest.approx(0.0)
    assert result["status"] == "degraded"


async def test_evolve_creates_child_and_marks_parent(service: MemoryService):
    """evolve() marks parent as 'evolved' and creates a child with new content."""
    parent_id = await _create_memory(
        service,
        content="I think Python is the best language.",
        topics=["programming"],
        people=["Guido"],
    )

    result = await service.evolve(
        parent_id,
        new_content="I now think Rust and Python are both excellent.",
        new_meaning="evolved perspective on programming languages",
    )

    assert result["parent_status"] == "evolved"
    assert result["parent_id"] == str(parent_id)

    child_id = uuid.UUID(result["child_id"])

    # Verify parent is marked evolved
    parent = await service.repo.get_by_id(parent_id)
    assert parent is not None
    assert parent.status == "evolved"

    # Verify child was created correctly
    child = await service.repo.get_by_id(child_id)
    assert child is not None
    assert child.content == "I now think Rust and Python are both excellent."
    assert child.meaning == "evolved perspective on programming languages"
    assert child.parent_memory_id == parent_id
    assert child.status == "active"
    assert child.confidence == 1.0

    # Child inherits topics
    child_topic_names = {t.name for t in child.topics}
    assert "programming" in child_topic_names

    # Child inherits people
    child_person_names = {p.name for p in child.people}
    assert "Guido" in child_person_names


async def test_evolve_preserves_parent_meaning_when_not_provided(
    service: MemoryService,
):
    """evolve() inherits the parent's meaning if new_meaning is not provided."""
    parent_id = await _create_memory(service, content="Original thought")

    result = await service.evolve(parent_id, new_content="Updated thought")

    child_id = uuid.UUID(result["child_id"])
    child = await service.repo.get_by_id(child_id)
    assert child is not None
    assert child.meaning == "original meaning"  # inherited from parent


async def test_degraded_memory_excluded_from_search(service: MemoryService):
    """Memories with status='degraded' are excluded from vector search."""
    memory_id = await _create_memory(
        service,
        content="This memory will be degraded and unsearchable",
        importance_score=0.9,
    )

    # Degrade until status becomes "degraded"
    for _ in range(4):
        await service.degrade(memory_id)

    memory = await service.repo.get_by_id(memory_id)
    assert memory is not None
    assert memory.status == "degraded"

    # Search should not return degraded memories (search filters status="active")
    results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    result_ids = {m.id for m in results}
    assert memory_id not in result_ids


async def test_evolved_parent_excluded_from_search(service: MemoryService):
    """Evolved parent memories are excluded from search; only child is found."""
    parent_id = await _create_memory(
        service,
        content="Old perspective on the topic",
        importance_score=0.9,
    )

    result = await service.evolve(
        parent_id, "New perspective on the topic", "grown understanding"
    )
    child_id = uuid.UUID(result["child_id"])

    # Search should return the child but not the evolved parent
    results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    result_ids = {m.id for m in results}
    assert parent_id not in result_ids
    assert child_id in result_ids


async def test_full_lifecycle_reinforce_degrade_evolve(service: MemoryService):
    """Full lifecycle: create -> reinforce -> degrade -> evolve."""
    # Create
    memory_id = await _create_memory(
        service,
        content="My initial stance on testing",
        importance_score=0.5,
        topics=["testing"],
    )

    # Reinforce twice
    r1 = await service.reinforce(memory_id)
    assert r1["reinforcement_count"] == 1
    assert r1["importance_score"] == pytest.approx(0.55)

    r2 = await service.reinforce(memory_id)
    assert r2["reinforcement_count"] == 2
    assert r2["importance_score"] == pytest.approx(0.6)

    # Degrade once
    d1 = await service.degrade(memory_id)
    assert d1["confidence"] == pytest.approx(0.8)
    assert d1["status"] == "active"

    # Evolve
    evolve_result = await service.evolve(
        memory_id,
        new_content="My evolved stance: integration tests are essential",
        new_meaning="matured view on testing practices",
    )
    child_id = uuid.UUID(evolve_result["child_id"])

    # Parent is evolved
    parent = await service.repo.get_by_id(memory_id)
    assert parent is not None
    assert parent.status == "evolved"

    # Child is active with confidence 1.0
    child = await service.repo.get_by_id(child_id)
    assert child is not None
    assert child.status == "active"
    assert child.confidence == 1.0
    assert child.content == "My evolved stance: integration tests are essential"
    assert "testing" in {t.name for t in child.topics}
