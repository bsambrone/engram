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
from engram.processing.pipeline import process_documents

EMBEDDING_DIM = 1536
DETERMINISTIC_EMBEDDING = [0.1] * EMBEDDING_DIM


def _analysis_json(
    *,
    intent: str = "sharing experience",
    meaning: str = "values outdoor activities",
    topics: list[str] | None = None,
    people: list[str] | None = None,
    importance_score: float = 0.8,
    keep: bool = True,
) -> str:
    """Build a deterministic analysis JSON string."""
    return json.dumps({
        "intent": intent,
        "meaning": meaning,
        "topics": topics or [],
        "people": people or [],
        "importance_score": importance_score,
        "keep": keep,
    })


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
