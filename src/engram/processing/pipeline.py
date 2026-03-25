"""Processing pipeline orchestrator — normalize, chunk, embed, analyze, store."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.ingestion.parsers.base import RawDocument
from engram.memory.repository import MemoryRepository
from engram.memory.service import MemoryService
from engram.models.social import LifeEvent, Location, Relationship
from engram.processing.analyzer import analyze_chunk
from engram.processing.chunker import chunk_text
from engram.processing.embedder import embed_texts
from engram.processing.normalizer import normalize

logger = logging.getLogger(__name__)


async def _update_relationships(
    session: AsyncSession,
    repo: MemoryRepository,
    people: list[str],
    source: str,
    relationship_type: str = "contact",
) -> None:
    """Find or create Relationship records for each person on the given platform."""
    with session.no_autoflush:
        for person_name in people:
            person = await repo.get_or_create_person(person_name)
            result = await session.execute(
                select(Relationship).where(
                    Relationship.person_id == person.id,
                    Relationship.platform == source,
                )
            )
            rel = result.scalar_one_or_none()
            if rel:
                rel.message_count += 1
                rel.interaction_score = min(rel.message_count / 100, 1.0)
            else:
                session.add(
                    Relationship(
                        person_id=person.id,
                        platform=source,
                        relationship_type=relationship_type,
                        message_count=1,
                        interaction_score=0.01,
                    )
                )
        await session.flush()


async def _store_locations(
    session: AsyncSession,
    location_names: list[str],
    source: str,
    timestamp=None,
) -> None:
    """Get-or-create Location records for each location name."""
    # Strip timezone if present
    if timestamp and hasattr(timestamp, "tzinfo") and timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)
    with session.no_autoflush:
        for loc_name in location_names:
            result = await session.execute(
                select(Location).where(Location.name == loc_name)
            )
            loc = result.scalar_one_or_none()
            if loc:
                loc.visit_count += 1
                if timestamp and (loc.last_visited is None or timestamp > loc.last_visited):
                    loc.last_visited = timestamp
            else:
                session.add(
                    Location(
                        name=loc_name,
                        source=source,
                        first_visited=timestamp,
                        last_visited=timestamp,
                    )
                )
        await session.flush()


async def _store_life_events(
    session: AsyncSession,
    life_events: list[dict],
    source: str,
    source_ref: str,
    timestamp=None,
    people: list[str] | None = None,
) -> None:
    """Create LifeEvent records."""
    for event in life_events:
        title = event.get("title", "")
        if not title:
            continue
        session.add(
            LifeEvent(
                title=title,
                event_type=event.get("event_type"),
                source=source,
                source_ref=source_ref,
                event_date=timestamp,
                people=", ".join(people) if people else None,
            )
        )
    await session.flush()


async def _process_image_refs(
    session: AsyncSession,
    image_refs: list[str],
    source: str,
    people: list[str] | None = None,
) -> None:
    """Upload images from disk and optionally link people to the photos."""
    from engram.photos.service import PhotoService

    photo_svc = PhotoService(session)
    repo = MemoryRepository(session)

    for image_ref in image_refs:
        image_path = Path(image_ref)
        if not image_path.exists():
            # Try relative to common export paths
            for base in [
                Path("/home/bsambrone/engram-data/facebook"),
                Path("/home/bsambrone/engram-data/instagram"),
            ]:
                candidate = base / image_ref
                if candidate.exists():
                    image_path = candidate
                    break
        if not image_path.exists():
            logger.debug("Image not found: %s", image_ref)
            continue

        result = await photo_svc.upload_photo(
            file_content=image_path.read_bytes(),
            filename=image_path.name,
            source=source,
        )

        # Link people to the uploaded photo
        if people and result.get("id"):
            import uuid as _uuid

            from engram.models.photo import PhotoPerson

            photo_id = _uuid.UUID(result["id"])
            for person_name in people:
                person = await repo.get_or_create_person(person_name)
                existing = await session.execute(
                    select(PhotoPerson).where(
                        PhotoPerson.photo_id == photo_id,
                        PhotoPerson.person_id == person.id,
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(
                        PhotoPerson(photo_id=photo_id, person_id=person.id)
                    )
            await session.flush()


async def process_documents(
    documents: list[RawDocument],
    session: AsyncSession,
    *,
    process_images: bool = False,
) -> int:
    """Process raw documents through the full pipeline.

    Steps: normalize -> chunk -> embed -> analyze -> store.
    Returns the number of memories created.

    Args:
        documents: Raw documents to process.
        session: Database session.
        process_images: If True, upload images from image_refs to the photo store.
    """
    memory_service = MemoryService(session)
    repo = MemoryRepository(session)
    count = 0

    for doc in documents:
        if not doc.content:
            continue

        normalized = normalize(doc.content)
        if not normalized:
            continue

        chunks = chunk_text(normalized)
        embeddings = await embed_texts(chunks)

        for chunk_content, embedding in zip(chunks, embeddings):
            analyzed = await analyze_chunk(chunk_content, doc.authorship, embedding)
            if not analyzed.keep:
                continue

            # Merge parser-extracted people with LLM-extracted people
            all_people = list(dict.fromkeys(doc.people + analyzed.people))

            await memory_service.store_analyzed_chunk(
                content=analyzed.content,
                embedding=analyzed.embedding,
                source=doc.source,
                source_ref=doc.source_ref,
                authorship=analyzed.authorship,
                intent=analyzed.intent,
                meaning=analyzed.meaning,
                interaction_context=analyzed.interaction_context,
                topics=analyzed.topics,
                people=all_people,
                importance_score=analyzed.importance_score,
                timestamp=doc.timestamp,
            )
            count += 1

            # Store locations extracted by LLM
            if analyzed.locations:
                await _store_locations(
                    session, analyzed.locations, doc.source, doc.timestamp
                )

            # Store life events extracted by LLM
            if analyzed.life_events:
                await _store_life_events(
                    session,
                    analyzed.life_events,
                    doc.source,
                    doc.source_ref,
                    doc.timestamp,
                    all_people,
                )

            # Update relationships for received messages (Gap 4)
            if doc.authorship == "received" and all_people:
                await _update_relationships(
                    session, repo, all_people, doc.source, "contact"
                )

            # Update relationships for Facebook tagged people (Gap 5)
            if doc.source == "facebook" and doc.people:
                await _update_relationships(
                    session, repo, doc.people, doc.source, "tagged_together"
                )

        # Process image refs if enabled (Gap 3)
        if process_images and doc.image_refs:
            all_doc_people = list(dict.fromkeys(doc.people))
            await _process_image_refs(
                session, doc.image_refs, doc.source, all_doc_people
            )

    return count
