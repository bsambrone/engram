"""Tests for memory and sources API routes."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.service import MemoryService


def _dummy_embedding(seed: float = 0.1) -> list[float]:
    return [seed] * 1536


async def _create_test_memory(db_session: AsyncSession, **overrides) -> uuid.UUID:
    """Helper to create a memory directly via the service for testing."""
    defaults = {
        "content": "Test memory for API",
        "embedding": _dummy_embedding(),
        "source": "file",
        "source_ref": "api-test.txt",
        "authorship": "user_authored",
        "importance_score": 0.6,
    }
    defaults.update(overrides)
    service = MemoryService(db_session)
    return await service.store_analyzed_chunk(**defaults)


async def test_get_memories_returns_list(test_client: AsyncClient):
    """GET /api/memories returns a list (possibly empty)."""
    resp = await test_client.get("/api/memories")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_stats(test_client: AsyncClient):
    """GET /api/memories/stats returns aggregate stats."""
    resp = await test_client.get("/api/memories/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_memories" in body
    assert "by_source" in body
    assert "topic_count" in body
    assert "person_count" in body


async def test_get_contradictions_stub(test_client: AsyncClient):
    """GET /api/memories/contradictions returns empty list (stub)."""
    resp = await test_client.get("/api/memories/contradictions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_then_get_by_id(test_client: AsyncClient, db_session: AsyncSession):
    """Create a memory via service, then GET it by ID."""
    memory_id = await _create_test_memory(db_session)
    await db_session.commit()

    resp = await test_client.get(f"/api/memories/{memory_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(memory_id)
    assert body["content"] == "Test memory for API"
    assert body["source"] == "file"


async def test_get_memory_not_found(test_client: AsyncClient):
    """GET /api/memories/{id} returns 404 for non-existent ID."""
    fake_id = uuid.uuid4()
    resp = await test_client.get(f"/api/memories/{fake_id}")
    assert resp.status_code == 404


async def test_update_visibility(test_client: AsyncClient, db_session: AsyncSession):
    """PUT /api/memories/{id} updates visibility."""
    memory_id = await _create_test_memory(db_session)
    await db_session.commit()

    resp = await test_client.put(
        f"/api/memories/{memory_id}",
        json={"visibility": "hidden"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["visibility"] == "hidden"


async def test_update_importance(test_client: AsyncClient, db_session: AsyncSession):
    """PUT /api/memories/{id} can update importance_score."""
    memory_id = await _create_test_memory(db_session, importance_score=0.3)
    await db_session.commit()

    resp = await test_client.put(
        f"/api/memories/{memory_id}",
        json={"importance_score": 0.95},
    )
    assert resp.status_code == 200
    assert resp.json()["importance_score"] == 0.95


async def test_delete_memory(test_client: AsyncClient, db_session: AsyncSession):
    """DELETE /api/memories/{id} removes the memory."""
    memory_id = await _create_test_memory(db_session)
    await db_session.commit()

    resp = await test_client.delete(f"/api/memories/{memory_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Verify it's gone
    resp2 = await test_client.get(f"/api/memories/{memory_id}")
    assert resp2.status_code == 404


async def test_delete_memory_not_found(test_client: AsyncClient):
    """DELETE /api/memories/{id} returns 404 for non-existent ID."""
    fake_id = uuid.uuid4()
    resp = await test_client.delete(f"/api/memories/{fake_id}")
    assert resp.status_code == 404


async def test_timeline(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories/timeline returns chronological list."""
    await _create_test_memory(db_session, content="Timeline entry")
    await db_session.commit()

    resp = await test_client.get("/api/memories/timeline")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_sources_list(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/sources returns list of sources."""
    await _create_test_memory(db_session, source="test-source", source_ref="test-ref")
    await db_session.commit()

    resp = await test_client.get("/api/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
