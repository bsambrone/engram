"""Memory repository — DB queries for CRUD, vector search, and filtered search."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engram.config import settings
from engram.models.memory import Memory, MemoryPerson, MemoryTopic, Person, Topic


def _recency_score(timestamp: datetime | None, halflife_days: int) -> float:
    """Compute exponential decay score based on memory age."""
    if timestamp is None:
        return 0.5
    now = datetime.now(timezone.utc)
    ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    days_ago = (now - ts).total_seconds() / 86400
    return math.exp(-0.693 * days_ago / halflife_days)


def _reinforcement_score(count: int) -> float:
    """Normalize reinforcement count to 0-1 range (capped at 10)."""
    return min(count / 10, 1.0)


def _composite_score(
    cosine_similarity: float,
    importance: float | None,
    timestamp: datetime | None,
    reinforcement_count: int,
    halflife_days: int,
) -> float:
    """Weighted composite ranking score."""
    imp = importance if importance is not None else 0.5
    rec = _recency_score(timestamp, halflife_days)
    rein = _reinforcement_score(reinforcement_count)
    return cosine_similarity * 0.5 + imp * 0.2 + rec * 0.2 + rein * 0.1


class MemoryRepository:
    """Database operations for Memory, Topic, and Person models."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- CRUD ----------------------------------------------------------------

    async def create(self, **kwargs) -> Memory:
        """Create a new memory with the given fields."""
        # Strip timezone info — DB uses TIMESTAMP WITHOUT TIME ZONE
        if "timestamp" in kwargs and kwargs["timestamp"] is not None:
            ts = kwargs["timestamp"]
            if ts.tzinfo is not None:
                kwargs["timestamp"] = ts.replace(tzinfo=None)
        memory = Memory(**kwargs)
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def get_by_id(self, memory_id: uuid.UUID) -> Memory | None:
        """Get a memory by ID with eager-loaded topics and people."""
        result = await self.session.execute(
            select(Memory)
            .where(Memory.id == memory_id)
            .options(selectinload(Memory.topics), selectinload(Memory.people))
        )
        return result.scalar_one_or_none()

    async def update(self, memory_id: uuid.UUID, **kwargs) -> Memory | None:
        """Partial update of a memory. Returns updated memory or None."""
        memory = await self.get_by_id(memory_id)
        if memory is None:
            return None
        for key, value in kwargs.items():
            setattr(memory, key, value)
        await self.session.flush()
        return memory

    async def delete(self, memory_id: uuid.UUID) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        result = await self.session.execute(
            delete(Memory).where(Memory.id == memory_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    # ---- Vector search -------------------------------------------------------

    async def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        topic: str | None = None,
        person: str | None = None,
        source: str | None = None,
        visibility: str | None = None,
        before_date: datetime | None = None,
    ) -> list[Memory]:
        """Vector search with optional filters and composite re-ranking.

        Fetches top limit*3 results by cosine distance, then re-ranks using the
        composite scoring formula and returns the top `limit` results.
        """
        fetch_limit = limit * 3

        # Build base query with cosine distance
        embedding_col = Memory.embedding
        distance = embedding_col.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(Memory, distance)
            .where(Memory.embedding.isnot(None))
            .where(Memory.status == "active")
        )

        # Apply filters
        if topic:
            stmt = stmt.join(Memory.topics).where(Topic.name == topic)
        if person:
            stmt = stmt.join(Memory.people).where(Person.name == person)
        if source:
            stmt = stmt.where(Memory.source == source)
        if visibility:
            stmt = stmt.where(Memory.visibility == visibility)
        if before_date:
            stmt = stmt.where(Memory.timestamp <= before_date)

        stmt = stmt.order_by(distance).limit(fetch_limit)

        result = await self.session.execute(
            stmt.options(selectinload(Memory.topics), selectinload(Memory.people))
        )
        rows = result.all()

        # Re-rank with composite score
        halflife = settings.memory_decay_halflife_days
        scored = []
        for row in rows:
            memory = row[0]
            cosine_dist = row[1]
            cosine_sim = 1.0 - cosine_dist
            score = _composite_score(
                cosine_sim,
                memory.importance_score,
                memory.timestamp,
                memory.reinforcement_count,
                halflife,
            )
            scored.append((memory, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored[:limit]]

    # ---- Timeline ------------------------------------------------------------

    async def get_timeline(
        self,
        *,
        topic: str | None = None,
        person: str | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        """Get memories in chronological order with optional filters."""
        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .options(selectinload(Memory.topics), selectinload(Memory.people))
        )

        if topic:
            stmt = stmt.join(Memory.topics).where(Topic.name == topic)
        if person:
            stmt = stmt.join(Memory.people).where(Person.name == person)

        stmt = stmt.order_by(Memory.timestamp.desc().nulls_last()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---- Topics & People -----------------------------------------------------

    async def get_or_create_topic(self, name: str) -> Topic:
        """Find an existing topic by name or create a new one."""
        result = await self.session.execute(
            select(Topic).where(Topic.name == name)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            topic = Topic(name=name)
            self.session.add(topic)
            await self.session.flush()
        return topic

    async def get_or_create_person(self, name: str) -> Person:
        """Find an existing person by name or create a new one."""
        result = await self.session.execute(
            select(Person).where(Person.name == name)
        )
        person = result.scalar_one_or_none()
        if person is None:
            person = Person(name=name)
            self.session.add(person)
            await self.session.flush()
        return person

    async def link_topics(self, memory_id: uuid.UUID, topic_ids: list[uuid.UUID]) -> None:
        """Create M2M links between a memory and topics."""
        for topic_id in topic_ids:
            # Check if link already exists
            result = await self.session.execute(
                select(MemoryTopic).where(
                    MemoryTopic.memory_id == memory_id,
                    MemoryTopic.topic_id == topic_id,
                )
            )
            if result.scalar_one_or_none() is None:
                self.session.add(MemoryTopic(memory_id=memory_id, topic_id=topic_id))
        await self.session.flush()

    async def link_people(self, memory_id: uuid.UUID, person_ids: list[uuid.UUID]) -> None:
        """Create M2M links between a memory and people."""
        for person_id in person_ids:
            result = await self.session.execute(
                select(MemoryPerson).where(
                    MemoryPerson.memory_id == memory_id,
                    MemoryPerson.person_id == person_id,
                )
            )
            if result.scalar_one_or_none() is None:
                self.session.add(MemoryPerson(memory_id=memory_id, person_id=person_id))
        await self.session.flush()

    # ---- Stats ---------------------------------------------------------------

    async def get_stats(self) -> dict:
        """Get aggregate statistics about memories."""
        # Total memories
        total_result = await self.session.execute(
            select(func.count(Memory.id)).where(Memory.status == "active")
        )
        total_count = total_result.scalar() or 0

        # Counts by source
        source_result = await self.session.execute(
            select(Memory.source, func.count(Memory.id))
            .where(Memory.status == "active")
            .group_by(Memory.source)
        )
        by_source = {row[0] or "unknown": row[1] for row in source_result.all()}

        # Topic count
        topic_result = await self.session.execute(select(func.count(Topic.id)))
        topic_count = topic_result.scalar() or 0

        # Person count
        person_result = await self.session.execute(select(func.count(Person.id)))
        person_count = person_result.scalar() or 0

        return {
            "total_memories": total_count,
            "by_source": by_source,
            "topic_count": topic_count,
            "person_count": person_count,
        }

    # ---- Sources -------------------------------------------------------------

    async def get_sources(self) -> list[dict]:
        """Get list of sources with counts and visibility breakdown."""
        result = await self.session.execute(
            select(
                Memory.source,
                Memory.source_ref,
                Memory.visibility,
                func.count(Memory.id),
            )
            .where(Memory.status == "active")
            .group_by(Memory.source, Memory.source_ref, Memory.visibility)
        )
        rows = result.all()

        # Aggregate by source_ref
        sources: dict[str, dict] = {}
        for source, source_ref, visibility, count in rows:
            key = source_ref or source or "unknown"
            if key not in sources:
                sources[key] = {
                    "source": source,
                    "source_ref": key,
                    "total": 0,
                    "visibility": {},
                }
            sources[key]["total"] += count
            sources[key]["visibility"][visibility] = (
                sources[key]["visibility"].get(visibility, 0) + count
            )

        return list(sources.values())

    async def update_visibility_by_source_ref(
        self, source_ref: str, visibility: str
    ) -> int:
        """Update visibility for all memories with a given source_ref."""
        result = await self.session.execute(
            select(Memory).where(Memory.source_ref == source_ref)
        )
        memories = result.scalars().all()
        for memory in memories:
            memory.visibility = visibility
        await self.session.flush()
        return len(memories)

    async def delete_by_source_ref(self, source_ref: str) -> int:
        """Delete all memories with a given source_ref."""
        result = await self.session.execute(
            delete(Memory).where(Memory.source_ref == source_ref)
        )
        await self.session.flush()
        return result.rowcount
