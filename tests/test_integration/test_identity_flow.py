"""Integration test: ingest data -> run inference -> identity populated -> query engram.

Creates memories directly, runs LLM-powered identity inference (mocked), verifies
that beliefs, preferences, and style profile are created, then queries the engram
RAG pipeline and verifies the response incorporates identity context.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.inference import run_inference
from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService
from engram.llm.rag import ask_engram
from engram.memory.repository import MemoryRepository

EMBEDDING_DIM = 1536
DETERMINISTIC_EMBEDDING = [0.1] * EMBEDDING_DIM


async def _seed_memories(session: AsyncSession, count: int = 5) -> None:
    """Create several user-authored memories with embeddings."""
    repo = MemoryRepository(session)
    contents = [
        "I strongly believe in open source software and contribute to several projects.",
        "I prefer working remotely because it gives me more time to focus.",
        "Coffee is essential to my morning routine, I cannot start the day without it.",
        "I think climate change is the most important issue of our time.",
        "I enjoy reading science fiction, especially Asimov and Le Guin.",
    ]
    for i, content in enumerate(contents[:count]):
        await repo.create(
            content=content,
            embedding=DETERMINISTIC_EMBEDDING,
            source="file",
            source_ref=f"identity-seed-{i}.txt",
            authorship="user",
            importance_score=0.8,
            confidence=1.0,
            status="active",
        )


def _inference_response() -> str:
    """Return a deterministic inference JSON response."""
    return json.dumps({
        "beliefs": [
            {
                "topic": "open source",
                "stance": "strong advocate",
                "nuance": "believes in community-driven development",
                "confidence": 0.9,
            },
            {
                "topic": "climate change",
                "stance": "urgent priority",
                "nuance": "considers it existential",
                "confidence": 0.85,
            },
        ],
        "preferences": [
            {
                "category": "work_style",
                "value": "remote",
                "strength": 0.9,
            },
            {
                "category": "beverage",
                "value": "coffee",
                "strength": 0.95,
            },
        ],
        "style": {
            "tone": "thoughtful",
            "humor_level": 0.4,
            "verbosity": 0.6,
            "formality": 0.5,
            "vocabulary_notes": "uses technical jargon comfortably",
            "communication_patterns": "tends to give detailed explanations",
        },
    })


@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_inference_creates_beliefs(mock_generate, db_session: AsyncSession):
    """run_inference extracts beliefs from memories and persists them."""
    await _seed_memories(db_session)

    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    mock_generate.return_value = _inference_response()

    result = await run_inference(db_session, profile.id)

    assert result["status"] == "ok"
    assert result["extracted"] >= 1

    # Verify beliefs were created
    repo = IdentityRepository(db_session)
    beliefs = await repo.list_beliefs(profile.id)
    belief_topics = {b.topic for b in beliefs}
    assert "open source" in belief_topics
    assert "climate change" in belief_topics

    # Check specific belief details
    os_beliefs = [b for b in beliefs if b.topic == "open source"]
    assert len(os_beliefs) == 1
    assert os_beliefs[0].stance == "strong advocate"
    assert os_beliefs[0].confidence == pytest.approx(0.9)
    assert os_beliefs[0].source == "inferred"


@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_inference_creates_preferences(mock_generate, db_session: AsyncSession):
    """run_inference extracts preferences and persists them."""
    await _seed_memories(db_session)

    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    mock_generate.return_value = _inference_response()
    await run_inference(db_session, profile.id)

    repo = IdentityRepository(db_session)
    preferences = await repo.list_preferences(profile.id)
    pref_categories = {p.category for p in preferences}
    assert "work_style" in pref_categories
    assert "beverage" in pref_categories

    coffee_prefs = [p for p in preferences if p.category == "beverage"]
    assert len(coffee_prefs) == 1
    assert coffee_prefs[0].value == "coffee"
    assert coffee_prefs[0].strength == pytest.approx(0.95)
    assert coffee_prefs[0].source == "inferred"


@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_inference_creates_style_profile(mock_generate, db_session: AsyncSession):
    """run_inference extracts communication style and persists it."""
    await _seed_memories(db_session)

    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    mock_generate.return_value = _inference_response()
    await run_inference(db_session, profile.id)

    repo = IdentityRepository(db_session)
    style = await repo.get_style(profile.id)
    assert style is not None
    assert style.tone == "thoughtful"
    assert style.humor_level == pytest.approx(0.4)
    assert style.verbosity == pytest.approx(0.6)
    assert style.formality == pytest.approx(0.5)
    assert style.vocabulary_notes == "uses technical jargon comfortably"
    assert style.source == "inferred"


@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_inference_no_memories_returns_early(
    mock_generate, db_session: AsyncSession
):
    """run_inference returns early when there are no memories to analyze."""
    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    result = await run_inference(db_session, profile.id)
    assert result["status"] == "no_memories"
    assert result["extracted"] == 0
    mock_generate.assert_not_called()


@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_get_full_identity_after_inference(
    mock_generate, db_session: AsyncSession
):
    """After inference, get_full_identity returns complete identity dict."""
    await _seed_memories(db_session)

    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    mock_generate.return_value = _inference_response()
    await run_inference(db_session, profile.id)

    identity = await identity_svc.get_full_identity(profile.id)

    assert len(identity["beliefs"]) >= 2
    assert len(identity["preferences"]) >= 2
    assert identity["style"] is not None
    assert identity["style"]["tone"] == "thoughtful"

    # Beliefs should have the expected structure
    belief_topics = {b["topic"] for b in identity["beliefs"]}
    assert "open source" in belief_topics


@patch("engram.llm.rag.generate", new_callable=AsyncMock)
@patch("engram.llm.rag.embed_texts", new_callable=AsyncMock)
@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_ask_engram_uses_identity_context(
    mock_inference_generate,
    mock_rag_embed,
    mock_rag_generate,
    db_session: AsyncSession,
):
    """ask_engram incorporates identity (beliefs, style) into its response."""
    await _seed_memories(db_session)

    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    # First, run inference to populate identity
    mock_inference_generate.return_value = _inference_response()
    await run_inference(db_session, profile.id)

    # Now ask engram a question
    mock_rag_embed.return_value = [DETERMINISTIC_EMBEDDING]
    mock_rag_generate.return_value = (
        "I am a strong advocate for open source software and believe in "
        "community-driven development."
    )

    response = await ask_engram(db_session, "What do you think about open source?")

    assert response.answer is not None
    assert len(response.answer) > 0
    assert "open source" in response.answer.lower()

    # Verify the LLM was called with a system prompt containing identity info
    call_args = mock_rag_generate.call_args
    system_prompt = call_args.kwargs.get("system") or call_args[0][0]
    assert "open source" in system_prompt.lower()
    assert "thoughtful" in system_prompt.lower()


@patch("engram.identity.inference.generate", new_callable=AsyncMock)
async def test_inference_does_not_overwrite_user_beliefs(
    mock_generate, db_session: AsyncSession
):
    """run_inference skips beliefs where a user-sourced belief already exists."""
    await _seed_memories(db_session)

    identity_svc = IdentityService(db_session)
    profile = await identity_svc.get_or_create_default_profile()

    # Manually create a user-sourced belief on "open source"
    repo = IdentityRepository(db_session)
    await repo.create_belief(
        profile.id,
        topic="open source",
        stance="moderate supporter",
        confidence=0.7,
        source="user",
    )

    mock_generate.return_value = _inference_response()
    await run_inference(db_session, profile.id)

    # The user-sourced belief should NOT be overwritten
    beliefs = await repo.list_beliefs(profile.id, topic="open source")
    user_beliefs = [b for b in beliefs if b.source == "user"]
    assert len(user_beliefs) == 1
    assert user_beliefs[0].stance == "moderate supporter"

    # No inferred belief should have been created for this topic
    inferred = [b for b in beliefs if b.source == "inferred"]
    assert len(inferred) == 0
