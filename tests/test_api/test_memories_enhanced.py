"""Tests for enhanced memory search: multi-source, visibility, sort, date range, pagination."""

import uuid
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.service import MemoryService


def _dummy_embedding(seed: float = 0.1) -> list[float]:
    return [seed] * 1536


async def _create_memory(
    db_session: AsyncSession,
    content: str = "Test memory",
    source: str = "file",
    source_ref: str = "test.txt",
    importance_score: float = 0.5,
    visibility: str = "active",
    reinforcement_count: int = 0,
    timestamp: datetime | None = None,
    interaction_context: str | None = None,
) -> uuid.UUID:
    """Create a memory via the service and optionally set extra fields."""
    service = MemoryService(db_session)
    memory_id = await service.store_analyzed_chunk(
        content=content,
        embedding=_dummy_embedding(),
        source=source,
        source_ref=source_ref,
        authorship="user_authored",
        importance_score=importance_score,
        timestamp=timestamp,
        interaction_context=interaction_context,
    )
    # Apply fields not handled by store_analyzed_chunk
    from engram.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    updates = {}
    if visibility != "active":
        updates["visibility"] = visibility
    if reinforcement_count != 0:
        updates["reinforcement_count"] = reinforcement_count
    if updates:
        await repo.update(memory_id, **updates)
    return memory_id


# ---------- Multi-source filter ----------


async def test_multi_source_filter(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories?sources=gmail,reddit returns only those sources."""
    await _create_memory(db_session, content="From Gmail", source="gmail")
    await _create_memory(db_session, content="From Reddit", source="reddit")
    await _create_memory(db_session, content="From Slack", source="slack")
    await db_session.commit()

    resp = await test_client.get("/api/memories", params={"sources": "gmail,reddit"})
    assert resp.status_code == 200
    body = resp.json()
    returned_sources = {m["source"] for m in body}
    assert returned_sources <= {"gmail", "reddit"}
    # At minimum our two seeded memories should be present
    assert len(body) >= 2


# ---------- Visibility filter ----------


async def test_visibility_filter(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories?visibility=private returns only private memories."""
    await _create_memory(db_session, content="Active memory", visibility="active")
    await _create_memory(db_session, content="Private memory", visibility="private")
    await db_session.commit()

    resp = await test_client.get("/api/memories", params={"visibility": "private"})
    assert resp.status_code == 200
    body = resp.json()
    assert all(m["visibility"] == "private" for m in body)
    assert any(m["content"] == "Private memory" for m in body)


async def test_default_visibility_is_active(test_client: AsyncClient, db_session: AsyncSession):
    """Without visibility param, only active memories are returned."""
    await _create_memory(db_session, content="Active default", visibility="active")
    await _create_memory(db_session, content="Excluded memory", visibility="excluded")
    await db_session.commit()

    resp = await test_client.get("/api/memories")
    assert resp.status_code == 200
    body = resp.json()
    # All returned memories should be active
    assert all(m["visibility"] == "active" for m in body)


# ---------- Sort by importance ----------


async def test_sort_by_importance(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories?sort=importance returns highest importance first."""
    await _create_memory(db_session, content="Low imp", importance_score=0.1)
    await _create_memory(db_session, content="High imp", importance_score=0.99)
    await _create_memory(db_session, content="Mid imp", importance_score=0.5)
    await db_session.commit()

    resp = await test_client.get("/api/memories", params={"sort": "importance"})
    assert resp.status_code == 200
    body = resp.json()
    scores = [m["importance_score"] for m in body if m["importance_score"] is not None]
    # Scores should be in descending order
    assert scores == sorted(scores, reverse=True)


# ---------- Sort by reinforcement ----------


async def test_sort_by_reinforcement(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories?sort=reinforcement returns highest reinforcement first."""
    await _create_memory(db_session, content="No reinforce", reinforcement_count=0)
    await _create_memory(db_session, content="High reinforce", reinforcement_count=10)
    await _create_memory(db_session, content="Mid reinforce", reinforcement_count=5)
    await db_session.commit()

    resp = await test_client.get("/api/memories", params={"sort": "reinforcement"})
    assert resp.status_code == 200
    body = resp.json()
    counts = [m["reinforcement_count"] for m in body]
    assert counts == sorted(counts, reverse=True)


# ---------- Date range filter ----------


async def test_date_range_filter(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories?date_from=...&date_to=... returns only memories in range."""
    now = datetime.now(tz=None)  # naive UTC-equivalent for DB without timezone
    old = now - timedelta(days=30)
    recent = now - timedelta(days=1)

    await _create_memory(db_session, content="Old memory", timestamp=old)
    await _create_memory(db_session, content="Recent memory", timestamp=recent)
    await db_session.commit()

    # Filter to only last 7 days
    date_from = (now - timedelta(days=7)).isoformat()
    date_to = now.isoformat()

    resp = await test_client.get(
        "/api/memories",
        params={"date_from": date_from, "date_to": date_to},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Recent memory should be in results, old one should not
    contents = [m["content"] for m in body]
    assert "Recent memory" in contents
    assert "Old memory" not in contents


# ---------- Offset pagination ----------


async def test_offset_pagination(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/memories?limit=2&offset=0 vs offset=2 returns different pages."""
    for i in range(5):
        await _create_memory(
            db_session,
            content=f"Pagination memory {i}",
            importance_score=0.5 + i * 0.01,
        )
    await db_session.commit()

    page1 = await test_client.get("/api/memories", params={"limit": 2, "offset": 0})
    page2 = await test_client.get("/api/memories", params={"limit": 2, "offset": 2})
    assert page1.status_code == 200
    assert page2.status_code == 200

    ids_page1 = {m["id"] for m in page1.json()}
    ids_page2 = {m["id"] for m in page2.json()}
    # Pages should not overlap
    assert ids_page1.isdisjoint(ids_page2)


# ---------- interaction_context in detail response ----------


async def test_interaction_context_in_detail(
    test_client: AsyncClient, db_session: AsyncSession
):
    """GET /api/memories/{id} includes interaction_context."""
    memory_id = await _create_memory(
        db_session,
        content="Memory with context",
        interaction_context="User asked about cooking recipes",
    )
    await db_session.commit()

    resp = await test_client.get(f"/api/memories/{memory_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "interaction_context" in body
    assert body["interaction_context"] == "User asked about cooking recipes"


# ---------- Invalid date format ----------


async def test_invalid_date_from_returns_400(test_client: AsyncClient):
    """GET /api/memories?date_from=bad returns 400."""
    resp = await test_client.get("/api/memories", params={"date_from": "not-a-date"})
    assert resp.status_code == 400
