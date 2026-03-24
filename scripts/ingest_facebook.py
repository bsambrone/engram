"""Ingest Facebook export through the full pipeline."""

import asyncio
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from engram.config import settings
from engram.ingestion.parsers.facebook import FacebookExportParser
from engram.processing.pipeline import process_documents


async def main():
    engine = create_async_engine(settings.database_url, pool_size=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    parser = FacebookExportParser(user_display_name="Bill Sambrone")
    docs = await parser.parse(Path("/home/bsambrone/engram-data/facebook"))
    total = len(docs)

    print(f"\n{'='*60}")
    print(f"  Ingesting Facebook: {total} documents")
    print(f"  (process_images=True for photo cross-referencing)")
    print(f"{'='*60}\n")

    created = 0
    errors = 0
    start = time.time()

    for i, doc in enumerate(docs):
        try:
            async with factory() as session:
                count = await process_documents([doc], session, process_images=True)
                await session.commit()
                created += count
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [{i+1}/{total}] ERROR: {e}")

        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(
                f"  [{i+1}/{total}] {created} memories, {errors} errors, "
                f"{rate:.1f}/sec, ETA: {eta:.0f}s"
            )

    elapsed = time.time() - start
    print(f"\n  Done: {created} memories from {total} docs in {elapsed:.0f}s ({errors} errors)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
