"""Shared test fixtures."""

import hashlib
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from engram.models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram_test"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    return engine


@pytest.fixture(autouse=True)
async def setup_database(test_engine):
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with auth token."""
    from engram.db import get_session
    from engram.main import app
    from engram.models.auth import AccessToken

    # Create a test access token
    token_value = "test-token-" + uuid.uuid4().hex[:16]
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()
    access_token = AccessToken(
        name="test-token",
        token_hash=token_hash,
        access_level="admin",
    )
    db_session.add(access_token)
    await db_session.flush()

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_value}"},
    ) as client:
        yield client

    app.dependency_overrides.clear()
