"""Processing pipeline orchestrator — normalize, chunk, embed, analyze, store."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from engram.ingestion.parsers.base import RawDocument
from engram.memory.service import MemoryService
from engram.processing.analyzer import analyze_chunk
from engram.processing.chunker import chunk_text
from engram.processing.embedder import embed_texts
from engram.processing.normalizer import normalize


async def process_documents(documents: list[RawDocument], session: AsyncSession) -> int:
    """Process raw documents through the full pipeline.

    Steps: normalize -> chunk -> embed -> analyze -> store.
    Returns the number of memories created.
    """
    memory_service = MemoryService(session)
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

            await memory_service.store_analyzed_chunk(
                content=analyzed.content,
                embedding=analyzed.embedding,
                source=doc.source,
                source_ref=doc.source_ref,
                authorship=analyzed.authorship,
                intent=analyzed.intent,
                meaning=analyzed.meaning,
                topics=analyzed.topics,
                people=analyzed.people,
                importance_score=analyzed.importance_score,
                timestamp=doc.timestamp,
            )
            count += 1

    return count
