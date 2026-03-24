"""Memory service — business logic for store, remember, reinforce, degrade, evolve."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.repository import MemoryRepository


class MemoryService:
    """High-level memory operations backed by the repository layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MemoryRepository(session)

    async def store_analyzed_chunk(
        self,
        *,
        content: str,
        embedding: list[float],
        source: str,
        source_ref: str,
        authorship: str,
        intent: str | None = None,
        meaning: str | None = None,
        interaction_context: str | None = None,
        topics: list[str] | None = None,
        people: list[str] | None = None,
        importance_score: float = 0.5,
        timestamp: datetime | None = None,
    ) -> uuid.UUID:
        """Store a memory from analyzer output, linking topics and people.

        Returns the new memory's ID.
        """
        memory = await self.repo.create(
            content=content,
            embedding=embedding,
            source=source,
            source_ref=source_ref,
            authorship=authorship,
            intent=intent,
            meaning=meaning,
            interaction_context=interaction_context,
            importance_score=importance_score,
            confidence=1.0,
            timestamp=timestamp,
            visibility="active",
            status="active",
        )

        # Link topics
        if topics:
            topic_ids = []
            for topic_name in topics:
                topic = await self.repo.get_or_create_topic(topic_name)
                topic_ids.append(topic.id)
            await self.repo.link_topics(memory.id, topic_ids)

        # Link people
        if people:
            person_ids = []
            for person_name in people:
                person = await self.repo.get_or_create_person(person_name)
                person_ids.append(person.id)
            await self.repo.link_people(memory.id, person_ids)

        return memory.id

    async def remember(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        visibility: str | None = None,
        topic: str | None = None,
        person: str | None = None,
        source: str | None = None,
        before_date: datetime | None = None,
    ) -> list:
        """Search memories with composite ranking."""
        return await self.repo.search(
            query_embedding,
            limit=limit,
            visibility=visibility,
            topic=topic,
            person=person,
            source=source,
            before_date=before_date,
        )

    async def reinforce(self, memory_id: uuid.UUID, evidence: str | None = None) -> dict:
        """Increment reinforcement_count and boost importance.

        Returns a dict with the updated values.
        """
        memory = await self.repo.get_by_id(memory_id)
        if memory is None:
            return {"error": "not_found"}

        new_count = memory.reinforcement_count + 1
        new_importance = min((memory.importance_score or 0.5) + 0.05, 1.0)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        await self.repo.update(
            memory_id,
            reinforcement_count=new_count,
            importance_score=new_importance,
            last_reinforced_at=now,
        )

        return {
            "memory_id": str(memory_id),
            "reinforcement_count": new_count,
            "importance_score": new_importance,
            "last_reinforced_at": now.isoformat(),
        }

    async def degrade(self, memory_id: uuid.UUID, evidence: str | None = None) -> dict:
        """Lower confidence. Mark as 'degraded' if confidence drops below 0.3.

        Returns a dict with the updated values.
        """
        memory = await self.repo.get_by_id(memory_id)
        if memory is None:
            return {"error": "not_found"}

        new_confidence = max((memory.confidence or 1.0) - 0.2, 0.0)
        updates: dict = {"confidence": new_confidence}
        if new_confidence < 0.3:
            updates["status"] = "degraded"

        await self.repo.update(memory_id, **updates)

        return {
            "memory_id": str(memory_id),
            "confidence": new_confidence,
            "status": updates.get("status", memory.status),
        }

    async def evolve(
        self,
        memory_id: uuid.UUID,
        new_content: str,
        new_meaning: str | None = None,
    ) -> dict:
        """Mark the parent memory as 'evolved' and create a child memory.

        Returns a dict with the new child memory's ID.
        """
        parent = await self.repo.get_by_id(memory_id)
        if parent is None:
            return {"error": "not_found"}

        # Mark parent as evolved
        await self.repo.update(memory_id, status="evolved")

        # Create child memory inheriting key fields from parent
        child = await self.repo.create(
            parent_memory_id=memory_id,
            content=new_content,
            embedding=parent.embedding,
            intent=parent.intent,
            meaning=new_meaning or parent.meaning,
            source=parent.source,
            source_ref=parent.source_ref,
            authorship=parent.authorship,
            importance_score=parent.importance_score,
            confidence=1.0,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            visibility=parent.visibility,
            status="active",
        )

        # Copy topic and people links
        topic_ids = [t.id for t in parent.topics]
        if topic_ids:
            await self.repo.link_topics(child.id, topic_ids)

        person_ids = [p.id for p in parent.people]
        if person_ids:
            await self.repo.link_people(child.id, person_ids)

        return {
            "parent_id": str(memory_id),
            "child_id": str(child.id),
            "parent_status": "evolved",
        }

    async def get_stats(self) -> dict:
        """Delegate to repository for aggregate statistics."""
        return await self.repo.get_stats()
