"""Integration test: visibility controls and privacy enforcement.

Verifies that memory visibility (active, private, excluded) is correctly
enforced across search, API endpoints, and token-based access control.

The system's visibility model:
- Owner search (visibility=None): sees all active-status memories regardless
  of visibility field (active, private, excluded).
- Shared search (visibility="active"): sees only memories where
  visibility="active".
- The visibility field is a data-level tag; the owner always has full access.
"""

import hashlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.service import MemoryService
from engram.models.auth import AccessToken

EMBEDDING_DIM = 1536
DETERMINISTIC_EMBEDDING = [0.1] * EMBEDDING_DIM


@pytest.fixture
def service(db_session: AsyncSession) -> MemoryService:
    return MemoryService(db_session)


async def _create_memory_with_visibility(
    service: MemoryService,
    content: str,
    visibility: str,
    source_ref: str | None = None,
) -> uuid.UUID:
    """Create a memory with a specific visibility setting."""
    memory_id = await service.store_analyzed_chunk(
        content=content,
        embedding=DETERMINISTIC_EMBEDDING,
        source="file",
        source_ref=source_ref or f"privacy-{uuid.uuid4().hex[:8]}.txt",
        authorship="user_authored",
        importance_score=0.8,
    )
    # Update visibility (store_analyzed_chunk always sets "active")
    if visibility != "active":
        await service.repo.update(memory_id, visibility=visibility)
    return memory_id


async def test_owner_sees_active_and_private(service: MemoryService):
    """Owner search (visibility=None) returns both active and private memories."""
    active_id = await _create_memory_with_visibility(
        service, "Active memory for owner test", "active"
    )
    private_id = await _create_memory_with_visibility(
        service, "Private memory for owner test", "private"
    )

    # Owner search: visibility=None means no filter
    results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    result_ids = {m.id for m in results}
    assert active_id in result_ids
    assert private_id in result_ids


async def test_shared_sees_only_active(service: MemoryService):
    """Shared search (visibility="active") returns only active memories."""
    active_id = await _create_memory_with_visibility(
        service, "Active memory for shared test", "active"
    )
    private_id = await _create_memory_with_visibility(
        service, "Private memory for shared test", "private"
    )

    # Shared search: explicit visibility="active"
    results = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    result_ids = {m.id for m in results}
    assert active_id in result_ids
    assert private_id not in result_ids


async def test_excluded_hidden_from_shared_search(service: MemoryService):
    """Excluded memories do not appear in shared (visibility='active') searches."""
    excluded_id = await _create_memory_with_visibility(
        service, "Excluded memory for shared search", "excluded"
    )

    # Shared search: visibility="active" should NOT return excluded
    shared_results = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    shared_ids = {m.id for m in shared_results}
    assert excluded_id not in shared_ids


async def test_owner_sees_excluded_memories(service: MemoryService):
    """Owner search (visibility=None) can see excluded memories."""
    excluded_id = await _create_memory_with_visibility(
        service, "Excluded memory visible to owner", "excluded"
    )

    # Owner search: no visibility filter, owner sees everything
    owner_results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    owner_ids = {m.id for m in owner_results}
    assert excluded_id in owner_ids


async def test_change_visibility_affects_shared_search(service: MemoryService):
    """Changing visibility from active to excluded removes from shared search."""
    memory_id = await _create_memory_with_visibility(
        service, "Initially active, will be excluded", "active"
    )

    # Verify it appears in shared search first
    results_before = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    assert memory_id in {m.id for m in results_before}

    # Change to excluded
    await service.repo.update(memory_id, visibility="excluded")

    # Should no longer appear in shared search
    results_after = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    assert memory_id not in {m.id for m in results_after}

    # But owner can still see it
    owner_results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    assert memory_id in {m.id for m in owner_results}


async def test_change_active_to_private_hides_from_shared(service: MemoryService):
    """Changing visibility from active to private hides from shared search."""
    memory_id = await _create_memory_with_visibility(
        service, "Will become private", "active"
    )

    # Shared search finds it
    results = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    assert memory_id in {m.id for m in results}

    # Change to private
    await service.repo.update(memory_id, visibility="private")

    # Shared search no longer finds it
    results = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    assert memory_id not in {m.id for m in results}

    # Owner still sees it
    owner_results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    assert memory_id in {m.id for m in owner_results}


async def test_visibility_update_by_source_ref(
    db_session: AsyncSession, service: MemoryService
):
    """update_visibility_by_source_ref changes all memories from a source."""
    ref = f"batch-source-{uuid.uuid4().hex[:8]}"

    id1 = await _create_memory_with_visibility(
        service, "Batch mem 1", "active", source_ref=ref
    )
    id2 = await _create_memory_with_visibility(
        service, "Batch mem 2", "active", source_ref=ref
    )

    updated_count = await service.repo.update_visibility_by_source_ref(ref, "private")
    assert updated_count == 2

    # Now shared search should not find them
    results = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    result_ids = {m.id for m in results}
    assert id1 not in result_ids
    assert id2 not in result_ids

    # But owner search should still find them
    owner_results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    owner_ids = {m.id for m in owner_results}
    assert id1 in owner_ids
    assert id2 in owner_ids


