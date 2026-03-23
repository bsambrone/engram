import json
from unittest.mock import patch

import pytest

from engram.processing.analyzer import AnalyzedChunk, analyze_chunk


@pytest.fixture
def dummy_embedding():
    return [0.1] * 1536


@patch("engram.processing.analyzer.generate")
async def test_analyze_user_content(mock_generate, dummy_embedding):
    mock_generate.return_value = json.dumps(
        {
            "intent": "expressing opinion",
            "meaning": "values work-life balance",
            "topics": ["remote work", "productivity"],
            "people": [],
            "importance_score": 0.8,
            "keep": True,
        }
    )
    result = await analyze_chunk("I prefer remote work", "user_authored", dummy_embedding)
    assert isinstance(result, AnalyzedChunk)
    assert result.intent == "expressing opinion"
    assert result.meaning == "values work-life balance"
    assert "remote work" in result.topics
    assert "productivity" in result.topics
    assert result.people == []
    assert result.importance_score == 0.8
    assert result.keep is True
    assert result.content == "I prefer remote work"
    assert result.authorship == "user_authored"
    assert result.embedding == dummy_embedding


@patch("engram.processing.analyzer.generate")
async def test_analyze_irrelevant_other_content(mock_generate, dummy_embedding):
    mock_generate.return_value = json.dumps(
        {
            "intent": "casual",
            "meaning": "none",
            "topics": [],
            "people": [],
            "importance_score": 0.1,
            "keep": False,
        }
    )
    result = await analyze_chunk("lol", "other_reply", dummy_embedding)
    assert result.keep is False
    assert result.importance_score == 0.1
    assert result.topics == []


@patch("engram.processing.analyzer.generate")
async def test_analyze_handles_bad_json(mock_generate, dummy_embedding):
    mock_generate.return_value = "not valid json"
    result = await analyze_chunk("test", "user_authored", dummy_embedding)
    assert result.keep is True  # fallback: user content is kept
    assert result.importance_score == 0.5
    assert result.topics == []
    assert result.people == []


@patch("engram.processing.analyzer.generate")
async def test_analyze_handles_bad_json_other(mock_generate, dummy_embedding):
    mock_generate.return_value = "not valid json"
    result = await analyze_chunk("test", "other_reply", dummy_embedding)
    assert result.keep is False  # fallback: non-user content is not kept
    assert result.importance_score == 0.5


@patch("engram.processing.analyzer.generate")
async def test_analyze_strips_markdown_fences(mock_generate, dummy_embedding):
    mock_generate.return_value = (
        '```json\n{"intent": "sharing", "meaning": "cares about friends",'
        ' "topics": ["friendship"], "people": ["Alice"],'
        ' "importance_score": 0.7, "keep": true}\n```'
    )
    result = await analyze_chunk("Alice is my best friend", "user_authored", dummy_embedding)
    assert result.intent == "sharing"
    assert result.people == ["Alice"]
    assert result.topics == ["friendship"]
    assert result.keep is True


@patch("engram.processing.analyzer.generate")
async def test_analyze_with_interaction_context(mock_generate, dummy_embedding):
    mock_generate.return_value = json.dumps(
        {
            "intent": "debating",
            "meaning": "firm on position",
            "topics": ["politics"],
            "people": ["Bob"],
            "importance_score": 0.9,
            "keep": True,
            "interaction_context": "disagreement with Bob",
        }
    )
    result = await analyze_chunk("I disagree with Bob", "user_authored", dummy_embedding)
    assert result.interaction_context == "disagreement with Bob"


@patch("engram.processing.analyzer.generate")
async def test_analyze_exception_fallback(mock_generate, dummy_embedding):
    mock_generate.side_effect = Exception("API error")
    result = await analyze_chunk("test content", "user_authored", dummy_embedding)
    assert result.keep is True
    assert result.importance_score == 0.5
    assert result.intent is None
    assert result.meaning is None


@patch("engram.processing.analyzer.generate")
async def test_analyze_passes_correct_prompt(mock_generate, dummy_embedding):
    mock_generate.return_value = json.dumps(
        {
            "intent": "test",
            "meaning": "test",
            "topics": [],
            "people": [],
            "importance_score": 0.5,
            "keep": True,
        }
    )
    await analyze_chunk("hello world", "user_authored", dummy_embedding)
    mock_generate.assert_called_once()
    call_kwargs = mock_generate.call_args
    assert "Authorship: user_authored" in call_kwargs[1]["user"] or call_kwargs[0][1]
    assert "hello world" in call_kwargs[1]["user"] or call_kwargs[0][1]
