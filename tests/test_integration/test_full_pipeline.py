"""Integration test: upload file -> process -> memories appear -> search works.

Exercises the full processing pipeline (normalize, chunk, embed, analyze, store)
with mocked external APIs (OpenAI embeddings and LLM generation) and verifies
that memories, topics, and people are correctly persisted and searchable.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engram.ingestion.parsers.base import RawDocument
from engram.memory.service import MemoryService
from engram.models.memory import Memory, Person, Topic
from engram.models.social import LifeEvent, Location, Relationship
from engram.processing.pipeline import process_documents

EMBEDDING_DIM = 1536
DETERMINISTIC_EMBEDDING = [0.1] * EMBEDDING_DIM


def _analysis_json(
    *,
    intent: str = "sharing experience",
    meaning: str = "values outdoor activities",
    topics: list[str] | None = None,
    people: list[str] | None = None,
    locations: list[str] | None = None,
    life_events: list[dict] | None = None,
    interaction_context: str | None = None,
    importance_score: float = 0.8,
    keep: bool = True,
) -> str:
    """Build a deterministic analysis JSON string."""
    data: dict = {
        "intent": intent,
        "meaning": meaning,
        "topics": topics or [],
        "people": people or [],
        "importance_score": importance_score,
        "keep": keep,
    }
    if locations is not None:
        data["locations"] = locations
    if life_events is not None:
        data["life_events"] = life_events
    if interaction_context is not None:
        data["interaction_context"] = interaction_context
    return json.dumps(data)


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_full_pipeline_creates_memories(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Process a RawDocument and verify memories, topics, and people are stored."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="sharing experience",
        meaning="values nature and adventure",
        topics=["hiking", "mountains"],
        people=["Sarah"],
        importance_score=0.85,
    )

    doc = RawDocument(
        content="I went hiking in the Rockies with Sarah last summer.",
        source="file",
        source_ref="journal.txt",
        authorship="user_authored",
    )

    count = await process_documents([doc], db_session)

    assert count == 1

    # Verify the memory was created
    result = await db_session.execute(
        select(Memory)
        .where(Memory.source_ref == "journal.txt")
        .options(selectinload(Memory.topics), selectinload(Memory.people))
    )
    memories = list(result.scalars().all())
    assert len(memories) == 1

    memory = memories[0]
    assert memory.content is not None
    assert memory.intent == "sharing experience"
    assert memory.meaning == "values nature and adventure"
    assert memory.importance_score == pytest.approx(0.85)
    assert memory.confidence == 1.0
    assert memory.source == "file"
    assert memory.source_ref == "journal.txt"
    assert memory.authorship == "user_authored"
    assert memory.status == "active"
    assert memory.visibility == "active"

    # Verify topics were linked
    topic_names = {t.name for t in memory.topics}
    assert "hiking" in topic_names
    assert "mountains" in topic_names

    # Verify people were linked
    person_names = {p.name for p in memory.people}
    assert "Sarah" in person_names


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_topics_persisted_globally(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Topics created by the pipeline exist as standalone Topic rows."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        topics=["integration-test-topic"],
    )

    doc = RawDocument(
        content="Testing topic persistence.",
        source="file",
        source_ref="topic-test.txt",
        authorship="user_authored",
    )
    await process_documents([doc], db_session)

    result = await db_session.execute(
        select(Topic).where(Topic.name == "integration-test-topic")
    )
    topic = result.scalar_one_or_none()
    assert topic is not None
    assert topic.name == "integration-test-topic"


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_people_persisted_globally(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """People created by the pipeline exist as standalone Person rows."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        people=["IntegrationTestPerson"],
    )

    doc = RawDocument(
        content="Testing person persistence.",
        source="file",
        source_ref="person-test.txt",
        authorship="user_authored",
    )
    await process_documents([doc], db_session)

    result = await db_session.execute(
        select(Person).where(Person.name == "IntegrationTestPerson")
    )
    person = result.scalar_one_or_none()
    assert person is not None


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_vector_search_finds_memory(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """After processing, vector search with the same embedding returns the memory."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="recounting adventure",
        meaning="loves travel",
        topics=["travel"],
        importance_score=0.9,
    )

    doc = RawDocument(
        content="I traveled through Europe for three months.",
        source="file",
        source_ref="travel-test.txt",
        authorship="user_authored",
    )
    await process_documents([doc], db_session)

    # Search using the same deterministic embedding
    service = MemoryService(db_session)
    results = await service.remember(DETERMINISTIC_EMBEDDING, limit=10)

    contents = [m.content for m in results]
    assert any("Europe" in c or "traveled" in c for c in contents)


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_skips_unkept_chunks(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Chunks where the analyzer returns keep=False are not stored."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(keep=False, importance_score=0.1)

    doc = RawDocument(
        content="lol ok",
        source="file",
        source_ref="skip-test.txt",
        authorship="other_reply",
    )
    count = await process_documents([doc], db_session)
    assert count == 0

    result = await db_session.execute(
        select(Memory).where(Memory.source_ref == "skip-test.txt")
    )
    assert result.scalar_one_or_none() is None


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_empty_content_skipped(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Documents with empty content are skipped entirely."""
    doc = RawDocument(
        content="",
        source="file",
        source_ref="empty-test.txt",
        authorship="user_authored",
    )
    count = await process_documents([doc], db_session)
    assert count == 0
    mock_embed.assert_not_called()
    mock_generate.assert_not_called()


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_multiple_documents(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Processing multiple documents creates one memory per kept chunk."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        topics=["batch-test"],
        importance_score=0.7,
    )

    docs = [
        RawDocument(
            content=f"Batch document number {i}.",
            source="file",
            source_ref=f"batch-{i}.txt",
            authorship="user_authored",
        )
        for i in range(3)
    ]
    count = await process_documents(docs, db_session)
    assert count == 3


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_stores_interaction_context(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Pipeline passes interaction_context through to the memory record."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="debating",
        meaning="strong opinion",
        interaction_context="challenged the user's view on climate",
        importance_score=0.9,
    )

    doc = RawDocument(
        content="That's not what the data shows about climate change.",
        source="reddit",
        source_ref="ctx-test.txt",
        authorship="received",
    )
    count = await process_documents([doc], db_session)
    assert count == 1

    result = await db_session.execute(
        select(Memory).where(Memory.source_ref == "ctx-test.txt")
    )
    memory = result.scalar_one()
    assert memory.interaction_context == "challenged the user's view on climate"


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_stores_locations(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Pipeline creates Location records from LLM-extracted locations."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="travel story",
        meaning="loves travel",
        topics=["travel"],
        locations=["Tokyo", "Mount Fuji"],
        importance_score=0.8,
    )

    doc = RawDocument(
        content="Visited Tokyo and climbed Mount Fuji.",
        source="instagram",
        source_ref="loc-test.txt",
        authorship="user_authored",
    )
    count = await process_documents([doc], db_session)
    assert count == 1

    result = await db_session.execute(
        select(Location).where(Location.name == "Tokyo")
    )
    loc = result.scalar_one_or_none()
    assert loc is not None
    assert loc.source == "instagram"

    result2 = await db_session.execute(
        select(Location).where(Location.name == "Mount Fuji")
    )
    assert result2.scalar_one_or_none() is not None


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_stores_life_events(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Pipeline creates LifeEvent records from LLM-extracted life events."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="announcing milestone",
        meaning="career growth",
        topics=["career"],
        life_events=[{"title": "Started new job at Acme Corp", "event_type": "career"}],
        importance_score=0.95,
    )

    doc = RawDocument(
        content="Excited to announce I started a new job at Acme Corp!",
        source="facebook",
        source_ref="event-test.txt",
        authorship="user_authored",
    )
    count = await process_documents([doc], db_session)
    assert count == 1

    result = await db_session.execute(
        select(LifeEvent).where(LifeEvent.title == "Started new job at Acme Corp")
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.event_type == "career"
    assert event.source == "facebook"


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_updates_relationships_for_received_messages(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Received messages create/update Relationship records."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="asking question",
        meaning="seeking advice",
        people=["Alice"],
        importance_score=0.6,
    )

    doc = RawDocument(
        content="Hey, what do you think about this?",
        source="gmail",
        source_ref="rel-test.txt",
        authorship="received",
        people=["Alice"],
    )
    count = await process_documents([doc], db_session)
    assert count == 1

    # Find the person
    person_result = await db_session.execute(
        select(Person).where(Person.name == "Alice")
    )
    person = person_result.scalar_one()

    # Check relationship was created
    rel_result = await db_session.execute(
        select(Relationship).where(
            Relationship.person_id == person.id,
            Relationship.platform == "gmail",
        )
    )
    rel = rel_result.scalar_one()
    assert rel.message_count == 1
    assert rel.relationship_type == "contact"
    assert rel.interaction_score == pytest.approx(0.01)


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_facebook_tags_create_relationships(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """Facebook posts with tagged people create tagged_together relationships."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(
        intent="sharing moment",
        meaning="values friendship",
        topics=["social"],
        importance_score=0.7,
    )

    doc = RawDocument(
        content="Great time at the concert!",
        source="facebook",
        source_ref="fb-tag-test.txt",
        authorship="user_authored",
        people=["TaggedFriend"],
    )
    count = await process_documents([doc], db_session)
    assert count == 1

    person_result = await db_session.execute(
        select(Person).where(Person.name == "TaggedFriend")
    )
    person = person_result.scalar_one()

    rel_result = await db_session.execute(
        select(Relationship).where(
            Relationship.person_id == person.id,
            Relationship.platform == "facebook",
        )
    )
    rel = rel_result.scalar_one()
    assert rel.relationship_type == "tagged_together"


@patch("engram.processing.analyzer.generate", new_callable=AsyncMock)
@patch("engram.processing.embedder.embed_texts", new_callable=AsyncMock)
async def test_pipeline_process_images_flag_off_by_default(
    mock_embed,
    mock_generate,
    db_session: AsyncSession,
):
    """By default, image_refs are NOT processed."""
    mock_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_generate.return_value = _analysis_json(importance_score=0.5)

    doc = RawDocument(
        content="Check out this photo!",
        source="facebook",
        source_ref="img-off-test.txt",
        authorship="user_authored",
        image_refs=["nonexistent_photo.jpg"],
    )
    # Should not raise even with nonexistent file, because process_images is False
    count = await process_documents([doc], db_session)
    assert count == 1
