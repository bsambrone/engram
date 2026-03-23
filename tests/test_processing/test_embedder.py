"""Tests for the embedder with mocked OpenAI and Redis."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engram.processing.embedder import _cache_key, embed_texts


def _make_embedding(dim: int = 1536) -> list[float]:
    """Create a fake embedding vector."""
    return [0.01 * i for i in range(dim)]


def _mock_openai_response(texts: list[str], dim: int = 1536):
    """Build a mock OpenAI embeddings response."""
    data = []
    for i, _text in enumerate(texts):
        obj = SimpleNamespace(embedding=_make_embedding(dim), index=i)
        data.append(obj)
    return SimpleNamespace(data=data)


@pytest.mark.asyncio
async def test_embed_single_text():
    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(
        return_value=_mock_openai_response(["hello"])
    )

    with (
        patch("engram.processing.embedder.AsyncOpenAI", return_value=mock_client),
        patch("engram.processing.embedder._redis", None),
    ):
        result = await embed_texts(["hello"])
    assert len(result) == 1
    assert len(result[0]) == 1536
    mock_client.embeddings.create.assert_called_once()


@pytest.mark.asyncio
async def test_embed_batch():
    texts = [f"text {i}" for i in range(5)]
    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(
        return_value=_mock_openai_response(texts)
    )

    with (
        patch("engram.processing.embedder.AsyncOpenAI", return_value=mock_client),
        patch("engram.processing.embedder._redis", None),
    ):
        result = await embed_texts(texts)
    assert len(result) == 5
    for emb in result:
        assert len(emb) == 1536
    mock_client.embeddings.create.assert_called_once()


@pytest.mark.asyncio
async def test_embed_uses_cache():
    """When the embedding is cached in Redis, the OpenAI API should not be called."""
    cached_embedding = _make_embedding()
    cache_data = json.dumps(cached_embedding).encode()

    mock_redis = MagicMock()
    mock_redis.mget = MagicMock(return_value=[cache_data])

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock()

    with (
        patch("engram.processing.embedder.AsyncOpenAI", return_value=mock_client),
        patch("engram.processing.embedder._redis", mock_redis),
    ):
        result = await embed_texts(["hello"])

    assert len(result) == 1
    assert result[0] == cached_embedding
    # OpenAI should NOT have been called since everything was cached
    mock_client.embeddings.create.assert_not_called()


@pytest.mark.asyncio
async def test_embed_partial_cache():
    """Some texts cached, some not — only uncached texts hit OpenAI."""
    cached_embedding = _make_embedding()
    cache_data = json.dumps(cached_embedding).encode()

    # First text cached, second not
    mock_redis = MagicMock()
    mock_redis.mget = MagicMock(return_value=[cache_data, None])
    mock_redis.pipeline = MagicMock()
    pipe = MagicMock()
    mock_redis.pipeline.return_value = pipe
    pipe.__enter__ = MagicMock(return_value=pipe)
    pipe.__exit__ = MagicMock(return_value=False)
    pipe.execute = MagicMock()

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(
        return_value=_mock_openai_response(["world"])
    )

    with (
        patch("engram.processing.embedder.AsyncOpenAI", return_value=mock_client),
        patch("engram.processing.embedder._redis", mock_redis),
    ):
        result = await embed_texts(["hello", "world"])

    assert len(result) == 2
    # OpenAI was called only for the uncached text
    mock_client.embeddings.create.assert_called_once()
    call_args = mock_client.embeddings.create.call_args
    assert call_args.kwargs["input"] == ["world"]


@pytest.mark.asyncio
async def test_cache_key_deterministic():
    key1 = _cache_key("hello")
    key2 = _cache_key("hello")
    assert key1 == key2
    assert key1.startswith("engram:emb:")


@pytest.mark.asyncio
async def test_embed_large_batch():
    """Texts exceeding MAX_BATCH_SIZE are split into multiple API calls."""
    texts = [f"text {i}" for i in range(150)]

    mock_client = AsyncMock()

    # Return correct responses for each batch call
    def side_effect(**kwargs):
        batch_texts = kwargs["input"]
        return _mock_openai_response(batch_texts)

    mock_client.embeddings.create = AsyncMock(side_effect=side_effect)

    with (
        patch("engram.processing.embedder.AsyncOpenAI", return_value=mock_client),
        patch("engram.processing.embedder._redis", None),
    ):
        result = await embed_texts(texts)

    assert len(result) == 150
    # Should have been called twice: batch of 100 + batch of 50
    assert mock_client.embeddings.create.call_count == 2
