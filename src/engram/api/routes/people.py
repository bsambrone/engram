"""People API routes — search, detail, graph, and related memories."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engram.api.deps import require_owner
from engram.db import get_session
from engram.models.auth import AccessToken
from engram.models.memory import Memory, MemoryPerson, MemoryTopic, Person, Topic
from engram.models.social import Relationship

router = APIRouter(prefix="/people", tags=["people"])


# ---- Pydantic schemas -------------------------------------------------------


class PersonListItem(BaseModel):
    id: uuid.UUID
    name: str
    relationship_type: str | None = None
    platforms: list[str] = []
    message_count: int = 0
    interaction_score: float = 0.0
    connected_since: str | None = None

    model_config = {"from_attributes": True}


class RelationshipOut(BaseModel):
    id: uuid.UUID
    platform: str
    relationship_type: str | None = None
    connected_since: str | None = None
    message_count: int = 0
    interaction_score: float = 0.0
    notes: str | None = None

    model_config = {"from_attributes": True}


class TopicCount(BaseModel):
    name: str
    count: int


class PersonDetail(BaseModel):
    id: uuid.UUID
    name: str
    relationship_type: str | None = None
    relationships: list[RelationshipOut] = []
    memory_count: int = 0
    top_topics: list[TopicCount] = []

    model_config = {"from_attributes": True}


class PersonUpdate(BaseModel):
    name: str | None = None
    relationship_type: str | None = None


class MemoryOut(BaseModel):
    id: uuid.UUID
    content: str
    intent: str | None = None
    meaning: str | None = None
    source: str | None = None
    source_ref: str | None = None
    timestamp: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class GraphNode(BaseModel):
    id: str
    name: str
    score: float = 0.0
    platform: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float = 0.0


class GraphOut(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


# ---- Routes (fixed paths BEFORE parameterized paths) ------------------------


@router.get("/graph", response_model=GraphOut)
async def get_people_graph(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Return a relationship graph centered on the user.

    Nodes: people with interaction_score > 0 (top 100 by score).
    Edges: between "self" center node and each person, weight = interaction_score.
    """
    # Get people with their max interaction score and primary platform
    stmt = (
        select(
            Person.id,
            Person.name,
            func.max(Relationship.interaction_score).label("max_score"),
            func.min(Relationship.platform).label("platform"),
        )
        .join(Relationship, Relationship.person_id == Person.id)
        .group_by(Person.id, Person.name)
        .having(func.max(Relationship.interaction_score) > 0)
        .order_by(func.max(Relationship.interaction_score).desc())
        .limit(100)
    )
    result = await session.execute(stmt)
    rows = result.all()

    nodes: list[GraphNode] = [GraphNode(id="self", name="You", score=1.0)]
    edges: list[GraphEdge] = []

    for row in rows:
        person_id_str = str(row.id)
        nodes.append(
            GraphNode(
                id=person_id_str,
                name=row.name,
                score=float(row.max_score),
                platform=row.platform,
            )
        )
        edges.append(
            GraphEdge(
                source="self",
                target=person_id_str,
                weight=float(row.max_score),
            )
        )

    return GraphOut(nodes=nodes, edges=edges)


