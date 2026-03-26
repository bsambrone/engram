"""Tests for the RAG pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from engram.llm.rag import EngramResponse, ask_engram, build_prompt


class TestBuildPrompt:
    """Tests for the prompt builder."""

    def test_contains_name(self):
        prompt = build_prompt(
            name="Alice",
            beliefs=[],
            preferences=[],
            style=None,
            memories=[],
        )
        assert "Alice" in prompt

    def test_contains_beliefs(self):
        beliefs = [
            {"topic": "testing", "stance": "essential", "confidence": 0.9},
        ]
        prompt = build_prompt(
            name="Bob",
            beliefs=beliefs,
            preferences=[],
            style=None,
            memories=[],
        )
        assert "testing" in prompt
        assert "essential" in prompt

    def test_contains_memories(self):
        memories = [
            {
                "content": "I love hiking in the mountains",
                "intent": "personal",
                "confidence": 0.8,
                "timestamp": "2025-01-01T00:00:00",
            },
        ]
        prompt = build_prompt(
            name="Carol",
            beliefs=[],
            preferences=[],
            style=None,
            memories=memories,
        )
        assert "hiking" in prompt

    def test_contains_preferences(self):
        preferences = [
            {"category": "food", "value": "sushi", "strength": 0.9},
        ]
        prompt = build_prompt(
            name="Dave",
            beliefs=[],
            preferences=preferences,
            style=None,
            memories=[],
        )
        assert "sushi" in prompt

    def test_contains_style(self):
        style = {
            "tone": "casual",
            "humor_level": 0.7,
            "verbosity": 0.5,
            "formality": 0.3,
            "vocabulary_notes": "uses slang",
            "communication_patterns": "short sentences",
        }
        prompt = build_prompt(
            name="Eve",
            beliefs=[],
            preferences=[],
            style=style,
            memories=[],
        )
        assert "casual" in prompt


def _make_fake_memory(**overrides):
    """Create a fake memory object for testing."""
    defaults = {
        "id": uuid.uuid4(),
        "content": "Test memory content",
        "intent": "personal",
        "meaning": "test meaning",
        "confidence": 0.8,
        "authorship": "user_authored",
        "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_fake_profile():
    """Create a fake profile object."""
    return SimpleNamespace(id=uuid.uuid4(), name="TestUser")


def _make_fake_identity():
    """Create a fake identity dict."""
    return {
        "beliefs": [
            {
                "id": str(uuid.uuid4()),
                "topic": "technology",
                "stance": "optimistic",
                "confidence": 0.9,
            },
        ],
        "preferences": [
            {"category": "language", "value": "Python", "strength": 0.95},
        ],
        "style": {
            "tone": "friendly",
            "humor_level": 0.5,
            "verbosity": 0.6,
            "formality": 0.4,
            "vocabulary_notes": None,
            "communication_patterns": None,
        },
    }


@pytest.mark.asyncio
async def test_ask_engram_owner():
    """Owner access returns memory_refs and belief_refs."""
    fake_memories = [_make_fake_memory(), _make_fake_memory()]
    fake_profile = _make_fake_profile()
    fake_identity = _make_fake_identity()

    with (
        patch("engram.llm.rag.embed_texts", new_callable=AsyncMock) as mock_embed,
        patch("engram.llm.rag.generate", new_callable=AsyncMock) as mock_generate,
        patch("engram.llm.rag.IdentityService") as mock_id_svc_cls,
        patch("engram.llm.rag.MemoryService") as mock_mem_svc_cls,
    ):
        mock_embed.return_value = [[0.1] * 1536]
        mock_generate.return_value = "This is the engram's answer."

        mock_id_svc = mock_id_svc_cls.return_value
        mock_id_svc.get_or_create_default_profile = AsyncMock(return_value=fake_profile)
        mock_id_svc.get_full_identity = AsyncMock(return_value=fake_identity)

        mock_mem_svc = mock_mem_svc_cls.return_value
        mock_mem_svc.remember = AsyncMock(return_value=fake_memories)

        session = AsyncMock()
        result = await ask_engram(session, "What do I think about tech?", is_owner=True)

    assert isinstance(result, EngramResponse)
    assert result.answer == "This is the engram's answer."
    assert result.memory_refs is not None
    assert len(result.memory_refs) == 2
    assert result.belief_refs is not None
    assert len(result.belief_refs) == 1
    assert result.confidence > 0

    # Verify generate was called with a system prompt and the user query
    mock_generate.assert_awaited_once()
    call_kwargs = mock_generate.call_args
    assert call_kwargs.kwargs["user"] == "What do I think about tech?"


@pytest.mark.asyncio
async def test_ask_engram_shared():
    """Shared access returns NO memory_refs and NO belief_refs."""
    fake_memories = [_make_fake_memory()]
    fake_profile = _make_fake_profile()
    fake_identity = _make_fake_identity()

    with (
        patch("engram.llm.rag.embed_texts", new_callable=AsyncMock) as mock_embed,
        patch("engram.llm.rag.generate", new_callable=AsyncMock) as mock_generate,
        patch("engram.llm.rag.IdentityService") as mock_id_svc_cls,
        patch("engram.llm.rag.MemoryService") as mock_mem_svc_cls,
    ):
        mock_embed.return_value = [[0.1] * 1536]
        mock_generate.return_value = "Shared answer."

        mock_id_svc = mock_id_svc_cls.return_value
        mock_id_svc.get_or_create_default_profile = AsyncMock(return_value=fake_profile)
        mock_id_svc.get_full_identity = AsyncMock(return_value=fake_identity)

        mock_mem_svc = mock_mem_svc_cls.return_value
        mock_mem_svc.remember = AsyncMock(return_value=fake_memories)

        session = AsyncMock()
        result = await ask_engram(session, "Hello?", is_owner=False)

    assert isinstance(result, EngramResponse)
    assert result.answer == "Shared answer."
    assert result.memory_refs is None
    assert result.belief_refs is None

    # Shared access should pass visibility="active"
    mock_mem_svc.remember.assert_awaited_once()
    call_kwargs = mock_mem_svc.remember.call_args
    assert call_kwargs.kwargs.get("visibility") == "active"


@pytest.mark.asyncio
async def test_ask_engram_no_memories():
    """When no memories found, response has a caveat."""
    fake_profile = _make_fake_profile()
    fake_identity = _make_fake_identity()

    with (
        patch("engram.llm.rag.embed_texts", new_callable=AsyncMock) as mock_embed,
        patch("engram.llm.rag.generate", new_callable=AsyncMock) as mock_generate,
        patch("engram.llm.rag.IdentityService") as mock_id_svc_cls,
        patch("engram.llm.rag.MemoryService") as mock_mem_svc_cls,
    ):
        mock_embed.return_value = [[0.1] * 1536]
        mock_generate.return_value = "Not much data."

        mock_id_svc = mock_id_svc_cls.return_value
        mock_id_svc.get_or_create_default_profile = AsyncMock(return_value=fake_profile)
        mock_id_svc.get_full_identity = AsyncMock(return_value=fake_identity)

        mock_mem_svc = mock_mem_svc_cls.return_value
        mock_mem_svc.remember = AsyncMock(return_value=[])

        session = AsyncMock()
        result = await ask_engram(session, "Obscure question", is_owner=True)

    assert len(result.caveats) > 0
    assert "Limited data available" in result.caveats
    assert result.confidence == 0.0
