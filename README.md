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

5. Install the web frontend:

   ```bash
   cd web && npm install && cd ..
   ```

6. Start everything:

   ```bash
   ./start.sh
   ```

   This starts Docker, the backend (port 8000), and the frontend (port 3001). Open **http://localhost:3001** and enter your engram token.

   Or start services individually:
   ```bash
   uv run engram server          # Backend only
   cd web && npm run dev -- -p 3001  # Frontend only
   ```

## CLI Commands

```bash
engram init        # Interactive setup wizard
engram server      # Start REST API server
engram mcp         # Start MCP server
engram ingest      # Run data ingestion
engram status      # Show engram statistics
```

## Data Sources

Engram can import your personal data from several platforms. The `engram init` wizard will guide you through downloading and configuring each export.

### Gmail (Google Takeout)

1. Go to https://takeout.google.com
2. Deselect all, then select only "Mail"
3. Choose .mbox format
4. Click "Create export" and wait for the email
5. Download and extract the ZIP archive

### Reddit (Data Request)

1. Go to https://www.reddit.com/settings/data-request
2. Click "Request data"
3. Wait for the email (can take up to 30 days)
4. Download and extract the archive

### Facebook (Download Your Information)

1. Go to Facebook Settings > Your Information > Download Your Information
2. Select format: JSON
3. Select data to include (Posts, Comments, Messages recommended)
4. Click "Request Download" and wait for notification
5. Download and extract the archive

### Instagram (Download Your Data)

1. Go to Instagram Settings > Privacy and Security > Download Your Data
2. Select format: JSON
3. Click "Request Download" and wait for email
4. Download and extract the archive

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
```