@router.get("", response_model=list[PersonListItem])
async def list_people(
    q: str | None = Query(None, description="Search by name (case-insensitive)"),
    sort: str = Query("name", description="Sort: name, interaction, messages"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List people with aggregated relationship data."""
    # Build a subquery that aggregates relationship data per person
    rel_sub = (
        select(
            Relationship.person_id,
            func.sum(Relationship.message_count).label("total_messages"),
            func.max(Relationship.interaction_score).label("max_score"),
            func.min(Relationship.connected_since).label("earliest_connected"),
            func.array_agg(func.distinct(Relationship.platform)).label("platforms"),
        )
        .group_by(Relationship.person_id)
        .subquery()
    )

    stmt = (
        select(
            Person.id,
            Person.name,
            Person.relationship_type,
            func.coalesce(rel_sub.c.total_messages, 0).label("message_count"),
            func.coalesce(rel_sub.c.max_score, 0.0).label("interaction_score"),
            rel_sub.c.earliest_connected.label("connected_since"),
            rel_sub.c.platforms,
        )
        .outerjoin(rel_sub, Person.id == rel_sub.c.person_id)
    )

    # Text search on name
    if q:
        stmt = stmt.where(Person.name.ilike(f"%{q}%"))

    # Sorting
    if sort == "interaction":
        stmt = stmt.order_by(
            func.coalesce(rel_sub.c.max_score, 0.0).desc()
        )
    elif sort == "messages":
        stmt = stmt.order_by(
            func.coalesce(rel_sub.c.total_messages, 0).desc()
        )
    else:  # default: name asc
        stmt = stmt.order_by(Person.name.asc())

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    items = []
    for row in rows:
        platforms = row.platforms or []
        # Filter out None values that might come from array_agg
        platforms = [p for p in platforms if p is not None]
        connected_since = (
            row.connected_since.isoformat() if row.connected_since else None
        )
        items.append(
            PersonListItem(
                id=row.id,
                name=row.name,
                relationship_type=row.relationship_type,
                platforms=platforms,
                message_count=int(row.message_count),
                interaction_score=float(row.interaction_score),
                connected_since=connected_since,
            )
        )

    return items


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    person_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get person detail with relationships, memory count, and top topics."""
    # Fetch person
    result = await session.execute(
        select(Person).where(Person.id == person_id)
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    # Fetch relationships
    rel_result = await session.execute(
        select(Relationship).where(Relationship.person_id == person_id)
    )
    relationships = rel_result.scalars().all()

    rel_out = []
    for r in relationships:
        rel_out.append(
            RelationshipOut(
                id=r.id,
                platform=r.platform,
                relationship_type=r.relationship_type,
                connected_since=r.connected_since.isoformat() if r.connected_since else None,
                message_count=r.message_count,
                interaction_score=r.interaction_score,
                notes=r.notes,
            )
        )

    # Memory count
    mem_count_result = await session.execute(
        select(func.count()).select_from(MemoryPerson).where(
            MemoryPerson.person_id == person_id
        )
    )
    memory_count = mem_count_result.scalar() or 0

    # Top topics: from memories linked to this person, count topic occurrences
    topic_stmt = (
        select(Topic.name, func.count(Topic.id).label("cnt"))
        .join(MemoryTopic, MemoryTopic.topic_id == Topic.id)
        .join(MemoryPerson, MemoryPerson.memory_id == MemoryTopic.memory_id)
        .where(MemoryPerson.person_id == person_id)
        .group_by(Topic.name)
        .order_by(func.count(Topic.id).desc())
        .limit(10)
    )
    topic_result = await session.execute(topic_stmt)
    top_topics = [
        TopicCount(name=row.name, count=row.cnt) for row in topic_result.all()
    ]

    return PersonDetail(
        id=person.id,
        name=person.name,
        relationship_type=person.relationship_type,
        relationships=rel_out,
        memory_count=memory_count,
        top_topics=top_topics,
    )


@router.put("/{person_id}", response_model=PersonDetail)
async def update_person(
    person_id: uuid.UUID,
    body: PersonUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Update a person's name or relationship_type."""
    result = await session.execute(
        select(Person).where(Person.id == person_id)
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for key, value in updates.items():
        setattr(person, key, value)
    await session.flush()

    # Re-use get_person to return full detail
    return await get_person(person_id, session=session, _owner=_owner)


@router.get("/{person_id}/memories", response_model=list[MemoryOut])
async def get_person_memories(
    person_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get memories involving this person via the memory_people join table."""
    # Verify person exists
    person_result = await session.execute(
        select(Person.id).where(Person.id == person_id)
    )
    if person_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Person not found")

    stmt = (
        select(Memory)
        .join(MemoryPerson, MemoryPerson.memory_id == Memory.id)
        .where(MemoryPerson.person_id == person_id)
        .where(Memory.status == "active")
        .order_by(Memory.timestamp.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    memories = result.scalars().all()

    return [
        MemoryOut(
            id=m.id,
            content=m.content,
            intent=m.intent,
            meaning=m.meaning,
            source=m.source,
            source_ref=m.source_ref,
            timestamp=m.timestamp.isoformat() if m.timestamp else None,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in memories
    ]
