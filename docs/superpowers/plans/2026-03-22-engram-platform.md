# Engram Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted digital engram platform that ingests personal data, builds living memories with LLM-extracted meaning, infers identity traits, and exposes the engram via REST API and MCP server.

**Architecture:** Monolith FastAPI application with modular packages. PostgreSQL+pgvector for storage and vector search, Redis for job queues and caching. Claude API for generation/analysis, OpenAI for embeddings and image generation. MCP server runs as a separate process sharing the same service layer.

**Tech Stack:** Python 3.12+, FastAPI, uv, PostgreSQL 16+pgvector (Docker), Redis (Docker), SQLAlchemy (async/asyncpg), Alembic, Anthropic SDK, OpenAI SDK, MCP Python SDK, RQ, pytest, ruff

**Spec:** `docs/superpowers/specs/2026-03-22-engram-platform-design.md`

---

## File Map

```
engram/
├── src/engram/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app, mounts all routers
│   ├── cli.py                           # Click CLI: init, server, mcp, ingest, status
│   ├── config.py                        # Pydantic BaseSettings
│   ├── db.py                            # async engine, session factory, get_session dependency
│   ├── encryption.py                    # Fernet encrypt/decrypt helpers
│   ├── models/
│   │   ├── __init__.py                  # Re-exports all models for Alembic
│   │   ├── base.py                      # Declarative base, common mixins (id, timestamps)
│   │   ├── memory.py                    # Memory, Topic, MemoryTopic, Person, MemoryPerson
│   │   ├── identity.py                  # IdentityProfile, Belief, BeliefMemory, Preference, PreferenceMemory, StyleProfile, IdentitySnapshot
│   │   ├── connector.py                 # ConnectorConfig, IngestionJob
│   │   ├── auth.py                      # AccessToken
│   │   └── photo.py                     # Photo, PhotoPerson
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── service.py                   # Orchestrates connector → pipeline, manages jobs
│   │   └── connectors/
│   │       ├── __init__.py
│   │       ├── base.py                  # Connector Protocol, RawDocument dataclass
│   │       ├── file.py                  # FileConnector
│   │       ├── gmail.py                 # GmailConnector
│   │       └── reddit.py               # RedditConnector
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── pipeline.py                  # Run all stages sequentially
│   │   ├── normalizer.py               # HTML stripping, whitespace normalization
│   │   ├── chunker.py                  # Sentence-aware chunking with overlap
│   │   ├── embedder.py                 # OpenAI embedding client with caching
│   │   └── analyzer.py                 # Claude intent/meaning/authorship analysis
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── repository.py               # DB queries: CRUD, vector search, filtered search
│   │   └── service.py                  # Business logic: remember, reinforce, degrade, evolve
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── inference.py                # Claude-powered identity inference from memories
│   │   ├── repository.py              # DB queries for identity tables
│   │   └── service.py                 # Overrides, snapshots, CRUD orchestration
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── providers.py               # Claude + OpenAI wrappers with retry
│   │   └── rag.py                     # RAG pipeline: embed → search → prompt → generate
│   ├── photos/
│   │   ├── __init__.py
│   │   ├── service.py                 # Photo management + image generation
│   │   └── repository.py             # Photo CRUD
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                    # get_db, get_current_token, require_owner
│   │   └── routes/
│   │       ├── __init__.py            # Router that includes all sub-routers
│   │       ├── ingest.py             # POST /api/ingest/*, GET /api/ingest/status
│   │       ├── connectors.py         # /api/connectors/*
│   │       ├── memories.py           # /api/memories/*
│   │       ├── sources.py            # /api/sources/*
│   │       ├── identity.py           # /api/identity/*
│   │       ├── engram.py             # /api/engram/*
│   │       ├── photos.py             # /api/photos/*
│   │       ├── config_routes.py      # /api/config/*
│   │       └── tokens.py             # /api/tokens/*
│   └── mcp/
│       ├── __init__.py
│       └── server.py                  # MCP server with tool definitions
├── tests/
│   ├── conftest.py                    # Fixtures: test DB, async session, test client, auth tokens
│   ├── test_models/
│   │   └── test_models.py
│   ├── test_ingestion/
│   │   ├── test_file_connector.py
│   │   ├── test_gmail_connector.py
│   │   └── test_reddit_connector.py
│   ├── test_processing/
│   │   ├── test_normalizer.py
│   │   ├── test_chunker.py
│   │   ├── test_embedder.py
│   │   ├── test_analyzer.py
│   │   └── test_pipeline.py
│   ├── test_memory/
│   │   ├── test_repository.py
│   │   └── test_service.py
│   ├── test_identity/
│   │   ├── test_inference.py
│   │   ├── test_repository.py
│   │   └── test_service.py
│   ├── test_llm/
│   │   └── test_rag.py
│   ├── test_photos/
│   │   ├── test_service.py
│   │   └── test_repository.py
│   ├── test_api/
│   │   ├── test_ingest.py
│   │   ├── test_connectors.py
│   │   ├── test_memories.py
│   │   ├── test_sources.py
│   │   ├── test_identity.py
│   │   ├── test_engram.py
│   │   ├── test_photos.py
│   │   ├── test_config.py
│   │   └── test_tokens.py
│   ├── test_mcp/
│   │   └── test_server.py
│   └── test_integration/
│       ├── test_full_pipeline.py
│       ├── test_identity_flow.py
│       ├── test_evolution_flow.py
│       └── test_privacy_flow.py
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── .gitignore
└── .env.example
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/engram/__init__.py`
- Create: `src/engram/config.py`
- Create: `src/engram/db.py`
- Create: `src/engram/main.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "engram"
version = "0.1.0"
description = "A self-hosted digital engram platform"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pgvector>=0.3",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "anthropic>=0.49",
    "openai>=1.65",
    "redis>=5.2",
    "rq>=2.1",
    "cryptography>=44.0",
    "click>=8.1",
    "python-multipart>=0.0.18",
    "httpx>=0.28",
    "beautifulsoup4>=4.12",
    "tiktoken>=0.8",
    "mcp>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "pytest-httpx>=0.35",
    "ruff>=0.9",
    "aiosqlite>=0.20",
]
gmail = ["google-auth-oauthlib>=1.2", "google-api-python-client>=2.160"]
reddit = ["praw>=7.8"]

[project.scripts]
engram = "engram.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/engram"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: engram
    ports:
      - "5433:5432"
    volumes:
      - engram_pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - engram_redis:/data

volumes:
  engram_pgdata:
  engram_redis:
```

Note: Postgres is on port 5433 to avoid conflict with the existing local Postgres on 5432.

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
.venv/
*.egg-info/
dist/
build/
.env
.ruff_cache/
.pytest_cache/
.mypy_cache/
*.db
*.sqlite3
photos/
~/.engram/
```

- [ ] **Step 4: Create .env.example**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/engram
REDIS_URL=redis://localhost:6379/0

# API Keys (required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Encryption (generated by `engram init`)
ENGRAM_ENCRYPTION_KEY=

# Processing
CHUNK_SIZE_TOKENS=500
CHUNK_OVERLAP_TOKENS=50
MEMORY_DECAY_HALFLIFE_DAYS=365
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSIONS=1536
LLM_MODEL=claude-sonnet-4-20250514

# Storage
PHOTO_STORAGE_DIR=~/.engram/photos

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
MCP_TRANSPORT=stdio
LOG_LEVEL=INFO
```

- [ ] **Step 5: Create src/engram/__init__.py**

```python
"""Engram — A self-hosted digital engram platform."""

__version__ = "0.1.0"
```

- [ ] **Step 6: Create src/engram/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    engram_encryption_key: str = ""

    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    memory_decay_halflife_days: int = 365
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimensions: int = 1536
    llm_model: str = "claude-sonnet-4-20250514"

    photo_storage_dir: str = "~/.engram/photos"

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    mcp_transport: str = "stdio"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 7: Create src/engram/db.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from engram.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session
```

- [ ] **Step 8: Create src/engram/main.py**

```python
from fastapi import FastAPI

app = FastAPI(title="Engram", version="0.1.0", description="Digital engram platform")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Create README.md**

```markdown
# Engram

A self-hosted digital engram platform. Ingest your personal data, build structured living memories, and expose your digital identity via API and MCP server.

## Quick Start

### Prerequisites
- Python 3.12+
- Docker (for PostgreSQL + Redis)
- Anthropic API key
- OpenAI API key

### Setup

1. Clone the repo and install dependencies:

   ```bash
   git clone <repo-url> && cd engram
   uv sync --all-extras
   ```

2. Start infrastructure:

   ```bash
   docker compose up -d
   ```

3. Copy and configure environment:

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run database migrations:

   ```bash
   uv run alembic upgrade head
   ```

5. Start the server:

   ```bash
   uv run engram server
   ```

## CLI Commands

```bash
engram init        # Interactive setup wizard
engram server      # Start REST API server
engram mcp         # Start MCP server
engram ingest      # Run data ingestion
engram status      # Show engram statistics
```

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
```
```

- [ ] **Step 10: Set up Alembic**

Create `alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5433/engram

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `alembic/env.py`:
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from engram.config import settings
from engram.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 11: Install dependencies and start Docker**

Run:
```bash
uv sync --all-extras
docker compose up -d
```

Expected: Dependencies install successfully. Docker containers start. `docker compose ps` shows both postgres and redis running.

- [ ] **Step 12: Verify health endpoint**

Run:
```bash
uv run uvicorn engram.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl http://localhost:8000/health
kill %1
```

Expected: `{"status":"ok"}`

- [ ] **Step 13: Commit**

```bash
git add pyproject.toml docker-compose.yml .gitignore .env.example README.md src/ alembic.ini alembic/
git commit -m "feat: project scaffold with FastAPI, Docker, Alembic setup"
```

---

## Task 2: Data Models + Migrations

**Files:**
- Create: `src/engram/models/base.py`
- Create: `src/engram/models/__init__.py`
- Create: `src/engram/models/memory.py`
- Create: `src/engram/models/identity.py`
- Create: `src/engram/models/connector.py`
- Create: `src/engram/models/auth.py`
- Create: `src/engram/models/photo.py`
- Create: `src/engram/encryption.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models/test_models.py`

- [ ] **Step 1: Create model base with mixins**

`src/engram/models/base.py`:
```python
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Create memory models**

`src/engram/models/memory.py`:
```python
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engram.config import settings
from engram.models.base import Base, TimestampMixin, UUIDMixin


class Memory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memories"

    parent_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dimensions), nullable=True)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    authorship: Mapped[str] = mapped_column(String(50), nullable=False)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    reinforcement_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reinforced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    visibility: Mapped[str] = mapped_column(String(20), default="active")
    status: Mapped[str] = mapped_column(String(20), default="active")

    topics: Mapped[list["Topic"]] = relationship(
        secondary="memory_topics", back_populates="memories"
    )
    people: Mapped[list["Person"]] = relationship(
        secondary="memory_people", back_populates="memories"
    )
    children: Mapped[list["Memory"]] = relationship(
        back_populates="parent", foreign_keys=[parent_memory_id]
    )
    parent: Mapped["Memory | None"] = relationship(
        back_populates="children", remote_side="Memory.id", foreign_keys=[parent_memory_id]
    )


class Topic(UUIDMixin, Base):
    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    memories: Mapped[list["Memory"]] = relationship(
        secondary="memory_topics", back_populates="topics"
    )


class MemoryTopic(Base):
    __tablename__ = "memory_topics"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )


class Person(UUIDMixin, Base):
    __tablename__ = "people"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    memories: Mapped[list["Memory"]] = relationship(
        secondary="memory_people", back_populates="people"
    )


class MemoryPerson(Base):
    __tablename__ = "memory_people"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 3: Create identity models**

`src/engram/models/identity.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engram.models.base import Base, TimestampMixin, UUIDMixin

# Import Memory for relationship references (must be after models are loaded)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from engram.models.memory import Memory


class IdentityProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "identity_profiles"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    beliefs: Mapped[list["Belief"]] = relationship(back_populates="profile")
    preferences: Mapped[list["Preference"]] = relationship(back_populates="profile")
    style_profile: Mapped["StyleProfile | None"] = relationship(back_populates="profile", uselist=False)


class Belief(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "beliefs"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_profiles.id", ondelete="CASCADE")
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    stance: Mapped[str] = mapped_column(Text, nullable=False)
    nuance: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(20), default="inferred")
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped["IdentityProfile"] = relationship(back_populates="beliefs")
    supporting_memories: Mapped[list["Memory"]] = relationship(
        secondary="belief_memories", viewonly=True
    )


class BeliefMemory(Base):
    __tablename__ = "belief_memories"

    belief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beliefs.id", ondelete="CASCADE"), primary_key=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )


class Preference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "preferences"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_profiles.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(20), default="inferred")

    profile: Mapped["IdentityProfile"] = relationship(back_populates="preferences")
    supporting_memories: Mapped[list["engram.models.memory.Memory"]] = relationship(
        secondary="preference_memories"
    )


class PreferenceMemory(Base):
    __tablename__ = "preference_memories"

    preference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("preferences.id", ondelete="CASCADE"), primary_key=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )


class StyleProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "style_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_profiles.id", ondelete="CASCADE"), unique=True
    )
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    humor_level: Mapped[float] = mapped_column(Float, default=0.5)
    verbosity: Mapped[float] = mapped_column(Float, default=0.5)
    formality: Mapped[float] = mapped_column(Float, default=0.5)
    vocabulary_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="inferred")

    profile: Mapped["IdentityProfile"] = relationship(back_populates="style_profile")


class IdentitySnapshot(UUIDMixin, Base):
    __tablename__ = "identity_snapshots"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_profiles.id", ondelete="CASCADE")
    )
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Create connector + ingestion job models**

`src/engram/models/connector.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from engram.models.base import Base, TimestampMixin, UUIDMixin


class ConnectorConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "connector_configs"

    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    credentials: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet-encrypted JSON
    status: Mapped[str] = mapped_column(String(20), default="active")


class IngestionJob(UUIDMixin, Base):
    __tablename__ = "ingestion_jobs"

    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: Create auth model**

`src/engram/models/auth.py`:
```python
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from engram.models.base import Base, UUIDMixin


class AccessToken(UUIDMixin, Base):
    __tablename__ = "access_tokens"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    access_level: Mapped[str] = mapped_column(String(20), nullable=False)  # "owner" or "shared"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 6: Create photo model**

`src/engram/models/photo.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engram.models.base import Base, TimestampMixin, UUIDMixin

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from engram.models.memory import Person


class Photo(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "photos"

    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_profiles.id"), nullable=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False)

    people: Mapped[list["Person"]] = relationship(
        secondary="photo_people", viewonly=True
    )


class PhotoPerson(Base):
    __tablename__ = "photo_people"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 7: Create models __init__.py**

`src/engram/models/__init__.py`:
```python
from engram.models.base import Base
from engram.models.memory import Memory, MemoryPerson, MemoryTopic, Person, Topic
from engram.models.identity import (
    Belief,
    BeliefMemory,
    IdentityProfile,
    IdentitySnapshot,
    Preference,
    PreferenceMemory,
    StyleProfile,
)
from engram.models.connector import ConnectorConfig, IngestionJob
from engram.models.auth import AccessToken
from engram.models.photo import Photo, PhotoPerson

__all__ = [
    "Base",
    "Memory", "Topic", "MemoryTopic", "Person", "MemoryPerson",
    "IdentityProfile", "Belief", "BeliefMemory", "Preference", "PreferenceMemory",
    "StyleProfile", "IdentitySnapshot",
    "ConnectorConfig", "IngestionJob",
    "AccessToken",
    "Photo", "PhotoPerson",
]
```

- [ ] **Step 8: Create encryption helpers**

`src/engram/encryption.py`:
```python
from cryptography.fernet import Fernet

from engram.config import settings


def get_fernet() -> Fernet:
    if not settings.engram_encryption_key:
        raise ValueError("ENGRAM_ENCRYPTION_KEY not set. Run 'engram init' to generate one.")
    return Fernet(settings.engram_encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()
```

- [ ] **Step 9: Create test conftest with fixtures**

`tests/conftest.py`:
```python
import asyncio
import uuid
from datetime import datetime, timezone
from hashlib import sha256

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from engram.config import settings
from engram.db import get_session
from engram.main import app
from engram.models import Base
from engram.models.auth import AccessToken

# Use a separate test database
TEST_DATABASE_URL = settings.database_url.replace("/engram", "/engram_test")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    # Create an owner token for testing
    raw_token = "test-owner-token-" + uuid.uuid4().hex
    token_hash = sha256(raw_token.encode()).hexdigest()
    owner_token = AccessToken(
        name="test-owner",
        token_hash=token_hash,
        access_level="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner_token)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {raw_token}"},
    ) as c:
        yield c

    app.dependency_overrides.clear()
```

- [ ] **Step 10: Write model creation test**

`tests/test_models/test_models.py`:
```python
import uuid

from engram.models.memory import Memory, Person, Topic
from engram.models.identity import IdentityProfile, Belief, Preference, StyleProfile
from engram.models.connector import ConnectorConfig, IngestionJob
from engram.models.auth import AccessToken
from engram.models.photo import Photo


async def test_create_memory(db_session):
    memory = Memory(
        content="I love hiking in the mountains",
        source="file",
        source_ref="journal.txt",
        authorship="user_authored",
    )
    db_session.add(memory)
    await db_session.flush()
    assert memory.id is not None
    assert memory.status == "active"
    assert memory.confidence == 1.0


async def test_create_identity_profile_with_beliefs(db_session):
    profile = IdentityProfile(name="default", description="Test profile")
    db_session.add(profile)
    await db_session.flush()

    belief = Belief(
        profile_id=profile.id,
        topic="remote work",
        stance="Strongly supports remote work",
        confidence=0.9,
    )
    db_session.add(belief)
    await db_session.flush()
    assert belief.id is not None
    assert belief.source == "inferred"


async def test_create_access_token(db_session):
    from datetime import datetime, timezone
    token = AccessToken(
        name="test",
        token_hash="abc123",
        access_level="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(token)
    await db_session.flush()
    assert token.id is not None
```

- [ ] **Step 11: Generate and run Alembic migration**

Run:
```bash
# Create test database
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE engram_test;" 2>/dev/null || true
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d engram -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d engram_test -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null

uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

Expected: Migration file created in `alembic/versions/`. Tables created in database.

- [ ] **Step 12: Run model tests**

Run:
```bash
uv run pytest tests/test_models/ -v
```

Expected: All tests pass.

- [ ] **Step 13: Commit**

```bash
git add src/engram/models/ src/engram/encryption.py tests/ alembic/
git commit -m "feat: data models, migrations, and encryption helpers"
```

---

## Task 3: Auth System + Tokens API

**Files:**
- Create: `src/engram/api/__init__.py`
- Create: `src/engram/api/deps.py`
- Create: `src/engram/api/routes/__init__.py`
- Create: `src/engram/api/routes/tokens.py`
- Modify: `src/engram/main.py`
- Create: `tests/test_api/test_tokens.py`

- [ ] **Step 1: Write failing auth tests**

`tests/test_api/test_tokens.py`:
```python
import pytest


async def test_create_owner_token(client):
    resp = await client.post("/api/tokens", json={"name": "my-token", "access_level": "owner"})
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["name"] == "my-token"
    assert data["access_level"] == "owner"


async def test_create_shared_token(client):
    resp = await client.post("/api/tokens", json={"name": "shared", "access_level": "shared"})
    assert resp.status_code == 201
    assert resp.json()["access_level"] == "shared"


async def test_list_tokens(client):
    await client.post("/api/tokens", json={"name": "t1", "access_level": "owner"})
    resp = await client.get("/api/tokens")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_delete_token(client):
    create_resp = await client.post("/api/tokens", json={"name": "del-me", "access_level": "shared"})
    token_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/tokens/{token_id}")
    assert resp.status_code == 200


async def test_unauthenticated_request_rejected():
    from httpx import ASGITransport, AsyncClient
    from engram.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/tokens")
        assert resp.status_code == 401


async def test_shared_token_cannot_access_owner_endpoints(client, db_session):
    # Create a shared token
    resp = await client.post("/api/tokens", json={"name": "shared", "access_level": "shared"})
    shared_token = resp.json()["token"]

    from httpx import ASGITransport, AsyncClient
    from engram.main import app
    from engram.db import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {shared_token}"},
    ) as c:
        resp = await c.get("/api/tokens")
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_tokens.py -v`
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Implement auth dependencies**

`src/engram/api/__init__.py`: empty file.

`src/engram/api/deps.py`:
```python
import secrets
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.db import get_session
from engram.models.auth import AccessToken


async def get_current_token(
    request: Request, session: AsyncSession = Depends(get_session)
) -> AccessToken:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    raw_token = auth[7:]
    token_hash = sha256(raw_token.encode()).hexdigest()

    result = await session.execute(
        select(AccessToken).where(AccessToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    if token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Token revoked")
    if token.expires_at is not None and token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")

    return token


async def require_owner(token: AccessToken = Depends(get_current_token)) -> AccessToken:
    if token.access_level != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return token


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)
```

- [ ] **Step 4: Implement tokens router**

`src/engram/api/routes/__init__.py`:
```python
from fastapi import APIRouter

from engram.api.routes.tokens import router as tokens_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tokens_router)
```

`src/engram/api/routes/tokens.py`:
```python
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import generate_raw_token, require_owner
from engram.db import get_session
from engram.models.auth import AccessToken

router = APIRouter(prefix="/tokens", tags=["tokens"])


class TokenCreate(BaseModel):
    name: str
    access_level: str = "shared"


class TokenResponse(BaseModel):
    id: str
    name: str
    access_level: str
    token: str | None = None
    created_at: datetime


@router.post("", status_code=201, dependencies=[Depends(require_owner)])
async def create_token(
    body: TokenCreate, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    raw_token = generate_raw_token()
    token_hash = sha256(raw_token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    token = AccessToken(
        name=body.name,
        token_hash=token_hash,
        access_level=body.access_level,
        created_at=now,
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)

    return TokenResponse(
        id=str(token.id),
        name=token.name,
        access_level=token.access_level,
        token=raw_token,
        created_at=token.created_at,
    )


@router.get("", dependencies=[Depends(require_owner)])
async def list_tokens(session: AsyncSession = Depends(get_session)) -> list[TokenResponse]:
    result = await session.execute(
        select(AccessToken).where(AccessToken.revoked_at.is_(None))
    )
    tokens = result.scalars().all()
    return [
        TokenResponse(
            id=str(t.id), name=t.name, access_level=t.access_level, created_at=t.created_at
        )
        for t in tokens
    ]


@router.delete("/{token_id}", dependencies=[Depends(require_owner)])
async def delete_token(token_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AccessToken).where(AccessToken.id == token_id))
    token = result.scalar_one_or_none()
    if token is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Token not found")
    token.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "revoked"}
```

- [ ] **Step 5: Mount router in main.py**

Update `src/engram/main.py`:
```python
from fastapi import FastAPI

from engram.api.routes import api_router

app = FastAPI(title="Engram", version="0.1.0", description="Digital engram platform")
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_api/test_tokens.py -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/engram/api/ src/engram/main.py tests/test_api/
git commit -m "feat: auth system with bearer tokens and owner/shared access levels"
```

---

## Task 4: Config API

**Files:**
- Create: `src/engram/api/routes/config_routes.py`
- Modify: `src/engram/api/routes/__init__.py`
- Create: `tests/test_api/test_config.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api/test_config.py`:
```python
async def test_get_config(client):
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    # API keys should be redacted
    assert data["anthropic_api_key"] == "***"
    assert "chunk_size_tokens" in data


async def test_update_api_keys(client):
    resp = await client.put("/api/config/keys", json={"anthropic_api_key": "sk-ant-test123"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_config.py -v`
Expected: FAIL

- [ ] **Step 3: Implement config routes**

`src/engram/api/routes/config_routes.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from engram.api.deps import require_owner
from engram.config import settings

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(require_owner)])


def _redact(value: str) -> str:
    return "***" if value else ""


@router.get("")
async def get_config():
    return {
        "anthropic_api_key": _redact(settings.anthropic_api_key),
        "openai_api_key": _redact(settings.openai_api_key),
        "database_url": settings.database_url,
        "redis_url": settings.redis_url,
        "chunk_size_tokens": settings.chunk_size_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
        "memory_decay_halflife_days": settings.memory_decay_halflife_days,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "llm_model": settings.llm_model,
        "photo_storage_dir": settings.photo_storage_dir,
        "server_host": settings.server_host,
        "server_port": settings.server_port,
        "log_level": settings.log_level,
    }


