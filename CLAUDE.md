# Engram

A self-hosted digital engram platform — a realistic digital representation of a person built from their real data. See **[ENGRAMDESIGN.md](ENGRAMDESIGN.md)** for full architecture, design decisions, database schema, and roadmap.

## Quick Reference

```bash
docker compose up -d          # Start pgvector (5433) + Redis (6379)
uv sync --all-extras          # Install dependencies
uv run engram init            # Setup wizard
uv run engram server          # Start REST API (port 8000)
uv run engram mcp             # Start MCP server (stdio)
uv run pytest tests/ -v       # Run tests (310+)
uv run ruff check src/ tests/ # Lint
```

## Critical Rules

- **NEVER drop or recreate database tables** — the database has real user data (10,000+ memories). Always use additive Alembic migrations.
- **NEVER commit API keys or .env files** — they are gitignored.
- **OpenAI API is used for both generation and embeddings** — Anthropic support is deferred.
- **All timestamps must be timezone-naive** — asyncpg requires naive datetimes for TIMESTAMP columns.
- **User-set identity traits (source="user") are never overwritten by inference.**

## Key Entry Points

| What | Where |
|------|-------|
| FastAPI app | `src/engram/main.py` |
| CLI commands | `src/engram/cli.py` |
| Config (env vars) | `src/engram/config.py` |
| Processing pipeline | `src/engram/processing/pipeline.py` |
| Memory search (composite ranking) | `src/engram/memory/repository.py` |
| Identity inference (temporal evolve) | `src/engram/identity/inference.py` |
| RAG pipeline (ask the engram) | `src/engram/llm/rag.py` |
| MCP server (9 tools) | `src/engram/mcp/server.py` |
| Export parsers | `src/engram/ingestion/parsers/` |
| Database models | `src/engram/models/` |
| Ingestion scripts | `scripts/` |

## Database

Docker Compose: pgvector on port **5433**, Redis on port **6379**. Connection: `postgresql+asyncpg://postgres:postgres@localhost:5433/engram`

21 tables — see ENGRAMDESIGN.md for full schema. Key tables: `memories` (pgvector embeddings), `beliefs` (temporal valid_from/valid_until), `relationships`, `locations`, `life_events`, `photos`.

## Testing

```bash
uv run pytest tests/ -v                    # Full suite
uv run pytest tests/test_memory/ -v        # Memory module only
uv run pytest tests/test_integration/ -v   # Integration tests
```

Tests use a separate `engram_test` database on the same Docker Postgres. Session-scoped async fixtures with `asyncio_default_test_loop_scope = "session"`.
