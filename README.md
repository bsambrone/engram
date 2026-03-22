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
