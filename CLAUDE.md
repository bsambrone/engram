# Engram — Project Guide

## What This Is

A self-hosted digital engram platform. Ingests personal data (emails, social media posts, messages, photos), builds structured living memories with LLM-extracted meaning, infers identity traits, and exposes the engram via REST API and MCP server.

Inspired by the engram concept from Cyberpunk 2077 — a realistic digital representation of a person built from their real data.

## Tech Stack

- **Python 3.12+** with **FastAPI** (async)
- **PostgreSQL 16 + pgvector** (Docker, port 5433) for storage + vector search
- **Redis** (Docker, port 6379) for embedding cache + job queue
- **OpenAI API** for embeddings (text-embedding-3-small) and generation (gpt-5.2)
- **SQLAlchemy** (async/asyncpg) + **Alembic** for ORM and migrations
- **MCP Python SDK** for Model Context Protocol server
- **uv** for package management, **pytest** for testing, **ruff** for linting

## Architecture

Monolith FastAPI app with modular packages:
```
Data Exports → Parsers → Processing Pipeline → Memory Store → Identity Layer → RAG Engine → MCP/REST API
```

### Key modules:
- `src/engram/ingestion/parsers/` — Export parsers for Gmail (MBOX), Reddit (CSV), Facebook (JSON), Instagram (JSON)
- `src/engram/processing/` — Pipeline: normalize → chunk → embed → LLM analyze → store
- `src/engram/memory/` — Living memory system with reinforcement, degradation, evolution
- `src/engram/identity/` — Beliefs, preferences, style inference with temporal tracking
- `src/engram/llm/` — LLM providers + RAG pipeline
- `src/engram/mcp/` — MCP server exposing engram as tools
- `src/engram/api/` — REST API with owner/shared access control
- `src/engram/photos/` — Photo storage, vision analysis, image generation

## Database

Docker Compose runs pgvector on port 5433 and Redis on port 6379.

Key tables: memories (with pgvector embeddings), topics, people, beliefs (with temporal valid_from/valid_until), preferences, style_profiles, identity_snapshots, relationships, locations, life_events, photos, data_exports, ingestion_jobs, access_tokens.

Migrations are managed with Alembic. **NEVER drop/recreate tables** — the database has real user data. Always use additive migrations.

## Running

```bash
docker compose up -d          # Start pgvector + Redis
uv sync --all-extras          # Install dependencies
uv run engram init            # Setup wizard
uv run engram server          # Start REST API
uv run engram mcp             # Start MCP server
uv run pytest tests/ -v       # Run tests
```

## Key Design Decisions

- **Data exports, not live APIs** — Users download their data from each platform (Google Takeout, Reddit data request, Facebook/Instagram download). Engram processes the files offline.
- **OpenAI for everything** — Embeddings (text-embedding-3-small) and generation (configurable model). Anthropic support deferred.
- **Temporal identity** — Beliefs and preferences have valid_from/valid_until. The engram can "respond as of" a specific date.
- **Living memories** — Memories can be reinforced (new data supports them), degraded (contradicted), or evolved (nuanced over time).
- **Owner vs shared access** — Owner sees full citations and sources. Shared access sees only the engram's responses.

## Current State

- Full processing pipeline working with real data
- ~7,000 memories from Gmail, Reddit, Instagram
- Identity inference with 21+ beliefs, 40+ preferences, style profile
- MCP server with 9 tools
- 300+ tests passing
- Facebook data imported (free signals), LLM processing pending

## What's Next

- Process Facebook posts/comments/messages through LLM pipeline
- Web UI for memory/identity management and visualization
- Timeline visualization of belief evolution
- Voice synthesis
- Continuous learning (real-time ingestion)