@patch("engram.llm.rag.generate", new_callable=AsyncMock)
@patch("engram.llm.rag.embed_texts", new_callable=AsyncMock)
async def test_ask_engram_owner_sees_private(
    mock_embed,
    mock_rag_generate,
    db_session: AsyncSession,
    service: MemoryService,
):
    """ask_engram with is_owner=True includes private memories in context."""
    from engram.identity.service import IdentityService
    from engram.llm.rag import ask_engram

    # Create identity profile
    identity_svc = IdentityService(db_session)
    await identity_svc.get_or_create_default_profile()

    active_id = await _create_memory_with_visibility(
        service, "Active public memory", "active"
    )
    private_id = await _create_memory_with_visibility(
        service, "Private secret memory", "private"
    )

    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_rag_generate.return_value = "Response incorporating both memories."

    response = await ask_engram(db_session, "Tell me everything", is_owner=True)

    assert response.answer is not None
    # Owner should get memory refs
    assert response.memory_refs is not None

    # Both memories should be referenced (both have the same embedding)
    ref_uuids = {uuid.UUID(r) for r in response.memory_refs}
    assert active_id in ref_uuids
    assert private_id in ref_uuids


@patch("engram.llm.rag.generate", new_callable=AsyncMock)
@patch("engram.llm.rag.embed_texts", new_callable=AsyncMock)
async def test_ask_engram_shared_excludes_private(
    mock_embed,
    mock_rag_generate,
    db_session: AsyncSession,
    service: MemoryService,
):
    """ask_engram with is_owner=False excludes private memories."""
    from engram.identity.service import IdentityService
    from engram.llm.rag import ask_engram

    identity_svc = IdentityService(db_session)
    await identity_svc.get_or_create_default_profile()

    await _create_memory_with_visibility(
        service, "Active shared memory content", "active"
    )
    await _create_memory_with_visibility(
        service, "Private owner-only memory content", "private"
    )

    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_rag_generate.return_value = "Response from shared perspective."

    response = await ask_engram(db_session, "Tell me about yourself", is_owner=False)

    assert response.answer is not None
    # Shared token should not get memory refs
    assert response.memory_refs is None


@patch("engram.api.routes.engram.ask_engram", new_callable=AsyncMock)
async def test_api_shared_token_query(
    mock_ask_engram,
    db_session: AsyncSession,
    service: MemoryService,
):
    """API test: a shared token calls ask_engram with is_owner=False."""
    from engram.db import get_session
    from engram.llm.rag import EngramResponse
    from engram.main import app

    # Create a shared token
    shared_token_value = "shared-test-" + uuid.uuid4().hex[:16]
    shared_token_hash = hashlib.sha256(shared_token_value.encode()).hexdigest()
    shared_token = AccessToken(
        name="shared-test",
        token_hash=shared_token_hash,
        access_level="shared",
    )
    db_session.add(shared_token)
    await db_session.flush()

    # Set up mock
    mock_ask_engram.return_value = EngramResponse(
        answer="I can only share what is public.",
        confidence=0.8,
        memory_refs=None,
        belief_refs=None,
        caveats=[],
    )

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    try:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {shared_token_value}"},
        ) as client:
            resp = await client.post(
                "/api/engram/ask",
                json={"query": "What are your secrets?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] is not None
        # Shared token should not get memory_refs or belief_refs
        assert data.get("memory_refs") is None
        assert data.get("belief_refs") is None

        # Verify ask_engram was called with is_owner=False
        call_kwargs = mock_ask_engram.call_args
        assert call_kwargs.kwargs.get("is_owner") is False

    finally:
        app.dependency_overrides.clear()


async def test_mixed_visibility_search_filters(service: MemoryService):
    """Comprehensive test of mixed visibility states in search."""
    active_id = await _create_memory_with_visibility(
        service, "Mixed-test: active visible", "active"
    )
    private_id = await _create_memory_with_visibility(
        service, "Mixed-test: private owner-only", "private"
    )
    excluded_id = await _create_memory_with_visibility(
        service, "Mixed-test: excluded tagged", "excluded"
    )

    # Owner search: sees all (active, private, excluded)
    owner_results = await service.remember(DETERMINISTIC_EMBEDDING, limit=50)
    owner_ids = {m.id for m in owner_results}
    assert active_id in owner_ids
    assert private_id in owner_ids
    assert excluded_id in owner_ids

    # Shared search: sees only active
    shared_results = await service.remember(
        DETERMINISTIC_EMBEDDING, limit=50, visibility="active"
    )
    shared_ids = {m.id for m in shared_results}
    assert active_id in shared_ids
    assert private_id not in shared_ids
    assert excluded_id not in shared_ids