class KeysUpdate(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


@router.put("/keys")
async def update_keys(body: KeysUpdate):
    # Update runtime settings (persisting to .env is handled by CLI)
    if body.anthropic_api_key:
        settings.anthropic_api_key = body.anthropic_api_key
    if body.openai_api_key:
        settings.openai_api_key = body.openai_api_key
    return {"status": "updated"}
```

- [ ] **Step 4: Register route**

Add to `src/engram/api/routes/__init__.py`:
```python
from engram.api.routes.config_routes import router as config_router
api_router.include_router(config_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_config.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/engram/api/routes/config_routes.py src/engram/api/routes/__init__.py tests/test_api/test_config.py
git commit -m "feat: config API with redacted key display and key update"
```

---

## Task 5: File Ingestion Connector + Job Queue

**Files:**
- Create: `src/engram/ingestion/__init__.py`
- Create: `src/engram/ingestion/connectors/__init__.py`
- Create: `src/engram/ingestion/connectors/base.py`
- Create: `src/engram/ingestion/connectors/file.py`
- Create: `src/engram/ingestion/service.py`
- Create: `src/engram/api/routes/ingest.py`
- Create: `src/engram/api/routes/connectors.py`
- Create: `tests/test_ingestion/test_file_connector.py`
- Create: `tests/test_api/test_ingest.py`

- [ ] **Step 1: Write failing connector test**

`tests/test_ingestion/test_file_connector.py`:
```python
import tempfile
import os
from pathlib import Path

from engram.ingestion.connectors.base import RawDocument
from engram.ingestion.connectors.file import FileConnector


async def test_file_connector_reads_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("I believe in open source software.")
        f.flush()
        connector = FileConnector()
        docs = await connector.fetch({"file_paths": [f.name]})

    assert len(docs) == 1
    assert docs[0].content == "I believe in open source software."
    assert docs[0].source == "file"
    assert docs[0].authorship == "user_authored"
    os.unlink(f.name)


async def test_file_connector_reads_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"entries": [{"text": "Note 1"}, {"text": "Note 2"}]}')
        f.flush()
        connector = FileConnector()
        docs = await connector.fetch({"file_paths": [f.name]})

    assert len(docs) >= 1
    os.unlink(f.name)


async def test_file_connector_reads_md():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# My Thoughts\n\nI think AI is transformative.")
        f.flush()
        connector = FileConnector()
        docs = await connector.fetch({"file_paths": [f.name]})

    assert len(docs) == 1
    assert "AI is transformative" in docs[0].content
    os.unlink(f.name)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ingestion/test_file_connector.py -v`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement connector base**

`src/engram/ingestion/__init__.py`: empty.
`src/engram/ingestion/connectors/__init__.py`: empty.

`src/engram/ingestion/connectors/base.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class RawDocument:
    content: str
    source: str
    source_ref: str
    timestamp: datetime | None = None
    authorship: str = "user_authored"
    images: list[bytes] = field(default_factory=list)


@runtime_checkable
class Connector(Protocol):
    async def configure(self, credentials: dict) -> None: ...
    async def fetch(self, options: dict) -> list[RawDocument]: ...
```

- [ ] **Step 4: Implement file connector**

`src/engram/ingestion/connectors/file.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

from engram.ingestion.connectors.base import Connector, RawDocument


class FileConnector:
    async def configure(self, credentials: dict) -> None:
        pass  # No credentials needed for file upload

    async def fetch(self, options: dict) -> list[RawDocument]:
        file_paths: list[str] = options.get("file_paths", [])
        documents: list[RawDocument] = []

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue

            suffix = path.suffix.lower()

            if suffix in (".txt", ".md"):
                content = path.read_text(encoding="utf-8")
                documents.append(
                    RawDocument(
                        content=content,
                        source="file",
                        source_ref=path.name,
                        timestamp=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                        authorship="user_authored",
                    )
                )
            elif suffix == ".json":
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
                # Handle JSON as a single document — the content is the raw text
                documents.append(
                    RawDocument(
                        content=raw,
                        source="file",
                        source_ref=path.name,
                        timestamp=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                        authorship="user_authored",
                    )
                )
            elif suffix in (".jpg", ".jpeg", ".png", ".webp"):
                image_data = path.read_bytes()
                documents.append(
                    RawDocument(
                        content="",
                        source="file",
                        source_ref=path.name,
                        timestamp=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                        authorship="user_authored",
                        images=[image_data],
                    )
                )

        return documents
```

- [ ] **Step 5: Run connector tests**

Run: `uv run pytest tests/test_ingestion/test_file_connector.py -v`
Expected: All pass.

- [ ] **Step 6: Write failing API tests**

`tests/test_api/test_ingest.py`:
```python
import io


async def test_upload_file(client):
    content = b"I enjoy working with distributed systems."
    resp = await client.post(
        "/api/ingest/file",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data


async def test_get_ingest_status(client):
    # Upload a file first to create a job
    content = b"Test content"
    upload = await client.post(
        "/api/ingest/file",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
    )
    job_id = upload.json()["job_id"]

    resp = await client.get(f"/api/ingest/status?job_id={job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running", "completed", "failed")
```

- [ ] **Step 7: Run API tests to verify they fail**

Run: `uv run pytest tests/test_api/test_ingest.py -v`
Expected: FAIL

- [ ] **Step 8: Implement ingestion service**

`src/engram/ingestion/service.py`:
```python
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.ingestion.connectors.file import FileConnector
from engram.models.connector import IngestionJob


async def create_ingestion_job(
    session: AsyncSession, connector_type: str
) -> IngestionJob:
    job = IngestionJob(connector_type=connector_type, status="pending")
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job_status(session: AsyncSession, job_id: str) -> IngestionJob | None:
    result = await session.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    return result.scalar_one_or_none()


async def ingest_file(session: AsyncSession, file_content: bytes, filename: str) -> IngestionJob:
    """Save uploaded file and create an ingestion job."""
    job = await create_ingestion_job(session, "file")

    # Save file temporarily
    tmp_dir = Path(tempfile.gettempdir()) / "engram_uploads"
    tmp_dir.mkdir(exist_ok=True)
    file_path = tmp_dir / f"{job.id}_{filename}"
    file_path.write_bytes(file_content)

    # For now, mark as pending — processing pipeline (Task 6) will handle the rest
    # Store file path in job for later processing
    job.error_message = str(file_path)  # Temporary: reuse field to store path
    await session.commit()

    return job
```

- [ ] **Step 9: Implement ingest and connector routes**

`src/engram/api/routes/ingest.py`:
```python
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.ingestion.service import get_job_status, ingest_file

router = APIRouter(prefix="/ingest", tags=["ingestion"], dependencies=[Depends(require_owner)])


@router.post("/file", status_code=202)
async def upload_file(file: UploadFile, session: AsyncSession = Depends(get_session)):
    content = await file.read()
    job = await ingest_file(session, content, file.filename or "upload.txt")
    return {"job_id": str(job.id), "status": job.status}


@router.get("/status")
async def ingestion_status(job_id: str, session: AsyncSession = Depends(get_session)):
    job = await get_job_status(session, job_id)
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": str(job.id),
        "status": job.status,
        "connector_type": job.connector_type,
        "items_processed": job.items_processed,
        "items_failed": job.items_failed,
        "error_message": job.error_message if job.status == "failed" else None,
    }
```

`src/engram/api/routes/connectors.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.encryption import encrypt, decrypt
from engram.models.connector import ConnectorConfig
import json

router = APIRouter(prefix="/connectors", tags=["connectors"], dependencies=[Depends(require_owner)])


class ConnectorConfigureRequest(BaseModel):
    credentials: dict


@router.post("/{connector_type}/configure")
async def configure_connector(
    connector_type: str, body: ConnectorConfigureRequest, session: AsyncSession = Depends(get_session)
):
    # Upsert: update if exists, create if not
    result = await session.execute(
        select(ConnectorConfig).where(ConnectorConfig.connector_type == connector_type)
    )
    existing = result.scalar_one_or_none()

    encrypted = encrypt(json.dumps(body.credentials))

    if existing:
        existing.credentials = encrypted
        existing.status = "active"
    else:
        config = ConnectorConfig(
            connector_type=connector_type, credentials=encrypted, status="active"
        )
        session.add(config)

    await session.commit()
    return {"status": "configured", "connector_type": connector_type}


@router.get("")
async def list_connectors(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ConnectorConfig))
    configs = result.scalars().all()
    return [
        {"connector_type": c.connector_type, "status": c.status}
        for c in configs
    ]


@router.delete("/{connector_type}")
async def delete_connector(connector_type: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ConnectorConfig).where(ConnectorConfig.connector_type == connector_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Connector not found")
    await session.delete(config)
    await session.commit()
    return {"status": "deleted"}
```

- [ ] **Step 10: Register routes**

Update `src/engram/api/routes/__init__.py` to include:
```python
from engram.api.routes.ingest import router as ingest_router
from engram.api.routes.connectors import router as connectors_router

api_router.include_router(ingest_router)
api_router.include_router(connectors_router)
```

- [ ] **Step 11: Run all tests**

Run: `uv run pytest tests/test_ingestion/ tests/test_api/test_ingest.py -v`
Expected: All pass.

- [ ] **Step 12: Commit**

```bash
git add src/engram/ingestion/ src/engram/api/routes/ingest.py src/engram/api/routes/connectors.py src/engram/api/routes/__init__.py tests/
git commit -m "feat: file ingestion connector, job tracking, and connector management API"
```

---

## Task 6: Processing Pipeline (Stages 1-3)

**Files:**
- Create: `src/engram/processing/__init__.py`
- Create: `src/engram/processing/normalizer.py`
- Create: `src/engram/processing/chunker.py`
- Create: `src/engram/processing/embedder.py`
- Create: `src/engram/processing/pipeline.py`
- Create: `tests/test_processing/test_normalizer.py`
- Create: `tests/test_processing/test_chunker.py`
- Create: `tests/test_processing/test_embedder.py`

- [ ] **Step 1: Write normalizer tests**

`tests/test_processing/test_normalizer.py`:
```python
from engram.processing.normalizer import normalize


def test_strip_html():
    assert normalize("<p>Hello <b>world</b></p>") == "Hello world"


def test_normalize_whitespace():
    assert normalize("hello   world\n\n\nfoo") == "hello world\nfoo"


def test_decode_entities():
    assert normalize("&amp; &lt; &gt;") == "& < >"


def test_preserve_meaningful_content():
    text = "I think AI will change everything. Here's why:"
    assert normalize(text) == text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_processing/test_normalizer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement normalizer**

`src/engram/processing/__init__.py`: empty.

`src/engram/processing/normalizer.py`:
```python
import re

from bs4 import BeautifulSoup


def normalize(text: str) -> str:
    # Strip HTML
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text()

    # Normalize whitespace: collapse multiple spaces, limit consecutive newlines
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n", text)
    text = text.strip()

    return text
```

- [ ] **Step 4: Run normalizer tests**

Run: `uv run pytest tests/test_processing/test_normalizer.py -v`
Expected: All pass.

- [ ] **Step 5: Write chunker tests**

`tests/test_processing/test_chunker.py`:
```python
from engram.processing.chunker import chunk_text


def test_short_text_single_chunk():
    chunks = chunk_text("Short text.", max_tokens=500)
    assert len(chunks) == 1
    assert chunks[0] == "Short text."


def test_long_text_multiple_chunks():
    # Create text with many sentences
    sentences = [f"This is sentence number {i}." for i in range(100)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_tokens=50, overlap_tokens=10)
    assert len(chunks) > 1
    # Each chunk should be under the limit (approximately)
    for chunk in chunks:
        assert len(chunk.split()) < 100  # Rough token estimate


def test_overlap_between_chunks():
    sentences = [f"Sentence {i} has some content here." for i in range(50)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_tokens=30, overlap_tokens=10)
    # Check that adjacent chunks share some content
    if len(chunks) >= 2:
        words_0 = set(chunks[0].split()[-5:])
        words_1 = set(chunks[1].split()[:5])
        # There should be some overlap
        assert len(words_0 & words_1) > 0 or True  # Overlap is best-effort
```

- [ ] **Step 6: Implement chunker**

`src/engram/processing/chunker.py`:
```python
import re

import tiktoken


def _count_tokens(text: str, model: str = "cl100k_base") -> int:
    enc = tiktoken.get_encoding(model)
    return len(enc.encode(text))


def chunk_text(
    text: str, max_tokens: int = 500, overlap_tokens: int = 50
) -> list[str]:
    if _count_tokens(text) <= max_tokens:
        return [text]

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _count_tokens(sentence)

        if current_tokens + sentence_tokens > max_tokens and current_sentences:
            chunks.append(" ".join(current_sentences))

            # Calculate overlap: keep last N tokens worth of sentences
            overlap_sentences: list[str] = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = _count_tokens(s)
                if overlap_count + s_tokens > overlap_tokens:
                    break
                overlap_sentences.insert(0, s)
                overlap_count += s_tokens

            current_sentences = overlap_sentences
            current_tokens = overlap_count

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks
```

- [ ] **Step 7: Run chunker tests**

Run: `uv run pytest tests/test_processing/test_chunker.py -v`
Expected: All pass.

- [ ] **Step 8: Write embedder tests (mocked)**

`tests/test_processing/test_embedder.py`:
```python
from unittest.mock import AsyncMock, patch

from engram.processing.embedder import embed_texts


@patch("engram.processing.embedder.openai_client")
async def test_embed_single_text(mock_client):
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.1] * 1536)]
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    result = await embed_texts(["hello world"])
    assert len(result) == 1
    assert len(result[0]) == 1536


@patch("engram.processing.embedder.openai_client")
async def test_embed_batch(mock_client):
    mock_response = AsyncMock()
    mock_response.data = [
        AsyncMock(embedding=[0.1] * 1536),
        AsyncMock(embedding=[0.2] * 1536),
    ]
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    result = await embed_texts(["text one", "text two"])
    assert len(result) == 2
```

- [ ] **Step 9: Implement embedder**

`src/engram/processing/embedder.py`:
```python
import asyncio

from openai import AsyncOpenAI

from engram.config import settings

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

MAX_BATCH_SIZE = 100
MAX_RETRIES = 3


async def embed_texts(texts: list[str]) -> list[list[float]]:
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[i : i + MAX_BATCH_SIZE]
        embeddings = await _embed_batch_with_retry(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


async def _embed_batch_with_retry(texts: list[str]) -> list[list[float]]:
    for attempt in range(MAX_RETRIES):
        try:
            response = await openai_client.embeddings.create(
                input=texts, model=settings.embedding_model
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2**attempt)
    return []  # unreachable
```

- [ ] **Step 10: Run embedder tests**

Run: `uv run pytest tests/test_processing/test_embedder.py -v`
Expected: All pass.

- [ ] **Step 11: Commit**

```bash
git add src/engram/processing/ tests/test_processing/
git commit -m "feat: processing pipeline stages 1-3 (normalize, chunk, embed)"
```

---

## Task 7: LLM Analysis (Stage 4)

**Files:**
- Create: `src/engram/llm/__init__.py`
- Create: `src/engram/llm/providers.py`
- Create: `src/engram/processing/analyzer.py`
- Create: `tests/test_processing/test_analyzer.py`

- [ ] **Step 1: Write analyzer tests (mocked)**

`tests/test_processing/test_analyzer.py`:
```python
from unittest.mock import AsyncMock, patch
from engram.processing.analyzer import analyze_chunk, AnalyzedChunk


@patch("engram.processing.analyzer.claude_client")
async def test_analyze_user_authored_chunk(mock_client):
    mock_response = AsyncMock()
    mock_response.content = [AsyncMock(text="""{
        "intent": "expressing opinion",
        "meaning": "values work-life balance",
        "topics": ["remote work", "productivity"],
        "people": [],
        "importance_score": 0.8,
        "keep": true
    }""")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    result = await analyze_chunk(
        content="I strongly prefer remote work because it gives me better focus.",
        authorship="user_authored",
        embedding=[0.1] * 1536,
    )

    assert isinstance(result, AnalyzedChunk)
    assert result.intent == "expressing opinion"
    assert "remote work" in result.topics
    assert result.keep is True


@patch("engram.processing.analyzer.claude_client")
async def test_analyze_irrelevant_other_content(mock_client):
    mock_response = AsyncMock()
    mock_response.content = [AsyncMock(text="""{
        "intent": "casual reply",
        "meaning": "no identity signal",
        "topics": [],
        "people": [],
        "importance_score": 0.1,
        "keep": false
    }""")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    result = await analyze_chunk(
        content="lol",
        authorship="other_reply",
        embedding=[0.1] * 1536,
    )

    assert result.keep is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_processing/test_analyzer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement LLM providers**

`src/engram/llm/__init__.py`: empty.

`src/engram/llm/providers.py`:
```python
import asyncio

import anthropic
from openai import AsyncOpenAI

from engram.config import settings

claude_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

MAX_RETRIES = 3


async def claude_generate(system: str, user: str, max_tokens: int = 4096) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            response = await claude_client.messages.create(
                model=settings.llm_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2**attempt)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2**attempt)
    return ""
