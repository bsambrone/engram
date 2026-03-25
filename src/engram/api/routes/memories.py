"""Memory API routes — owner-only."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.memory.repository import MemoryRepository
from engram.memory.service import MemoryService
from engram.models.auth import AccessToken
from engram.processing.embedder import embed_texts

router = APIRouter(prefix="/memories", tags=["memories"])


# ---- Pydantic schemas -------------------------------------------------------


class TopicOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class PersonOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class MemoryOut(BaseModel):
    id: uuid.UUID
    content: str
    intent: str | None = None
    meaning: str | None = None
    interaction_context: str | None = None
    source: str | None = None
    source_ref: str | None = None
    authorship: str | None = None
    importance_score: float | None = None
    confidence: float | None = None
    reinforcement_count: int = 0
    visibility: str = "active"
    status: str = "active"
    timestamp: str | None = None
    created_at: str | None = None
    topics: list[TopicOut] = []
    people: list[PersonOut] = []

    model_config = {"from_attributes": True}


class MemoryUpdate(BaseModel):
    content: str | None = None
    visibility: str | None = None
    importance_score: float | None = None


class StatsOut(BaseModel):
    total_memories: int
    by_source: dict[str, int]
    topic_count: int
    person_count: int


class ReinforceRequest(BaseModel):
    evidence: str | None = None


class DegradeRequest(BaseModel):
    evidence: str | None = None


class EvolveRequest(BaseModel):
    new_content: str
    new_meaning: str | None = None


# ---- Helpers -----------------------------------------------------------------


def _memory_to_dict(memory) -> dict:
    """Convert a Memory ORM object to a dict for MemoryOut."""
    return {
        "id": memory.id,
        "content": memory.content,
        "intent": memory.intent,
        "meaning": memory.meaning,
        "interaction_context": memory.interaction_context,
        "source": memory.source,
        "source_ref": memory.source_ref,
        "authorship": memory.authorship,
        "importance_score": memory.importance_score,
        "confidence": memory.confidence,
        "reinforcement_count": memory.reinforcement_count,
        "visibility": memory.visibility,
        "status": memory.status,
        "timestamp": memory.timestamp.isoformat() if memory.timestamp else None,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "topics": [{"id": t.id, "name": t.name} for t in memory.topics],
        "people": [{"id": p.id, "name": p.name} for p in memory.people],
    }


# ---- Routes (fixed paths BEFORE parameterized paths) ------------------------


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get aggregate memory statistics."""
    service = MemoryService(session)
    stats = await service.get_stats()
    return stats


@router.get("/contradictions")
async def get_contradictions(
    _owner: AccessToken = Depends(require_owner),
):
    """Stub: returns empty list for now."""
    return []


@router.get("/timeline", response_model=list[MemoryOut])
async def get_timeline(
    topic: str | None = Query(None),
    person: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get memories in chronological order."""
    repo = MemoryRepository(session)
    memories = await repo.get_timeline(topic=topic, person=person, limit=limit)
    return [_memory_to_dict(m) for m in memories]


@router.get("", response_model=list[MemoryOut])
async def search_memories(
    q: str | None = Query(None),
    topic: str | None = Query(None),
    person: str | None = Query(None),
    source: str | None = Query(None),
    sources: str | None = Query(None, description="Comma-separated source filter, e.g. 'gmail,reddit'"),
    visibility: str | None = Query(None, description="Filter by visibility: active, private, excluded"),
    sort: str = Query("date", description="Sort order: date, importance, reinforcement"),
    date_from: str | None = Query(None, description="ISO date string, filter memories >= this date"),
    date_to: str | None = Query(None, description="ISO date string, filter memories <= this date"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Search/filter memories.

    If ``q`` is provided *and* no extra filter params are used, performs vector
    search.  Otherwise falls back to SQL-based filtered search with sorting
    and pagination.
    """
    # Build the effective source list from both `source` (legacy single) and `sources` (new multi)
    source_list: list[str] | None = None
    if sources:
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
    if source:
        source_list = source_list or []
        if source not in source_list:
            source_list.append(source)

    # Parse date strings to datetime
    parsed_date_from: datetime | None = None
    parsed_date_to: datetime | None = None
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date_from: {date_from}")
    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date_to: {date_to}")

    # Determine whether to use vector search or filtered search.
    # Use vector search only when we have a text query AND no advanced filters.
    has_advanced_filters = any([
        source_list, visibility, sort != "date",
        parsed_date_from, parsed_date_to, offset > 0,
    ])

    if q and not has_advanced_filters:
        embeddings = await embed_texts([q])
        service = MemoryService(session)
        memories = await service.remember(
            embeddings[0],
            limit=limit,
            topic=topic,
            person=person,
            source=source,
        )
    else:
        repo = MemoryRepository(session)
        memories = await repo.filtered_search(
            q=q,
            topic=topic,
            person=person,
            sources=source_list,
            visibility=visibility,
            sort=sort,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            limit=limit,
            offset=offset,
        )
    return [_memory_to_dict(m) for m in memories]


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(
    memory_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get a single memory with topics and people."""
    repo = MemoryRepository(session)
    memory = await repo.get_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _memory_to_dict(memory)


@router.put("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: uuid.UUID,
    body: MemoryUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Update a memory's content, visibility, or importance."""
    repo = MemoryRepository(session)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    memory = await repo.update(memory_id, **updates)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Delete a memory."""
    repo = MemoryRepository(session)
    deleted = await repo.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}


@router.post("/{memory_id}/reinforce")
async def reinforce_memory(
    memory_id: uuid.UUID,
    body: ReinforceRequest | None = None,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Reinforce a memory — increment count and boost importance."""
    service = MemoryService(session)
    result = await service.reinforce(memory_id, evidence=body.evidence if body else None)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@router.post("/{memory_id}/degrade")
async def degrade_memory(
    memory_id: uuid.UUID,
    body: DegradeRequest | None = None,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Degrade a memory — lower confidence."""
    service = MemoryService(session)
    result = await service.degrade(memory_id, evidence=body.evidence if body else None)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@router.post("/{memory_id}/evolve")
async def evolve_memory(
    memory_id: uuid.UUID,
    body: EvolveRequest,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Evolve a memory — mark parent as evolved, create child."""
    service = MemoryService(session)
    result = await service.evolve(memory_id, body.new_content, body.new_meaning)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result
