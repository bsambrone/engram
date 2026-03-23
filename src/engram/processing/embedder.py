"""OpenAI embeddings with Redis caching."""

import asyncio
import hashlib
import json
import logging

from openai import AsyncOpenAI

from engram.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis cache (optional — gracefully degrade if unavailable)
# ---------------------------------------------------------------------------
_redis = None
try:
    import redis as redis_lib

    _redis = redis_lib.Redis.from_url(settings.redis_url)
    _redis.ping()
except Exception:
    _redis = None

CACHE_TTL = 30 * 24 * 3600  # 30 days
MAX_BATCH_SIZE = 100
MAX_RETRIES = 3


def _cache_key(text: str) -> str:
    """Deterministic cache key based on content SHA-256."""
    return f"engram:emb:{hashlib.sha256(text.encode()).hexdigest()}"


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed *texts* using OpenAI, with optional Redis caching.

    - Checks Redis for cached embeddings before calling the API.
    - Batches API calls in groups of up to ``MAX_BATCH_SIZE``.
    - Retries transient failures with exponential back-off.
    - Stores new embeddings in Redis with a 30-day TTL.
    """
    results: list[list[float] | None] = [None] * len(texts)

    # ---- 1. Check cache --------------------------------------------------
    uncached_indices: list[int] = []

    if _redis is not None:
        keys = [_cache_key(t) for t in texts]
        try:
            cached_values = _redis.mget(keys)
            for i, val in enumerate(cached_values):
                if val is not None:
                    results[i] = json.loads(val)
                else:
                    uncached_indices.append(i)
        except Exception:
            logger.warning("Redis read failed; falling back to API for all texts")
            uncached_indices = list(range(len(texts)))
    else:
        uncached_indices = list(range(len(texts)))

    # ---- 2. Embed uncached texts via OpenAI ------------------------------
    if uncached_indices:
        uncached_texts = [texts[i] for i in uncached_indices]
        embeddings = await _call_openai(uncached_texts)

        for idx, emb in zip(uncached_indices, embeddings):
            results[idx] = emb

        # ---- 3. Store in cache -------------------------------------------
        if _redis is not None:
            try:
                with _redis.pipeline() as pipe:
                    for idx, emb in zip(uncached_indices, embeddings):
                        pipe.setex(
                            _cache_key(texts[idx]),
                            CACHE_TTL,
                            json.dumps(emb),
                        )
                    pipe.execute()
            except Exception:
                logger.warning("Redis write failed; embeddings not cached")

    return results  # type: ignore[return-value]


async def _call_openai(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API, batching if needed, with retries."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    all_embeddings: list[list[float]] = []

    for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[batch_start : batch_start + MAX_BATCH_SIZE]
        embs = await _embed_batch_with_retry(client, batch)
        all_embeddings.extend(embs)

    return all_embeddings


async def _embed_batch_with_retry(
    client: AsyncOpenAI,
    texts: list[str],
) -> list[list[float]]:
    """Embed a single batch with exponential back-off retries."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.embeddings.create(
                input=texts,
                model=settings.embedding_model,
            )
            # Sort by index to guarantee order
            sorted_data = sorted(response.data, key=lambda d: d.index)
            return [d.embedding for d in sorted_data]
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2**attempt
            logger.warning(
                "OpenAI embedding attempt %d failed; retrying in %ds",
                attempt + 1,
                wait,
            )
            await asyncio.sleep(wait)

    # Should never reach here, but satisfy type checker
    raise RuntimeError("Embedding failed after retries")  # pragma: no cover