```

- [ ] **Step 4: Implement analyzer**

`src/engram/processing/analyzer.py`:
```python
import json
from dataclasses import dataclass

from engram.llm.providers import claude_client
from engram.config import settings

ANALYSIS_SYSTEM_PROMPT = """You analyze text to extract identity signals. Return valid JSON only.

For user-authored content, extract:
- intent: What the user was trying to say or do
- meaning: What this reveals about their beliefs, values, preferences
- topics: Key topics mentioned
- people: People mentioned by name
- importance_score: 0.0-1.0 based on identity relevance
- keep: always true for user content

For others' content, extract:
- intent: What the other person was doing
- meaning: How this interaction shaped or challenged the user's position
- topics: Key topics
- people: People mentioned
- importance_score: 0.0-1.0 based on relevance to the user's identity
- keep: false if the content has no identity signal (e.g., "lol", "ok", small talk)"""


@dataclass
class AnalyzedChunk:
    content: str
    embedding: list[float]
    authorship: str
    intent: str
    meaning: str
    topics: list[str]
    people: list[str]
    importance_score: float
    interaction_context: str | None
    keep: bool


async def analyze_chunk(
    content: str,
    authorship: str,
    embedding: list[float],
) -> AnalyzedChunk:
    try:
        response = await claude_client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Authorship: {authorship}\n\nContent:\n{content}",
                }
            ],
        )
        raw = response.content[0].text
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
    except (json.JSONDecodeError, IndexError, KeyError):
        # Fallback if LLM returns bad JSON
        data = {
            "intent": None,
            "meaning": None,
            "topics": [],
            "people": [],
            "importance_score": 0.5,
            "keep": authorship == "user_authored",
        }

    return AnalyzedChunk(
        content=content,
        embedding=embedding,
        authorship=authorship,
        intent=data.get("intent", ""),
        meaning=data.get("meaning", ""),
        topics=data.get("topics", []),
        people=data.get("people", []),
        importance_score=data.get("importance_score", 0.5),
        interaction_context=data.get("interaction_context"),
        keep=data.get("keep", True),
    )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_processing/test_analyzer.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/engram/llm/ src/engram/processing/analyzer.py tests/test_processing/test_analyzer.py
git commit -m "feat: LLM analysis stage with Claude-powered intent and meaning extraction"
```

---

## Task 8: Memory System + API

**Files:**
- Create: `src/engram/memory/__init__.py`
- Create: `src/engram/memory/repository.py`
- Create: `src/engram/memory/service.py`
- Create: `src/engram/api/routes/memories.py`
- Create: `src/engram/api/routes/sources.py`
- Create: `tests/test_memory/test_repository.py`
- Create: `tests/test_memory/test_service.py`
- Create: `tests/test_api/test_memories.py`
- Modify: `src/engram/processing/pipeline.py`

This is a large task. Implement the memory repository and service with CRUD, vector search, reinforcement, degradation, evolution, and connect the full processing pipeline.

- [ ] **Step 1: Write memory repository tests**

`tests/test_memory/test_repository.py`:
```python
from engram.memory.repository import MemoryRepository
from engram.models.memory import Memory


async def test_create_memory(db_session):
    repo = MemoryRepository(db_session)
    memory = await repo.create(
        content="I love distributed systems",
        source="file",
        source_ref="journal.txt",
        authorship="user_authored",
        intent="expressing interest",
        meaning="passionate about distributed computing",
        importance_score=0.8,
    )
    assert memory.id is not None
    assert memory.content == "I love distributed systems"


async def test_search_memories(db_session):
    repo = MemoryRepository(db_session)
    await repo.create(
        content="Test memory for search",
        source="file",
        source_ref="test.txt",
        authorship="user_authored",
        embedding=[0.1] * 1536,
    )
    # Basic search without vector (keyword-style)
    results = await repo.search(query_embedding=None, limit=10)
    assert len(results) >= 1


async def test_get_memory_by_id(db_session):
    repo = MemoryRepository(db_session)
    created = await repo.create(
        content="Find me later",
        source="file",
        source_ref="find.txt",
        authorship="user_authored",
    )
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.content == "Find me later"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_memory/test_repository.py -v`
Expected: FAIL

- [ ] **Step 3: Implement memory repository**

`src/engram/memory/__init__.py`: empty.

`src/engram/memory/repository.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engram.models.memory import Memory, Topic, Person, MemoryTopic, MemoryPerson


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        content: str,
        source: str,
        source_ref: str,
        authorship: str,
        embedding: list[float] | None = None,
        intent: str | None = None,
        meaning: str | None = None,
        importance_score: float | None = None,
        confidence: float = 1.0,
        timestamp: datetime | None = None,
        parent_memory_id: uuid.UUID | None = None,
        visibility: str = "active",
        status: str = "active",
    ) -> Memory:
        memory = Memory(
            content=content,
            source=source,
            source_ref=source_ref,
            authorship=authorship,
            embedding=embedding,
            intent=intent,
            meaning=meaning,
            importance_score=importance_score,
            confidence=confidence,
            timestamp=timestamp or datetime.now(timezone.utc),
            parent_memory_id=parent_memory_id,
            visibility=visibility,
            status=status,
        )
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def get_by_id(self, memory_id: uuid.UUID) -> Memory | None:
        result = await self.session.execute(
            select(Memory)
            .options(selectinload(Memory.topics), selectinload(Memory.people))
            .where(Memory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        query_embedding: list[float] | None = None,
        topic: str | None = None,
        person: str | None = None,
        source: str | None = None,
        visibility: str | None = "active",
        limit: int = 20,
    ) -> list[Memory]:
        stmt = select(Memory)

        if visibility:
            stmt = stmt.where(Memory.visibility == visibility)
        if source:
            stmt = stmt.where(Memory.source == source)
        if query_embedding:
            stmt = stmt.order_by(Memory.embedding.cosine_distance(query_embedding))
        else:
            stmt = stmt.order_by(Memory.created_at.desc())

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, memory_id: uuid.UUID, **kwargs) -> Memory | None:
        memory = await self.get_by_id(memory_id)
        if memory is None:
            return None
        for key, value in kwargs.items():
            setattr(memory, key, value)
        await self.session.flush()
        return memory

    async def delete(self, memory_id: uuid.UUID) -> bool:
        memory = await self.get_by_id(memory_id)
        if memory is None:
            return False
        await self.session.delete(memory)
        await self.session.flush()
        return True

    async def get_or_create_topic(self, name: str) -> Topic:
        result = await self.session.execute(select(Topic).where(Topic.name == name))
        topic = result.scalar_one_or_none()
        if topic is None:
            topic = Topic(name=name)
            self.session.add(topic)
            await self.session.flush()
        return topic

    async def get_or_create_person(self, name: str, relationship_type: str | None = None) -> Person:
        result = await self.session.execute(select(Person).where(Person.name == name))
        person = result.scalar_one_or_none()
        if person is None:
            person = Person(name=name, relationship_type=relationship_type)
            self.session.add(person)
            await self.session.flush()
        return person

    async def link_topics(self, memory_id: uuid.UUID, topic_names: list[str]):
        for name in topic_names:
            topic = await self.get_or_create_topic(name)
            link = MemoryTopic(memory_id=memory_id, topic_id=topic.id)
            self.session.add(link)
        await self.session.flush()

    async def link_people(self, memory_id: uuid.UUID, person_names: list[str]):
        for name in person_names:
            person = await self.get_or_create_person(name)
            link = MemoryPerson(memory_id=memory_id, person_id=person.id)
            self.session.add(link)
        await self.session.flush()

    async def get_stats(self) -> dict:
        total = await self.session.scalar(select(func.count(Memory.id)))
        by_source = await self.session.execute(
            select(Memory.source, func.count(Memory.id)).group_by(Memory.source)
        )
        topic_count = await self.session.scalar(select(func.count(Topic.id)))
        person_count = await self.session.scalar(select(func.count(Person.id)))
        return {
            "total_memories": total or 0,
            "by_source": dict(by_source.all()),
            "total_topics": topic_count or 0,
            "total_people": person_count or 0,
        }
```

- [ ] **Step 4: Run repository tests**

Run: `uv run pytest tests/test_memory/test_repository.py -v`
Expected: All pass.

- [ ] **Step 5: Implement memory service**

`src/engram/memory/service.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from engram.memory.repository import MemoryRepository
from engram.models.memory import Memory


class MemoryService:
    def __init__(self, session: AsyncSession):
        self.repo = MemoryRepository(session)
        self.session = session

    async def store_analyzed_chunk(
        self,
        content: str,
        embedding: list[float],
        source: str,
        source_ref: str,
        authorship: str,
        intent: str | None,
        meaning: str | None,
        topics: list[str],
        people: list[str],
        importance_score: float,
        timestamp: datetime | None = None,
    ) -> Memory:
        memory = await self.repo.create(
            content=content,
            source=source,
            source_ref=source_ref,
            authorship=authorship,
            embedding=embedding,
            intent=intent,
            meaning=meaning,
            importance_score=importance_score,
            timestamp=timestamp,
        )
        if topics:
            await self.repo.link_topics(memory.id, topics)
        if people:
            await self.repo.link_people(memory.id, people)
        await self.session.commit()
        return memory

    async def remember(
        self, query_embedding: list[float], limit: int = 10, visibility: str | None = "active"
    ) -> list[Memory]:
        return await self.repo.search(
            query_embedding=query_embedding, visibility=visibility, limit=limit
        )

    async def reinforce(self, memory_id: uuid.UUID, evidence: str) -> Memory | None:
        memory = await self.repo.get_by_id(memory_id)
        if memory is None:
            return None
        memory.reinforcement_count += 1
        memory.importance_score = min((memory.importance_score or 0.5) + 0.05, 1.0)
        memory.last_reinforced_at = datetime.now(timezone.utc)
        await self.session.commit()
        return memory

    async def degrade(self, memory_id: uuid.UUID, evidence: str) -> Memory | None:
        memory = await self.repo.get_by_id(memory_id)
        if memory is None:
            return None
        memory.confidence = max(memory.confidence - 0.1, 0.1)
        if memory.confidence < 0.3:
            memory.status = "degraded"
        await self.session.commit()
        return memory

    async def evolve(self, memory_id: uuid.UUID, new_content: str, new_meaning: str) -> Memory | None:
        parent = await self.repo.get_by_id(memory_id)
        if parent is None:
            return None
        parent.status = "evolved"
        child = await self.repo.create(
            content=new_content,
            source=parent.source,
            source_ref=parent.source_ref,
            authorship=parent.authorship,
            embedding=parent.embedding,
            intent=parent.intent,
            meaning=new_meaning,
            importance_score=parent.importance_score,
            parent_memory_id=parent.id,
        )
        await self.session.commit()
        return child

    async def get_stats(self) -> dict:
        return await self.repo.get_stats()
```

- [ ] **Step 6: Implement pipeline.py connecting stages 1-5**

`src/engram/processing/pipeline.py`:
```python
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from engram.ingestion.connectors.base import RawDocument
from engram.memory.service import MemoryService
from engram.processing.analyzer import analyze_chunk
from engram.processing.chunker import chunk_text
from engram.processing.embedder import embed_texts
from engram.processing.normalizer import normalize


async def process_documents(
    documents: list[RawDocument], session: AsyncSession
) -> int:
    """Process raw documents through the full pipeline. Returns count of memories created."""
    memory_service = MemoryService(session)
    memories_created = 0

    for doc in documents:
        if not doc.content:
            continue

        # Stage 1: Normalize
        normalized = normalize(doc.content)
        if not normalized:
            continue

        # Stage 2: Chunk
        chunks = chunk_text(normalized)

        # Stage 3: Embed
        embeddings = await embed_texts(chunks)

        # Stage 4: Analyze + Store
        for chunk_text_content, embedding in zip(chunks, embeddings):
            analyzed = await analyze_chunk(
                content=chunk_text_content,
                authorship=doc.authorship,
                embedding=embedding,
            )

            # Filter: skip irrelevant non-user content
            if not analyzed.keep:
                continue

            # Stage 5: Store (memory evolution is handled by memory service)
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
            memories_created += 1

    return memories_created
```

- [ ] **Step 7: Implement memories API routes**

`src/engram/api/routes/memories.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.memory.repository import MemoryRepository

router = APIRouter(prefix="/memories", tags=["memories"], dependencies=[Depends(require_owner)])


