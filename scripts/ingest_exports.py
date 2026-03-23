"""Script to ingest real data exports into the engram."""

import asyncio
import sys
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from engram.config import settings
from engram.ingestion.parsers.base import RawDocument
from engram.memory.service import MemoryService
from engram.photos.service import PhotoService
from engram.processing.analyzer import analyze_chunk
from engram.processing.chunker import chunk_text
from engram.processing.embedder import embed_texts
from engram.processing.normalizer import normalize

DATABASE_URL = settings.database_url


async def process_single_doc(
    doc: RawDocument,
    memory_service: MemoryService,
    session: AsyncSession,
    index: int,
    total: int,
) -> int:
    """Process a single document through the pipeline. Returns memories created."""
    if not doc.content or not doc.content.strip():
        return 0

    normalized = normalize(doc.content)
    if not normalized:
        return 0

    chunks = chunk_text(normalized)
    embeddings = await embed_texts(chunks)

    created = 0
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
        created += 1

    return created


async def ingest_platform(
    platform: str,
    docs: list[RawDocument],
    engine,
    batch_size: int = 10,
):
    """Ingest documents for a platform with progress tracking."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    total = len(docs)
    memories_created = 0
    errors = 0
    start = time.time()

    print(f"\n{'='*60}")
    print(f"  Ingesting {platform}: {total} documents")
    print(f"{'='*60}\n")

    for i, doc in enumerate(docs):
        try:
            async with factory() as session:
                memory_service = MemoryService(session)
                count = await process_single_doc(doc, memory_service, session, i, total)
                await session.commit()
                memories_created += count
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{total}] ERROR: {e}")

        if (i + 1) % 10 == 0 or (i + 1) == total:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(
                f"  [{i+1}/{total}] "
                f"{memories_created} memories, {errors} errors, "
                f"{rate:.1f} docs/sec, ETA: {eta:.0f}s"
            )

    elapsed = time.time() - start
    print(f"\n  Done: {memories_created} memories from {total} docs in {elapsed:.0f}s ({errors} errors)")
    return memories_created


async def ingest_photos(photo_paths: list[Path], engine):
    """Ingest photos with vision analysis."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    total = len(photo_paths)
    print(f"\n{'='*60}")
    print(f"  Processing {total} photos with vision analysis")
    print(f"{'='*60}\n")

    for i, photo_path in enumerate(photo_paths):
        try:
            async with factory() as session:
                photo_service = PhotoService(session, settings.photo_storage_dir)
                content = photo_path.read_bytes()
                photo = await photo_service.upload_photo(
                    file_content=content,
                    filename=photo_path.name,
                    source="instagram",
                    is_reference=False,
                )
                # Run vision analysis
                await photo_service.analyze_photo(photo.id)
                await session.commit()
                print(f"  [{i+1}/{total}] {photo_path.name}: {photo.description or 'analyzed'}")
        except Exception as e:
            print(f"  [{i+1}/{total}] ERROR on {photo_path.name}: {e}")

    print(f"\n  Done: {total} photos processed")


async def main():
    engine = create_async_engine(DATABASE_URL, pool_size=5)

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("reddit", "all"):
        from engram.ingestion.parsers.reddit import RedditExportParser

        parser = RedditExportParser()
        reddit_path = Path("/home/bsambrone/engram-data/reddit")
        if parser.validate(reddit_path):
            docs = await parser.parse(reddit_path)
            await ingest_platform("Reddit", docs, engine)
        else:
            print("Reddit export not found or invalid")

    if mode in ("instagram", "all"):
        from engram.ingestion.parsers.instagram import InstagramExportParser

        parser = InstagramExportParser()
        ig_path = Path("/home/bsambrone/engram-data/instagram")
        if parser.validate(ig_path):
            docs = await parser.parse(ig_path)
            await ingest_platform("Instagram", docs, engine)

            # Process photos
            photo_dir = ig_path / "media" / "posts"
            if photo_dir.exists():
                photos = list(photo_dir.rglob("*.jpg")) + list(photo_dir.rglob("*.png"))
                if photos:
                    await ingest_photos(photos, engine)
        else:
            print("Instagram export not found or invalid")

    if mode in ("gmail", "all"):
        from engram.ingestion.parsers.gmail import GmailExportParser

        parser = GmailExportParser(user_email="bsambrone@gmail.com")
        gmail_path = Path("/home/bsambrone/engram-data/google/Takeout/Mail")
        if parser.validate(gmail_path):
            print("\nParsing Gmail export (sent emails only)...")
            all_docs = await parser.parse(gmail_path)
            # Filter to sent emails only
            sent_docs = [d for d in all_docs if d.authorship == "user_authored"]
            print(f"Found {len(sent_docs)} sent emails out of {len(all_docs)} total")
            await ingest_platform("Gmail (sent)", sent_docs, engine)
        else:
            print("Gmail export not found or invalid")

    await engine.dispose()
    print("\nAll done!")


if __name__ == "__main__":
    asyncio.run(main())