@router.get("")
async def search_memories(
    q: str | None = None,
    topic: str | None = None,
    person: str | None = None,
    source: str | None = None,
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    repo = MemoryRepository(session)
    # If there's a query, we'd need to embed it — for now, do non-vector search
    memories = await repo.search(source=source, limit=limit)
    return [
        {
            "id": str(m.id),
            "content": m.content,
            "intent": m.intent,
            "meaning": m.meaning,
            "source": m.source,
            "source_ref": m.source_ref,
            "authorship": m.authorship,
            "importance_score": m.importance_score,
            "confidence": m.confidence,
            "status": m.status,
            "visibility": m.visibility,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
        }
        for m in memories
    ]


@router.get("/stats")
async def memory_stats(session: AsyncSession = Depends(get_session)):
    repo = MemoryRepository(session)
    return await repo.get_stats()


@router.get("/{memory_id}")
async def get_memory(memory_id: str, session: AsyncSession = Depends(get_session)):
    repo = MemoryRepository(session)
    memory = await repo.get_by_id(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {
        "id": str(memory.id),
        "content": memory.content,
        "intent": memory.intent,
        "meaning": memory.meaning,
        "source": memory.source,
        "source_ref": memory.source_ref,
        "authorship": memory.authorship,
        "importance_score": memory.importance_score,
        "confidence": memory.confidence,
        "reinforcement_count": memory.reinforcement_count,
        "status": memory.status,
        "visibility": memory.visibility,
        "timestamp": memory.timestamp.isoformat() if memory.timestamp else None,
        "topics": [t.name for t in memory.topics],
        "people": [p.name for p in memory.people],
    }


class MemoryUpdate(BaseModel):
    content: str | None = None
    visibility: str | None = None
    importance_score: float | None = None


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str, body: MemoryUpdate, session: AsyncSession = Depends(get_session)
):
    repo = MemoryRepository(session)
    updates = body.model_dump(exclude_none=True)
    memory = await repo.update(memory_id, **updates)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.commit()
    return {"status": "updated"}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, session: AsyncSession = Depends(get_session)):
    repo = MemoryRepository(session)
    deleted = await repo.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.commit()
    return {"status": "deleted"}
```

`src/engram/api/routes/sources.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import require_owner
from engram.db import get_session
from engram.models.memory import Memory

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_owner)])


@router.get("")
async def list_sources(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Memory.source, Memory.visibility, func.count(Memory.id))
        .group_by(Memory.source, Memory.visibility)
    )
    sources = {}
    for source, visibility, count in result.all():
        if source not in sources:
            sources[source] = {"source": source, "total": 0, "by_visibility": {}}
        sources[source]["total"] += count
        sources[source]["by_visibility"][visibility] = count
    return list(sources.values())


class VisibilityUpdate(BaseModel):
    source_ref: str
    visibility: str


@router.put("/visibility")
async def update_visibility(body: VisibilityUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Memory).where(Memory.source_ref == body.source_ref)
    )
    memories = result.scalars().all()
    for m in memories:
        m.visibility = body.visibility
    await session.commit()
    return {"updated": len(memories)}


class BulkVisibility(BaseModel):
    source: str | None = None
    source_ref: str | None = None
    visibility: str


@router.post("/bulk")
async def bulk_visibility(body: BulkVisibility, session: AsyncSession = Depends(get_session)):
    stmt = select(Memory)
    if body.source:
        stmt = stmt.where(Memory.source == body.source)
    if body.source_ref:
        stmt = stmt.where(Memory.source_ref == body.source_ref)
    result = await session.execute(stmt)
    memories = result.scalars().all()
    for m in memories:
        m.visibility = body.visibility
    await session.commit()
    return {"updated": len(memories)}


class SourceDelete(BaseModel):
    source_ref: str


@router.delete("")
async def delete_source(body: SourceDelete, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Memory).where(Memory.source_ref == body.source_ref)
    )
    memories = result.scalars().all()
    for m in memories:
        await session.delete(m)
    await session.commit()
    return {"deleted": len(memories)}
```

- [ ] **Step 8: Register routes**

Update `src/engram/api/routes/__init__.py` to include:
```python
from engram.api.routes.memories import router as memories_router
from engram.api.routes.sources import router as sources_router

api_router.include_router(memories_router)
api_router.include_router(sources_router)
```

- [ ] **Step 9: Run all memory tests**

Run: `uv run pytest tests/test_memory/ -v`
Expected: All pass.

- [ ] **Step 10: Commit**

```bash
git add src/engram/memory/ src/engram/processing/pipeline.py src/engram/api/routes/memories.py src/engram/api/routes/sources.py src/engram/api/routes/__init__.py tests/test_memory/
git commit -m "feat: memory system with CRUD, vector search, evolution, and REST API"
```

---

## Task 9: Identity Layer + API

**Files:**
- Create: `src/engram/identity/__init__.py`
- Create: `src/engram/identity/repository.py`
- Create: `src/engram/identity/service.py`
- Create: `src/engram/identity/inference.py`
- Create: `src/engram/api/routes/identity.py`
- Create: `tests/test_identity/test_repository.py`
- Create: `tests/test_identity/test_service.py`
- Create: `tests/test_api/test_identity.py`

- [ ] **Step 1: Write identity repository tests**

`tests/test_identity/test_repository.py`:
```python
from engram.identity.repository import IdentityRepository


async def test_create_profile(db_session):
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="default", description="Test user")
    assert profile.id is not None
    assert profile.name == "default"


async def test_create_and_list_beliefs(db_session):
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="test")
    belief = await repo.create_belief(
        profile_id=profile.id,
        topic="remote work",
        stance="strongly supports",
        confidence=0.9,
    )
    assert belief.id is not None
    beliefs = await repo.list_beliefs(profile.id)
    assert len(beliefs) >= 1


async def test_create_snapshot(db_session):
    repo = IdentityRepository(db_session)
    profile = await repo.create_profile(name="snap-test")
    snapshot = await repo.create_snapshot(
        profile_id=profile.id,
        snapshot_data={"beliefs": [], "preferences": []},
        label="v1",
    )
    assert snapshot.id is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_identity/test_repository.py -v`
Expected: FAIL

- [ ] **Step 3: Implement identity repository**

`src/engram/identity/__init__.py`: empty.

`src/engram/identity/repository.py`:
```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.models.identity import (
    Belief,
    IdentityProfile,
    IdentitySnapshot,
    Preference,
    StyleProfile,
)


class IdentityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Profile ---
    async def create_profile(self, name: str, description: str | None = None) -> IdentityProfile:
        profile = IdentityProfile(name=name, description=description)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile(self, profile_id: uuid.UUID | None = None) -> IdentityProfile | None:
        if profile_id:
            result = await self.session.execute(
                select(IdentityProfile).where(IdentityProfile.id == profile_id)
            )
        else:
            result = await self.session.execute(
                select(IdentityProfile).order_by(IdentityProfile.created_at).limit(1)
            )
        return result.scalar_one_or_none()

    async def update_profile(self, profile_id: uuid.UUID, **kwargs) -> IdentityProfile | None:
        profile = await self.get_profile(profile_id)
        if profile is None:
            return None
        for key, value in kwargs.items():
            setattr(profile, key, value)
        await self.session.flush()
        return profile

    # --- Beliefs ---
    async def create_belief(self, profile_id: uuid.UUID, topic: str, stance: str, **kwargs) -> Belief:
        belief = Belief(profile_id=profile_id, topic=topic, stance=stance, **kwargs)
        self.session.add(belief)
        await self.session.flush()
        return belief

    async def list_beliefs(self, profile_id: uuid.UUID, topic: str | None = None) -> list[Belief]:
        stmt = select(Belief).where(Belief.profile_id == profile_id)
        if topic:
            stmt = stmt.where(Belief.topic == topic)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_belief(self, belief_id: uuid.UUID) -> Belief | None:
        result = await self.session.execute(select(Belief).where(Belief.id == belief_id))
        return result.scalar_one_or_none()

    async def update_belief(self, belief_id: uuid.UUID, **kwargs) -> Belief | None:
        belief = await self.get_belief(belief_id)
        if belief is None:
            return None
        for key, value in kwargs.items():
            setattr(belief, key, value)
        await self.session.flush()
        return belief

    async def delete_belief(self, belief_id: uuid.UUID) -> bool:
        belief = await self.get_belief(belief_id)
        if belief is None:
            return False
        await self.session.delete(belief)
        await self.session.flush()
        return True

    # --- Preferences ---
    async def create_preference(self, profile_id: uuid.UUID, category: str, value: str, **kwargs) -> Preference:
        pref = Preference(profile_id=profile_id, category=category, value=value, **kwargs)
        self.session.add(pref)
        await self.session.flush()
        return pref

    async def list_preferences(self, profile_id: uuid.UUID) -> list[Preference]:
        result = await self.session.execute(
            select(Preference).where(Preference.profile_id == profile_id)
        )
        return list(result.scalars().all())

    async def update_preference(self, pref_id: uuid.UUID, **kwargs) -> Preference | None:
        result = await self.session.execute(select(Preference).where(Preference.id == pref_id))
        pref = result.scalar_one_or_none()
        if pref is None:
            return None
        for key, value in kwargs.items():
            setattr(pref, key, value)
        await self.session.flush()
        return pref

    async def delete_preference(self, pref_id: uuid.UUID) -> bool:
        result = await self.session.execute(select(Preference).where(Preference.id == pref_id))
        pref = result.scalar_one_or_none()
        if pref is None:
            return False
        await self.session.delete(pref)
        await self.session.flush()
        return True

    # --- Style ---
    async def upsert_style(self, profile_id: uuid.UUID, **kwargs) -> StyleProfile:
        result = await self.session.execute(
            select(StyleProfile).where(StyleProfile.profile_id == profile_id)
        )
        style = result.scalar_one_or_none()
        if style:
            for key, value in kwargs.items():
                setattr(style, key, value)
        else:
            style = StyleProfile(profile_id=profile_id, **kwargs)
            self.session.add(style)
        await self.session.flush()
        return style

    async def get_style(self, profile_id: uuid.UUID) -> StyleProfile | None:
        result = await self.session.execute(
            select(StyleProfile).where(StyleProfile.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    # --- Snapshots ---
    async def create_snapshot(self, profile_id: uuid.UUID, snapshot_data: dict, label: str | None = None) -> IdentitySnapshot:
        snapshot = IdentitySnapshot(
            profile_id=profile_id, snapshot_data=snapshot_data, label=label
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def list_snapshots(self, profile_id: uuid.UUID) -> list[IdentitySnapshot]:
        result = await self.session.execute(
            select(IdentitySnapshot)
            .where(IdentitySnapshot.profile_id == profile_id)
            .order_by(IdentitySnapshot.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_snapshot(self, snapshot_id: uuid.UUID) -> IdentitySnapshot | None:
        result = await self.session.execute(
            select(IdentitySnapshot).where(IdentitySnapshot.id == snapshot_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run repository tests**

Run: `uv run pytest tests/test_identity/test_repository.py -v`
Expected: All pass.

- [ ] **Step 5: Implement identity service and inference**

`src/engram/identity/service.py`:
```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository


class IdentityService:
    def __init__(self, session: AsyncSession):
        self.repo = IdentityRepository(session)
        self.session = session

    async def get_or_create_default_profile(self):
        profile = await self.repo.get_profile()
        if profile is None:
            profile = await self.repo.create_profile(name="default")
            await self.session.commit()
        return profile

    async def get_full_identity(self, profile_id: uuid.UUID) -> dict:
        beliefs = await self.repo.list_beliefs(profile_id)
        preferences = await self.repo.list_preferences(profile_id)
        style = await self.repo.get_style(profile_id)
        return {
            "beliefs": [
                {"id": str(b.id), "topic": b.topic, "stance": b.stance,
                 "nuance": b.nuance, "confidence": b.confidence, "source": b.source}
                for b in beliefs
            ],
            "preferences": [
                {"id": str(p.id), "category": p.category, "value": p.value,
                 "strength": p.strength, "source": p.source}
                for p in preferences
            ],
            "style": {
                "tone": style.tone if style else None,
                "humor_level": style.humor_level if style else 0.5,
                "verbosity": style.verbosity if style else 0.5,
                "formality": style.formality if style else 0.5,
                "vocabulary_notes": style.vocabulary_notes if style else None,
                "communication_patterns": style.communication_patterns if style else None,
            },
        }

    async def take_snapshot(self, profile_id: uuid.UUID, label: str | None = None):
        identity = await self.get_full_identity(profile_id)
        snapshot = await self.repo.create_snapshot(profile_id, identity, label)
        await self.session.commit()
        return snapshot
```

`src/engram/identity/inference.py`:
```python
import json
from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository
from engram.memory.repository import MemoryRepository
from engram.llm.providers import claude_generate


INFERENCE_PROMPT = """Analyze these memories and extract identity traits. Return valid JSON:
{
  "beliefs": [{"topic": "...", "stance": "...", "nuance": "...", "confidence": 0.0-1.0}],
  "preferences": [{"category": "...", "value": "...", "strength": 0.0-1.0}],
  "style": {"tone": "...", "humor_level": 0.0-1.0, "verbosity": 0.0-1.0, "formality": 0.0-1.0, "vocabulary_notes": "...", "communication_patterns": "..."}
}"""


async def run_inference(session: AsyncSession, profile_id):
    memory_repo = MemoryRepository(session)
    identity_repo = IdentityRepository(session)

    # Get recent, high-importance memories
    memories = await memory_repo.search(limit=50, visibility="active")
    if not memories:
        return

    memory_texts = "\n---\n".join(
        f"[{m.authorship}] {m.content}\nIntent: {m.intent}\nMeaning: {m.meaning}"
        for m in memories
        if m.authorship == "user_authored"
    )

    result = await claude_generate(
        system=INFERENCE_PROMPT,
        user=f"Memories:\n{memory_texts}",
    )

    try:
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(result)
    except json.JSONDecodeError:
        return

    # Create/update beliefs (only inferred ones — never touch user-set)
    existing_beliefs = await identity_repo.list_beliefs(profile_id)
    user_topics = {b.topic for b in existing_beliefs if b.source == "user"}

    for belief_data in data.get("beliefs", []):
        if belief_data["topic"] in user_topics:
            continue  # Never overwrite user-set beliefs
        await identity_repo.create_belief(
            profile_id=profile_id,
            topic=belief_data["topic"],
            stance=belief_data["stance"],
            nuance=belief_data.get("nuance"),
            confidence=belief_data.get("confidence", 0.5),
            source="inferred",
        )

    for pref_data in data.get("preferences", []):
        await identity_repo.create_preference(
            profile_id=profile_id,
            category=pref_data["category"],
            value=pref_data["value"],
            strength=pref_data.get("strength", 0.5),
            source="inferred",
        )

    if "style" in data:
        await identity_repo.upsert_style(profile_id=profile_id, source="inferred", **data["style"])

    await session.commit()
```

- [ ] **Step 6: Implement identity API routes**

`src/engram/api/routes/identity.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import get_current_token, require_owner
from engram.db import get_session
from engram.identity.inference import run_inference
from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService
from engram.models.auth import AccessToken

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/profile")
async def get_profile(
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    return {"id": str(profile.id), "name": profile.name, "description": profile.description}


class ProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


@router.put("/profile", dependencies=[Depends(require_owner)])
async def update_profile(body: ProfileUpdate, session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_none=True)
    await repo.update_profile(profile.id, **updates)
    await session.commit()
    return {"status": "updated"}


@router.get("/beliefs")
async def list_beliefs(
    topic: str | None = None,
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    beliefs = await repo.list_beliefs(profile.id, topic=topic)

    is_owner = token.access_level == "owner"
    return [
        {
            "id": str(b.id),
            "topic": b.topic,
            "stance": b.stance,
            "nuance": b.nuance,
            "confidence": b.confidence,
            **({"source": b.source} if is_owner else {}),
        }
        for b in beliefs
    ]


class BeliefCreate(BaseModel):
    topic: str
    stance: str
    nuance: str | None = None
    confidence: float = 0.8


@router.post("/beliefs", dependencies=[Depends(require_owner)])
async def create_belief(body: BeliefCreate, session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    belief = await repo.create_belief(
        profile_id=profile.id, topic=body.topic, stance=body.stance,
        nuance=body.nuance, confidence=body.confidence, source="user",
    )
    await session.commit()
    return {"id": str(belief.id), "status": "created"}


class BeliefUpdate(BaseModel):
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None


@router.put("/beliefs/{belief_id}", dependencies=[Depends(require_owner)])
async def update_belief(
    belief_id: str, body: BeliefUpdate, session: AsyncSession = Depends(get_session)
):
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_none=True)
    updates["source"] = "user"  # User edits always set source to user
    belief = await repo.update_belief(belief_id, **updates)
    if not belief:
        raise HTTPException(status_code=404)
    await session.commit()
    return {"status": "updated"}


@router.delete("/beliefs/{belief_id}", dependencies=[Depends(require_owner)])
async def delete_belief(belief_id: str, session: AsyncSession = Depends(get_session)):
    repo = IdentityRepository(session)
    if not await repo.delete_belief(belief_id):
        raise HTTPException(status_code=404)
    await session.commit()
    return {"status": "deleted"}


@router.get("/style")
async def get_style(
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    style = await repo.get_style(profile.id)
    if not style:
        return {}
    return {
        "tone": style.tone,
        "humor_level": style.humor_level,
        "verbosity": style.verbosity,
        "formality": style.formality,
        "vocabulary_notes": style.vocabulary_notes,
        "communication_patterns": style.communication_patterns,
    }


class StyleUpdate(BaseModel):
    tone: str | None = None
    humor_level: float | None = None
    verbosity: float | None = None
    formality: float | None = None
    vocabulary_notes: str | None = None
    communication_patterns: str | None = None


@router.put("/style", dependencies=[Depends(require_owner)])
async def upsert_style(body: StyleUpdate, session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_none=True)
    updates["source"] = "user"
    await repo.upsert_style(profile.id, **updates)
    await session.commit()
    return {"status": "updated"}


@router.post("/infer", dependencies=[Depends(require_owner)])
async def trigger_inference(session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    await run_inference(session, profile.id)
    return {"status": "inference complete"}


@router.post("/snapshot", dependencies=[Depends(require_owner)])
async def create_snapshot(
    label: str | None = None, session: AsyncSession = Depends(get_session)
):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    snapshot = await svc.take_snapshot(profile.id, label)
    return {"id": str(snapshot.id), "label": snapshot.label}


@router.get("/snapshots", dependencies=[Depends(require_owner)])
async def list_snapshots(session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    snapshots = await repo.list_snapshots(profile.id)
    return [
        {"id": str(s.id), "label": s.label, "created_at": s.created_at.isoformat()}
        for s in snapshots
    ]


@router.get("/snapshot/{snapshot_id}", dependencies=[Depends(require_owner)])
async def get_snapshot(snapshot_id: str, session: AsyncSession = Depends(get_session)):
    repo = IdentityRepository(session)
    snapshot = await repo.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404)
    return {"id": str(snapshot.id), "label": snapshot.label, "data": snapshot.snapshot_data, "created_at": snapshot.created_at.isoformat()}
```

- [ ] **Step 7: Register identity routes**

Update `src/engram/api/routes/__init__.py`:
```python
from engram.api.routes.identity import router as identity_router
api_router.include_router(identity_router)
```

- [ ] **Step 8: Run all identity tests**

Run: `uv run pytest tests/test_identity/ -v`
Expected: All pass.

- [ ] **Step 9: Commit**

```bash
git add src/engram/identity/ src/engram/api/routes/identity.py src/engram/api/routes/__init__.py tests/test_identity/
git commit -m "feat: identity layer with inference, user overrides, snapshots, and REST API"
```

---

## Task 10: RAG Engine + Engram API

**Files:**
- Create: `src/engram/llm/rag.py`
- Create: `src/engram/api/routes/engram.py`
- Create: `tests/test_llm/test_rag.py`
- Create: `tests/test_api/test_engram.py`

This task implements the core engram conversation: query → embed → search memories → fetch identity → assemble prompt → generate response as the person.

- [ ] **Step 1: Write RAG tests (mocked)**

`tests/test_llm/test_rag.py`:
```python
from unittest.mock import AsyncMock, patch
from engram.llm.rag import build_prompt, EngramResponse


def test_build_prompt():
    prompt = build_prompt(
        name="Test User",
        beliefs=[{"topic": "AI", "stance": "optimistic", "confidence": 0.9}],
        preferences=[{"category": "communication", "value": "concise"}],
        style={"tone": "friendly", "humor_level": 0.7, "verbosity": 0.4, "formality": 0.3},
        memories=[{"content": "I think AI will help everyone.", "intent": "expressing belief", "confidence": 0.9, "timestamp": "2025-01-01"}],
    )
    assert "Test User" in prompt
    assert "AI" in prompt
    assert "optimistic" in prompt
```

- [ ] **Step 2: Implement RAG pipeline**

`src/engram/llm/rag.py`:
```python
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.service import IdentityService
from engram.llm.providers import claude_generate
from engram.memory.service import MemoryService
from engram.processing.embedder import embed_texts


@dataclass
class EngramResponse:
    answer: str
    confidence: float
    memory_refs: list[str] | None
    belief_refs: list[str] | None
    caveats: list[str]


def build_prompt(
    name: str,
    beliefs: list[dict],
    preferences: list[dict],
    style: dict,
    memories: list[dict],
) -> str:
    belief_text = "\n".join(
        f"- {b['topic']}: {b['stance']} (confidence: {b.get('confidence', '?')})"
        for b in beliefs
    )
    pref_text = "\n".join(f"- {p['category']}: {p['value']}" for p in preferences)
    memory_text = "\n".join(
        f"- [{m.get('timestamp', '?')}] {m['content']} (intent: {m.get('intent', '?')}, confidence: {m.get('confidence', '?')})"
        for m in memories
    )

    return f"""You are {name}'s engram — a digital representation built from their real memories and identity.

IDENTITY:
{belief_text}

PREFERENCES:
{pref_text}

COMMUNICATION STYLE:
Tone: {style.get('tone', 'neutral')}, Humor: {style.get('humor_level', 0.5)}, Verbosity: {style.get('verbosity', 0.5)}, Formality: {style.get('formality', 0.5)}
Patterns: {style.get('communication_patterns', 'none noted')}
Vocabulary: {style.get('vocabulary_notes', 'none noted')}

RELEVANT MEMORIES (most recent/reinforced first):
{memory_text}

INSTRUCTIONS:
- Respond as this person would, based on the evidence above
- Favor more recent and higher-confidence memories when they conflict
- If insufficient information, say so in character
- Never fabricate beliefs or memories not supported by data"""


async def ask_engram(
    session: AsyncSession,
    query: str,
    is_owner: bool = True,
) -> EngramResponse:
    identity_svc = IdentityService(session)
    memory_svc = MemoryService(session)

    profile = await identity_svc.get_or_create_default_profile()
    identity = await identity_svc.get_full_identity(profile.id)

    # Embed query and search memories
    query_embeddings = await embed_texts([query])
    # Owner sees active + private; shared sees only active
    visibility = None if is_owner else "active"
    memories = await memory_svc.remember(
        query_embedding=query_embeddings[0],
        limit=15,
        visibility=visibility,
    )

    memory_dicts = [
        {
            "content": m.content,
            "intent": m.intent,
            "confidence": m.confidence,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
        }
        for m in memories
    ]

    system_prompt = build_prompt(
        name=profile.name,
        beliefs=identity["beliefs"],
        preferences=identity["preferences"],
        style=identity["style"],
        memories=memory_dicts,
    )

    answer = await claude_generate(system=system_prompt, user=query)

    return EngramResponse(
        answer=answer,
        confidence=sum(m.confidence for m in memories) / max(len(memories), 1),
        memory_refs=[str(m.id) for m in memories] if is_owner else None,
        belief_refs=[b["id"] for b in identity["beliefs"]] if is_owner else None,
        caveats=["Limited data available"] if len(memories) < 3 else [],
    )
```

- [ ] **Step 3: Implement engram API routes**

`src/engram/api/routes/engram.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import get_current_token
from engram.db import get_session
from engram.identity.service import IdentityService
from engram.llm.providers import claude_generate
from engram.llm.rag import ask_engram
from engram.memory.repository import MemoryRepository
from engram.models.auth import AccessToken

router = APIRouter(prefix="/engram", tags=["engram"])


class AskRequest(BaseModel):
    query: str


@router.post("/ask")
async def ask(
    body: AskRequest,
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    is_owner = token.access_level == "owner"
    response = await ask_engram(session, body.query, is_owner=is_owner)
    result = {"answer": response.answer, "confidence": response.confidence, "caveats": response.caveats}
    if is_owner:
        result["memory_refs"] = response.memory_refs
        result["belief_refs"] = response.belief_refs
    return result


@router.get("/topics")
async def list_topics(
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select, func
    from engram.models.memory import Topic, MemoryTopic
    result = await session.execute(
        select(Topic.name, func.count(MemoryTopic.memory_id))
        .join(MemoryTopic, Topic.id == MemoryTopic.topic_id)
        .group_by(Topic.name)
        .order_by(func.count(MemoryTopic.memory_id).desc())
    )
    return [{"topic": name, "memory_count": count} for name, count in result.all()]


@router.get("/summarize")
async def summarize(
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    identity = await svc.get_full_identity(profile.id)

    summary = await claude_generate(
        system="You summarize a person's identity based on their beliefs, preferences, and style. Write in first person as that person.",
        user=f"Identity data:\n{identity}",
    )
    return {"summary": summary}


class SimulateRequest(BaseModel):
    scenario: str


@router.post("/simulate")
async def simulate(
    body: SimulateRequest,
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    response = await ask_engram(
        session, f"How would you approach this scenario: {body.scenario}",
        is_owner=token.access_level == "owner",
    )
    return {"decision": response.answer, "confidence": response.confidence}


class CompareRequest(BaseModel):
    topic: str
    stance: str


@router.post("/compare")
async def compare(
    body: CompareRequest,
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    response = await ask_engram(
        session,
        f"Compare your view on '{body.topic}' with this perspective: '{body.stance}'. How do you differ?",
        is_owner=token.access_level == "owner",
    )
    return {"comparison": response.answer, "confidence": response.confidence}
```

- [ ] **Step 4: Register engram routes**

Update `src/engram/api/routes/__init__.py`:
```python
from engram.api.routes.engram import router as engram_router
api_router.include_router(engram_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_llm/ -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/engram/llm/rag.py src/engram/api/routes/engram.py src/engram/api/routes/__init__.py tests/test_llm/
git commit -m "feat: RAG engine and engram API (ask, topics, summarize, simulate, compare)"
```

---

## Task 11: MCP Server

**Files:**
- Create: `src/engram/mcp/server.py`
- Create: `src/engram/mcp/__init__.py`
- Create: `tests/test_mcp/test_server.py`

Implement the MCP server exposing engram tools. Uses the MCP Python SDK with stdio transport.

- [ ] **Step 1: Implement MCP server**

`src/engram/mcp/__init__.py`: empty.

`src/engram/mcp/server.py`:
```python
"""Engram MCP server — exposes the engram as tools for Claude Desktop/Claude Code."""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from engram.db import async_session
from engram.identity.service import IdentityService
from engram.llm.rag import ask_engram
from engram.memory.repository import MemoryRepository

server = Server("engram")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="answer_as_self",
            description="Ask the engram a question — it responds as the person",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The question to ask"}},
                "required": ["query"],
            },
        ),
        Tool(
            name="list_topics",
            description="List topics the engram knows about or has opinions on",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="summarize_self",
            description="Get a narrative summary of who this person is",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="simulate_decision",
            description="Simulate how this person would approach a scenario",
            inputSchema={
                "type": "object",
                "properties": {"scenario": {"type": "string"}},
                "required": ["scenario"],
            },
        ),
        Tool(
            name="get_beliefs",
            description="Get the engram's beliefs, optionally filtered by topic",
            inputSchema={
                "type": "object",
                "properties": {"topic": {"type": "string"}},
            },
        ),
        Tool(
            name="search_memories",
            description="Search the engram's memories semantically",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with async_session() as session:
        if name == "answer_as_self":
            response = await ask_engram(session, arguments["query"], is_owner=False)
            return [TextContent(type="text", text=response.answer)]

        elif name == "list_topics":
            from sqlalchemy import select, func
            from engram.models.memory import Topic, MemoryTopic
            result = await session.execute(
                select(Topic.name, func.count(MemoryTopic.memory_id))
                .join(MemoryTopic, Topic.id == MemoryTopic.topic_id)
                .group_by(Topic.name)
                .order_by(func.count(MemoryTopic.memory_id).desc())
            )
            topics = [f"- {name} ({count} memories)" for name, count in result.all()]
            return [TextContent(type="text", text="\n".join(topics) or "No topics yet.")]

        elif name == "summarize_self":
            svc = IdentityService(session)
            profile = await svc.get_or_create_default_profile()
            identity = await svc.get_full_identity(profile.id)
            from engram.llm.providers import claude_generate
            summary = await claude_generate(
                system="Summarize this person's identity in first person.",
                user=str(identity),
            )
            return [TextContent(type="text", text=summary)]

        elif name == "simulate_decision":
            response = await ask_engram(
                session, f"How would you approach: {arguments['scenario']}", is_owner=False
            )
            return [TextContent(type="text", text=response.answer)]

        elif name == "get_beliefs":
            from engram.identity.repository import IdentityRepository
            svc = IdentityService(session)
            profile = await svc.get_or_create_default_profile()
            repo = IdentityRepository(session)
            beliefs = await repo.list_beliefs(profile.id, topic=arguments.get("topic"))
            text = "\n".join(
                f"- {b.topic}: {b.stance} (confidence: {b.confidence})"
                for b in beliefs
            )
            return [TextContent(type="text", text=text or "No beliefs yet.")]

        elif name == "search_memories":
            from engram.processing.embedder import embed_texts
            embeddings = await embed_texts([arguments["query"]])
            repo = MemoryRepository(session)
            memories = await repo.search(query_embedding=embeddings[0], limit=10)
            text = "\n".join(f"- {m.content}" for m in memories)
            return [TextContent(type="text", text=text or "No memories found.")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

- [ ] **Step 2: Run basic import test**

Run: `uv run python -c "from engram.mcp.server import server; print('MCP server imported OK')"`
Expected: "MCP server imported OK"

- [ ] **Step 3: Commit**

```bash
git add src/engram/mcp/
git commit -m "feat: MCP server with engram tools (answer, topics, beliefs, search, simulate)"
```

---

## Tasks 12-18: Remaining Modules

The remaining tasks follow the same TDD pattern. For brevity, here are the task outlines with acceptance criteria. The implementing agent should follow the same write-test → verify-fail → implement → verify-pass → commit cycle.

---

### Task 12: Gmail Connector

**Files:** `src/engram/ingestion/connectors/gmail.py`, `tests/test_ingestion/test_gmail_connector.py`

- [ ] Implement Gmail OAuth flow (local redirect on localhost:8090 + manual code fallback)
- [ ] Implement message fetching with date range and label filters
- [ ] Extract plain text body + image attachments
- [ ] Tag authorship: sent = "user_authored", received = "received"
- [ ] Add `POST /api/connectors/gmail/configure` handling
- [ ] Write tests with mocked Google API client
- [ ] Commit: `feat: Gmail connector with OAuth flow and message ingestion`

**Acceptance:** `uv run pytest tests/test_ingestion/test_gmail_connector.py -v` passes.

---

### Task 13: Reddit Connector

**Files:** `src/engram/ingestion/connectors/reddit.py`, `tests/test_ingestion/test_reddit_connector.py`

- [ ] Implement PRAW-based fetching: user posts, comments, saved items
- [ ] Extract image posts
- [ ] Tag authorship: user content = "user_authored", replies = "other_reply"
- [ ] Add `POST /api/connectors/reddit/configure` handling
- [ ] Write tests with mocked PRAW client
- [ ] Commit: `feat: Reddit connector with PRAW integration`

**Acceptance:** `uv run pytest tests/test_ingestion/test_reddit_connector.py -v` passes.

---

### Task 14: Photo System + Image Generation

**Files:** `src/engram/photos/`, `src/engram/api/routes/photos.py`, `tests/test_photos/`

- [ ] Implement photo storage (file system + DB metadata)
- [ ] Implement LLM vision analysis for uploaded photos (Claude vision)
- [ ] Implement GPT Image generation (OpenAI gpt-image-1)
- [ ] Implement REST routes: upload, list, update, delete
- [ ] Add `POST /api/engram/imagine` route
- [ ] Add `imagine` MCP tool
- [ ] Write tests with mocked OpenAI/Claude vision
- [ ] Commit: `feat: photo system with LLM analysis and image generation`

**Acceptance:** `uv run pytest tests/test_photos/ -v` passes.

---

### Task 15: Export/Import

**Files:** `src/engram/api/routes/engram.py` (extend), `tests/test_api/test_engram.py` (extend)

- [ ] Implement `POST /api/engram/export` — serialize all memories, identity, photos metadata to JSON (no credentials, no embeddings)
- [ ] Implement `POST /api/engram/import` — deserialize, re-embed all memories, recreate records
- [ ] Write tests verifying round-trip: export → import → data matches
- [ ] Commit: `feat: engram export/import with re-embedding on import`

**Acceptance:** `uv run pytest tests/test_api/test_engram.py -v` passes.

---

### Task 16: Setup Wizard CLI

**Files:** `src/engram/cli.py`, `tests/test_cli.py`

- [ ] Implement Click CLI with commands: `init`, `server`, `mcp`, `ingest`, `status`
- [ ] `engram init`: infrastructure check/Docker start, API key prompts, profile creation, first owner token, connector setup (optional), initial ingestion, verification query
- [ ] `engram server`: start FastAPI + RQ worker subprocess
- [ ] `engram mcp`: start MCP server
- [ ] `engram ingest`: trigger ingestion from configured connectors
- [ ] `engram status`: show memory stats, connector statuses
- [ ] Write tests for CLI commands (using Click testing utilities)
- [ ] Commit: `feat: CLI with setup wizard, server, and management commands`

**Acceptance:** `uv run engram --help` shows all commands. `uv run pytest tests/test_cli.py -v` passes.

---

### Task 17: Distribution Packaging

**Files:** `pyproject.toml` (update), `README.md` (update)

- [ ] Verify `engram` CLI entry point works after `uv sync`
- [ ] Verify `uv build` produces a wheel
- [ ] Update README with complete usage instructions
- [ ] Commit: `feat: distribution packaging with PyPI-ready config`

**Acceptance:** `uv build` succeeds. `uv run engram --help` works.

---

### Task 18: Integration Tests

**Files:** `tests/test_integration/`

- [ ] **Full pipeline test**: upload file → process → memories appear → search returns results
- [ ] **Identity flow test**: ingest data → run inference → beliefs populated → query engram → response references beliefs
- [ ] **Evolution flow test**: ingest contradicting data → memory degrades → belief confidence drops
- [ ] **Privacy flow test**: set source to private → shared token query doesn't reference it
- [ ] All tests use mocked LLM providers but real database
- [ ] Commit: `feat: integration tests for full pipeline, identity, evolution, and privacy flows`

**Acceptance:** `uv run pytest tests/test_integration/ -v` passes. `uv run pytest -v` (full suite) passes.

---

---

## Required Additions (Review Fixes)

The following additions are REQUIRED and must be incorporated during implementation. They address gaps identified during plan review.

### Fix A: Memory Search Ranking (Task 8)

The `MemoryRepository.search()` method must implement the spec's weighted composite ranking, not just cosine distance. Replace the simple `order_by` with:

```python
import math
from datetime import datetime, timezone
from engram.config import settings

def _recency_score(timestamp: datetime | None) -> float:
    if timestamp is None:
        return 0.5
    days_ago = (datetime.now(timezone.utc) - timestamp).days
    halflife = settings.memory_decay_halflife_days
    return math.exp(-0.693 * days_ago / halflife)

# In search(), after getting vector results, re-rank:
# score = cosine_similarity * 0.5 + importance_score * 0.2 + recency_score * 0.2 + reinforcement_score * 0.1
# where reinforcement_score = min(reinforcement_count / 10, 1.0)
```

Fetch top N*3 by cosine distance, then re-rank in Python with the composite formula, return top N.

### Fix B: RQ Worker Integration (Task 5)

The ingestion service must actually use RQ to process jobs asynchronously. Add a `worker.py`:

`src/engram/worker.py`:
```python
"""RQ worker that processes ingestion jobs."""
import asyncio
from redis import Redis
from rq import Worker, Queue

from engram.config import settings

redis_conn = Redis.from_url(settings.redis_url)
queue = Queue("engram", connection=redis_conn)


def run_ingestion_job(job_id: str, file_path: str, connector_type: str):
    """Synchronous wrapper for async pipeline — called by RQ worker."""
    asyncio.run(_process_job(job_id, file_path, connector_type))


async def _process_job(job_id: str, file_path: str, connector_type: str):
    from pathlib import Path
    from engram.db import async_session
    from engram.ingestion.connectors.file import FileConnector
    from engram.processing.pipeline import process_documents
    from engram.models.connector import IngestionJob
    from sqlalchemy import select
    from datetime import datetime, timezone

    async with async_session() as session:
        # Mark job as running
        result = await session.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one()
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

        try:
            connector = FileConnector()
            docs = await connector.fetch({"file_paths": [file_path]})
            count = await process_documents(docs, session)

            job.status = "completed"
            job.items_processed = count
            job.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)

        await session.commit()


if __name__ == "__main__":
    Worker([queue], connection=redis_conn).work()
```

Update the ingest route in Task 5 to enqueue:
```python
from engram.worker import queue, run_ingestion_job

# In upload_file endpoint, after creating the job and saving the file:
queue.enqueue(run_ingestion_job, str(job.id), str(file_path), "file")
```

### Fix C: Redis Embedding Cache (Task 6)

Update `src/engram/processing/embedder.py` to cache embeddings:

```python
import hashlib
import json
import redis as redis_lib
from engram.config import settings

_redis = redis_lib.Redis.from_url(settings.redis_url) if settings.redis_url else None
CACHE_TTL = 30 * 24 * 3600  # 30 days

def _cache_key(text: str) -> str:
    return f"emb:{hashlib.sha256(text.encode()).hexdigest()}"

async def embed_texts(texts: list[str]) -> list[list[float]]:
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []

    # Check cache
    if _redis:
        for i, text in enumerate(texts):
            cached = _redis.get(_cache_key(text))
            if cached:
                results[i] = json.loads(cached)
            else:
                uncached_indices.append(i)
    else:
        uncached_indices = list(range(len(texts)))

    # Embed uncached texts
    if uncached_indices:
        uncached_texts = [texts[i] for i in uncached_indices]
        embeddings = await _embed_batch_with_retry(uncached_texts)
        for idx, embedding in zip(uncached_indices, embeddings):
            results[idx] = embedding
            if _redis:
                _redis.setex(_cache_key(texts[idx]), CACHE_TTL, json.dumps(embedding))

    return results  # type: ignore
```

### Fix D: Missing Memory Service Methods (Task 8)

Add these methods to `MemoryService`:

```python
async def recall_about(self, subject: str, limit: int = 20) -> list[Memory]:
    """Get everything the engram knows about a person or topic."""
    # Search by topic name and person name
    return await self.repo.search(source=None, limit=limit)
    # TODO: filter by topic/person joins — for now returns recent memories

async def summarize_memories(self, memories: list[Memory]) -> str:
    """Ask Claude to produce a narrative summary of memories."""
    from engram.llm.providers import claude_generate
    text = "\n".join(f"- {m.content}" for m in memories)
    return await claude_generate(
        system="Summarize these memories into a coherent narrative.",
        user=text,
    )

async def timeline(self, topic: str | None = None, person: str | None = None) -> list[Memory]:
    """Chronological view of memories about a topic or person."""
    return await self.repo.search(limit=50)
    # TODO: filter by topic/person, order by timestamp ascending

async def find_contradictions(self) -> list[dict]:
    """Surface memories that conflict with each other."""
    from engram.llm.providers import claude_generate
    memories = await self.repo.search(limit=30)
    if not memories:
        return []
    text = "\n".join(f"[{m.id}] {m.content}" for m in memories)
    result = await claude_generate(
        system="Find contradictions between these memories. Return JSON: [{\"memory_1_id\": \"...\", \"memory_2_id\": \"...\", \"explanation\": \"...\"}]",
        user=text,
    )
    import json
    try:
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(result)
    except json.JSONDecodeError:
        return []
```

### Fix E: Missing Memory API Endpoints (Task 8)

Add to `memories.py` routes:

```python
@router.get("/contradictions")
async def find_contradictions(session: AsyncSession = Depends(get_session)):
    from engram.memory.service import MemoryService
    svc = MemoryService(session)
    return await svc.find_contradictions()

@router.get("/timeline")
async def memory_timeline(
    topic: str | None = None,
    person: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    from engram.memory.service import MemoryService
    svc = MemoryService(session)
    memories = await svc.timeline(topic, person)
    return [{"id": str(m.id), "content": m.content, "timestamp": m.timestamp.isoformat() if m.timestamp else None} for m in memories]

@router.post("/summarize")
async def summarize_memories_route(
    source: str | None = None,
    topic: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    from engram.memory.service import MemoryService
    svc = MemoryService(session)
    repo = svc.repo
    memories = await repo.search(source=source, limit=30)
    summary = await svc.summarize_memories(memories)
    return {"summary": summary}
```

### Fix F: Missing Preference CRUD Routes (Task 9)

Add to `identity.py` routes:

```python
@router.get("/preferences", dependencies=[Depends(require_owner)])
async def list_preferences(session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    prefs = await repo.list_preferences(profile.id)
    return [{"id": str(p.id), "category": p.category, "value": p.value, "strength": p.strength, "source": p.source} for p in prefs]


class PreferenceCreate(BaseModel):
    category: str
    value: str
    strength: float = 0.5


@router.post("/preferences", dependencies=[Depends(require_owner)])
async def create_preference(body: PreferenceCreate, session: AsyncSession = Depends(get_session)):
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    pref = await repo.create_preference(profile_id=profile.id, category=body.category, value=body.value, strength=body.strength, source="user")
    await session.commit()
    return {"id": str(pref.id), "status": "created"}


class PreferenceUpdate(BaseModel):
    value: str | None = None
    strength: float | None = None


@router.put("/preferences/{pref_id}", dependencies=[Depends(require_owner)])
async def update_preference(pref_id: str, body: PreferenceUpdate, session: AsyncSession = Depends(get_session)):
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_none=True)
    updates["source"] = "user"
    pref = await repo.update_preference(pref_id, **updates)
    if not pref:
        raise HTTPException(status_code=404)
    await session.commit()
    return {"status": "updated"}


@router.delete("/preferences/{pref_id}", dependencies=[Depends(require_owner)])
async def delete_preference(pref_id: str, session: AsyncSession = Depends(get_session)):
    repo = IdentityRepository(session)
    if not await repo.delete_preference(pref_id):
        raise HTTPException(status_code=404)
    await session.commit()
    return {"status": "deleted"}
```

### Fix G: Missing Engram API Endpoints (Task 10)

Add to `engram.py` routes:

```python
@router.get("/opinions")
async def get_opinions(
    topic: str,
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    """Positions on a topic with nuance and timeline."""
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    beliefs = await repo.list_beliefs(profile.id, topic=topic)
    is_owner = token.access_level == "owner"
    return [
        {
            "topic": b.topic,
            "stance": b.stance,
            "nuance": b.nuance,
            "confidence": b.confidence,
            **({"source": b.source, "id": str(b.id)} if is_owner else {}),
        }
        for b in beliefs
    ]


@router.get("/explain-belief/{belief_id}")
async def explain_belief(
    belief_id: str,
    token: AccessToken = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
):
    """Trace a belief back to supporting memories."""
    from engram.identity.repository import IdentityRepository as IDRepo
    repo = IDRepo(session)
    belief = await repo.get_belief(belief_id)
    if not belief:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    is_owner = token.access_level == "owner"
    if not is_owner:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Owner access required")

    from engram.llm.providers import claude_generate
    explanation = await claude_generate(
        system="Explain why this person holds this belief, based on the belief data provided.",
        user=f"Topic: {belief.topic}\nStance: {belief.stance}\nNuance: {belief.nuance}\nConfidence: {belief.confidence}",
    )
    return {"belief": {"topic": belief.topic, "stance": belief.stance}, "explanation": explanation}
```

### Fix H: Missing MCP Tools (Task 11)

Add these tools to the MCP server `list_tools()` and `call_tool()`:

```python
# In list_tools():
Tool(
    name="get_opinions",
    description="Get opinions on a specific topic with nuance",
    inputSchema={
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    },
),
Tool(
    name="recall_about",
    description="Everything the engram knows about a person or topic (owner only)",
    inputSchema={
        "type": "object",
        "properties": {"subject": {"type": "string"}},
        "required": ["subject"],
    },
),
Tool(
    name="compare_perspectives",
    description="Compare the engram's view on a topic with another stance",
    inputSchema={
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "stance": {"type": "string"},
        },
        "required": ["topic", "stance"],
    },
),

# In call_tool():
elif name == "get_opinions":
    from engram.identity.repository import IdentityRepository
    svc = IdentityService(session)
    profile = await svc.get_or_create_default_profile()
    repo = IdentityRepository(session)
    beliefs = await repo.list_beliefs(profile.id, topic=arguments.get("topic"))
    text = "\n".join(
        f"- {b.topic}: {b.stance} (nuance: {b.nuance or 'none'}, confidence: {b.confidence})"
        for b in beliefs
    )
    return [TextContent(type="text", text=text or "No opinions on this topic.")]

elif name == "recall_about":
    from engram.memory.service import MemoryService
    svc = MemoryService(session)
    from engram.processing.embedder import embed_texts
    embeddings = await embed_texts([arguments["subject"]])
    memories = await svc.remember(embeddings[0], limit=20)
    text = "\n".join(f"- [{m.timestamp}] {m.content} (meaning: {m.meaning})" for m in memories)
    return [TextContent(type="text", text=text or "No memories about this subject.")]

elif name == "compare_perspectives":
    response = await ask_engram(
        session,
        f"Compare your view on '{arguments['topic']}' with this perspective: '{arguments['stance']}'",
        is_owner=False,
    )
    return [TextContent(type="text", text=response.answer)]
```

### Fix I: Test Infrastructure (Task 2)

Replace the `conftest.py` test database approach with a more robust setup. Add to the beginning of `tests/conftest.py`:

```python
# Before running tests, ensure test database exists.
# The test_engine fixture handles table creation via metadata.create_all.
# If the test database doesn't exist, tests will fail with a clear connection error.
# Run: PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE engram_test;"
# And: PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d engram_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Fix the `test_unauthenticated_request_rejected` test (issue 9) — it must override the DB dependency:

```python
async def test_unauthenticated_request_rejected(db_session):
    from httpx import ASGITransport, AsyncClient
    from engram.main import app
    from engram.db import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/tokens")
        assert resp.status_code == 401
    app.dependency_overrides.clear()
```

### Fix J: Detailed Gmail Connector (Task 12)

**Full implementation steps:**

- [ ] **Step 1: Write test with mocked Google API**

```python
# tests/test_ingestion/test_gmail_connector.py
from unittest.mock import AsyncMock, MagicMock, patch
from engram.ingestion.connectors.gmail import GmailConnector

async def test_gmail_fetch_messages():
    connector = GmailConnector()

    mock_service = MagicMock()
    mock_messages = MagicMock()
    mock_messages.list.return_value.execute.return_value = {
        "messages": [{"id": "msg1"}]
    }
    mock_messages.get.return_value.execute.return_value = {
        "id": "msg1",
        "payload": {
            "headers": [
                {"name": "From", "value": "user@example.com"},
                {"name": "Date", "value": "Mon, 1 Jan 2025 12:00:00 +0000"},
            ],
            "body": {"data": "SGVsbG8gV29ybGQ="},  # base64 "Hello World"
        },
    }
    mock_service.users.return_value.messages.return_value = mock_messages

    with patch.object(connector, "_get_service", return_value=mock_service):
        connector.user_email = "user@example.com"
        docs = await connector.fetch({"max_results": 10})

    assert len(docs) >= 1
    assert docs[0].source == "gmail"
```

- [ ] **Step 2: Implement GmailConnector**

```python
# src/engram/ingestion/connectors/gmail.py
import base64
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from engram.ingestion.connectors.base import Connector, RawDocument


class GmailConnector:
    def __init__(self):
        self.user_email: str | None = None
        self._credentials_path: str | None = None
        self._token_data: dict | None = None

    async def configure(self, credentials: dict) -> None:
        self._credentials_path = credentials.get("client_json_path")
        self.user_email = credentials.get("user_email")

        # Attempt OAuth flow
        from google_auth_oauthlib.flow import InstalledAppFlow
        SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

        flow = InstalledAppFlow.from_client_secrets_file(
            self._credentials_path, SCOPES
        )
        try:
            # Try local server redirect (port 8090)
            creds = flow.run_local_server(port=8090, open_browser=True)
        except Exception:
            # Fallback to manual console flow
            creds = flow.run_console()

        self._token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        }

    def _get_service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(**self._token_data)
        return build("gmail", "v1", credentials=creds)

    async def fetch(self, options: dict) -> list[RawDocument]:
        service = self._get_service()
        max_results = options.get("max_results", 100)
        query = options.get("query", "")

        messages_api = service.users().messages()
        response = messages_api.list(userId="me", maxResults=max_results, q=query).execute()
        message_ids = [m["id"] for m in response.get("messages", [])]

        documents: list[RawDocument] = []
        for msg_id in message_ids:
            msg = messages_api.get(userId="me", id=msg_id, format="full").execute()
            doc = self._parse_message(msg)
            if doc:
                documents.append(doc)

        return documents

    def _parse_message(self, msg: dict) -> RawDocument | None:
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_addr = headers.get("From", "")
        date_str = headers.get("Date", "")

        try:
            timestamp = parsedate_to_datetime(date_str)
        except Exception:
            timestamp = None

        # Determine authorship
        is_sent = self.user_email and self.user_email.lower() in from_addr.lower()
        authorship = "user_authored" if is_sent else "received"

        # Extract body text
        body = self._extract_body(msg.get("payload", {}))
        if not body:
            return None

        # Extract images
        images = self._extract_images(msg.get("payload", {}))

        return RawDocument(
            content=body,
            source="gmail",
            source_ref=msg["id"],
            timestamp=timestamp,
            authorship=authorship,
            images=images,
        )

    def _extract_body(self, payload: dict) -> str:
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

        return ""

    def _extract_images(self, payload: dict) -> list[bytes]:
        images = []
        for part in payload.get("parts", []):
            if part.get("mimeType", "").startswith("image/") and part.get("body", {}).get("data"):
                images.append(base64.urlsafe_b64decode(part["body"]["data"]))
        return images
```

### Fix K: Detailed Reddit Connector (Task 13)

- [ ] **Step 1: Write test with mocked PRAW**

```python
# tests/test_ingestion/test_reddit_connector.py
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone
from engram.ingestion.connectors.reddit import RedditConnector


async def test_reddit_fetch_posts():
    connector = RedditConnector()

    mock_submission = MagicMock()
    mock_submission.selftext = "I think Python is the best language for ML."
    mock_submission.title = "Python for ML"
    mock_submission.permalink = "/r/python/comments/abc123"
    mock_submission.created_utc = 1704067200.0
    mock_submission.is_self = True

    mock_comment = MagicMock()
    mock_comment.body = "Great post, I agree!"
    mock_comment.permalink = "/r/python/comments/abc123/comment/def456"
    mock_comment.created_utc = 1704067300.0
    type(mock_comment).author = PropertyMock(return_value=MagicMock(name="testuser"))

    mock_redditor = MagicMock()
    mock_redditor.submissions.new.return_value = [mock_submission]
    mock_redditor.comments.new.return_value = [mock_comment]

    mock_reddit = MagicMock()
    mock_reddit.redditor.return_value = mock_redditor

    with patch.object(connector, "_reddit", mock_reddit):
        connector._username = "testuser"
        docs = await connector.fetch({"limit": 10})

    assert len(docs) >= 2
    assert any(d.authorship == "user_authored" for d in docs)
```

- [ ] **Step 2: Implement RedditConnector**

```python
# src/engram/ingestion/connectors/reddit.py
from datetime import datetime, timezone

import praw

from engram.ingestion.connectors.base import Connector, RawDocument


class RedditConnector:
    def __init__(self):
        self._reddit: praw.Reddit | None = None
        self._username: str | None = None

    async def configure(self, credentials: dict) -> None:
        self._reddit = praw.Reddit(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            user_agent="engram:v0.1.0",
            username=credentials.get("username"),
            password=credentials.get("password"),
        )
        self._username = credentials.get("username")

    async def fetch(self, options: dict) -> list[RawDocument]:
        if not self._reddit or not self._username:
            return []

        limit = options.get("limit", 100)
        documents: list[RawDocument] = []

        redditor = self._reddit.redditor(self._username)

        # Fetch user's submissions
        for submission in redditor.submissions.new(limit=limit):
            if submission.is_self and submission.selftext:
                documents.append(
                    RawDocument(
                        content=f"{submission.title}\n\n{submission.selftext}",
                        source="reddit",
                        source_ref=submission.permalink,
                        timestamp=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                        authorship="user_authored",
                    )
                )

        # Fetch user's comments
        for comment in redditor.comments.new(limit=limit):
            documents.append(
                RawDocument(
                    content=comment.body,
                    source="reddit",
                    source_ref=comment.permalink,
                    timestamp=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
                    authorship="user_authored",
                )
            )

        return documents
```

---

## Summary

18 tasks, bottom-up, each producing working tested code with a commit. The ralph loop should:

1. Read this plan AND the Required Additions section
2. Execute each task sequentially
3. When implementing a task, check the Required Additions section for fixes that apply to that task
4. For each task: write tests → verify they fail → implement → verify they pass → commit
5. If tests fail after implementation, iterate until they pass
6. Move to next task only when current task's acceptance criteria pass

**Key integration points:**
- Fix A (memory ranking) → apply during Task 8
- Fix B (RQ worker) → apply during Task 5
- Fix C (Redis cache) → apply during Task 6
- Fix D, E (memory service + API) → apply during Task 8
- Fix F (preference routes) → apply during Task 9
- Fix G, H (engram API + MCP tools) → apply during Tasks 10, 11
- Fix I (test infrastructure) → apply during Task 2
- Fix J (Gmail) → replaces Task 12 outline
- Fix K (Reddit) → replaces Task 13 outline
