"""Engram CLI with interactive setup wizard."""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Utility helpers (kept at module level so tests can mock them)
# ---------------------------------------------------------------------------

def check_postgres(host: str = "localhost", port: int = 5433, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to Postgres succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_redis(host: str = "localhost", port: int = 6379, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to Redis succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _check_pgvector(database_url: str) -> bool:
    """Return True if the pgvector extension is installed."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            return result.scalar() is not None
    finally:
        await engine.dispose()


async def _check_database_exists(database_url: str) -> bool:
    """Return True if we can connect to the database."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def validate_anthropic_key(api_key: str) -> tuple[bool, str]:
    """Validate an Anthropic API key by making a small API call.

    Returns (success, message).
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )
        model = response.model
        return True, f"Claude API key works! (Model: {model})"
    except Exception as exc:
        return False, f"Anthropic validation failed: {exc}"


def validate_openai_key(api_key: str) -> tuple[bool, str]:
    """Validate an OpenAI API key by creating a test embedding.

    Returns (success, message).
    """
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        client.embeddings.create(input=["test"], model="text-embedding-ada-002")
        return True, "OpenAI API key works! (Embedding model: text-embedding-ada-002)"
    except Exception as exc:
        return False, f"OpenAI validation failed: {exc}"


async def _create_identity_profile(database_url: str, name: str, description: str | None):
    """Create an identity profile row and return its id."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from engram.models.identity import IdentityProfile

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            profile = IdentityProfile(name=name, description=description or None)
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            return profile.id
    finally:
        await engine.dispose()


async def _create_access_token(
    database_url: str, raw_token: str, name: str = "owner-init"
):
    """Hash *raw_token* and store it as an owner access token."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from engram.models.auth import AccessToken

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            token = AccessToken(
                name=name,
                token_hash=token_hash,
                access_level="owner",
            )
            session.add(token)
            await session.commit()
    finally:
        await engine.dispose()


async def _verify_tables(database_url: str) -> bool:
    """Return True if key tables exist after migration."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            tables = {row[0] for row in result.fetchall()}
            required = {"access_tokens", "identity_profiles", "memories"}
            return required.issubset(tables)
    finally:
        await engine.dispose()


async def _verify_health(host: str, port: int) -> bool:
    """Quick HTTP check against the health endpoint."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{host}:{port}/health", timeout=5.0)
            return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Engram -- A self-hosted digital engram platform."""
    pass


@cli.command()
def server():
    """Start the FastAPI REST API server."""
    import uvicorn

    from engram.config import settings

    uvicorn.run(
        "engram.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
    )


@cli.command()
def mcp():
    """Start the MCP server."""
    click.echo("MCP server not yet implemented. Coming in a later task.")


@cli.command()
def ingest():
    """Run data ingestion from configured exports."""
    click.echo("Ingestion not yet implemented. Coming in a later task.")


@cli.command()
def status():
    """Show engram statistics."""
    click.echo("Status not yet implemented. Coming in a later task.")


# ---------------------------------------------------------------------------
# Init wizard helpers (one function per step, called sequentially)
# ---------------------------------------------------------------------------

def _prompt_llm_provider(
    provider_name: str,
    validate_fn,
) -> str | None:
    """Prompt the user for an LLM provider API key with auth method selection.

    Returns the validated API key, or None if the user chose subscription (stub).
    """
    click.echo(f"\n--- {provider_name} ---")
    click.echo("Authentication method:")
    click.echo("  [1] API Key (recommended)")
    click.echo("  [2] Subscription-based access (coming soon)")

    choice = click.prompt("Choice", default="1", type=click.Choice(["1", "2"]))

    if choice == "2":
        click.echo(
            f"\nSubscription-based access is not yet available. This feature is planned "
            f"for when {provider_name} supports subscription-based API access. "
            f"Please use an API key for now."
        )
        # Re-prompt with API key path
        choice = "1"

    if choice == "1":
        while True:
            api_key = click.prompt(f"Enter your {provider_name} API key", hide_input=False)
            click.echo("Validating... ", nl=False)
            ok, msg = validate_fn(api_key)
            if ok:
                click.echo(f"  {msg}")
                return api_key
            else:
                click.echo(f"  {msg}")
                if not click.confirm("Try again?", default=True):
                    return None

    return None


def _step1_infrastructure() -> bool:
    """Step 1: Infrastructure Check. Returns True on success."""
    click.echo("\n Step 1: Infrastructure Check\n")
    click.echo("Checking Docker containers...")

    pg_ok = check_postgres()
    if pg_ok:
        click.echo("  PostgreSQL (pgvector) is running on port 5433")
    else:
        click.echo("  PostgreSQL is NOT reachable on port 5433")

    redis_ok = check_redis()
    if redis_ok:
        click.echo("  Redis is running on port 6379")
    else:
        click.echo("  Redis is NOT reachable on port 6379")

    if not pg_ok or not redis_ok:
        click.echo(
            "\nPlease make sure Docker is running and start the containers:\n"
            "  docker compose up -d\n"
        )
        if not click.confirm("Continue anyway?", default=False):
            click.echo("Setup aborted.")
            return False

    # Check database and pgvector extension
    database_url = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
    if pg_ok:
        click.echo("\nChecking database...")
        try:
            db_exists = asyncio.run(_check_database_exists(database_url))
            if db_exists:
                click.echo("  Database 'engram' exists")
            else:
                click.echo("  Database 'engram' not found — it may be created by migrations")
        except Exception:
            click.echo("  Could not verify database")

        try:
            pgvec = asyncio.run(_check_pgvector(database_url))
            if pgvec:
                click.echo("  pgvector extension installed")
            else:
                click.echo("  pgvector extension NOT found — run: CREATE EXTENSION vector;")
        except Exception:
            click.echo("  Could not check pgvector extension")

    return True


def _step2_llm_providers() -> tuple[str | None, str | None]:
    """Step 2: LLM Provider Setup. Returns (anthropic_key, openai_key)."""
    click.echo("\n Step 2: LLM Provider Setup\n")
    click.echo("Engram needs access to Claude (for analysis) and OpenAI (for embeddings).")

    anthropic_key = _prompt_llm_provider("Anthropic (Claude)", validate_anthropic_key)
    openai_key = _prompt_llm_provider("OpenAI", validate_openai_key)

    return anthropic_key, openai_key


def _step3_config(
    anthropic_key: str | None,
    openai_key: str | None,
) -> str:
    """Step 3: Generate encryption key and write .env. Returns the database_url."""
    click.echo("\n Step 3: Configuration\n")

    from engram.encryption import generate_key

    click.echo("Generating encryption key...")
    encryption_key = generate_key()

    env_path = Path.cwd() / ".env"
    if env_path.exists():
        if not click.confirm(".env already exists. Overwrite?", default=False):
            click.echo("Keeping existing .env file.")
            database_url = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
            return database_url

    database_url = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
    redis_url = "redis://localhost:6379/0"

    lines = [
        f"DATABASE_URL={database_url}",
        f"REDIS_URL={redis_url}",
        f"ANTHROPIC_API_KEY={anthropic_key or ''}",
        f"OPENAI_API_KEY={openai_key or ''}",
        f"ENGRAM_ENCRYPTION_KEY={encryption_key}",
        "CHUNK_SIZE_TOKENS=500",
        "CHUNK_OVERLAP_TOKENS=50",
        "MEMORY_DECAY_HALFLIFE_DAYS=365",
        "EMBEDDING_MODEL=text-embedding-ada-002",
        "EMBEDDING_DIMENSIONS=1536",
        "LLM_MODEL=claude-sonnet-4-20250514",
        "PHOTO_STORAGE_DIR=~/.engram/photos",
        "SERVER_HOST=0.0.0.0",
        "SERVER_PORT=8000",
        "MCP_TRANSPORT=stdio",
        "LOG_LEVEL=INFO",
    ]

    click.echo("Writing .env file...")
    env_path.write_text("\n".join(lines) + "\n")
    click.echo("  Configuration saved to .env")

    return database_url


def _step4_database() -> bool:
    """Step 4: Run Alembic migrations. Returns True on success."""
    click.echo("\n Step 4: Database Setup\n")
    click.echo("Running database migrations...")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        click.echo(f"  Migration failed:\n{result.stderr}")
        return False

    database_url = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
    try:
        ok = asyncio.run(_verify_tables(database_url))
        if ok:
            click.echo("  All tables created successfully")
        else:
            click.echo("  Warning: some expected tables were not found")
    except Exception as exc:
        click.echo(f"  Could not verify tables: {exc}")

    return True


def _step5_identity(database_url: str) -> None:
    """Step 5: Create identity profile."""
    click.echo("\n Step 5: Identity Profile\n")

    name = click.prompt("What's your name?")
    description = click.prompt("Description (optional)", default="", show_default=False)

    try:
        profile_id = asyncio.run(
            _create_identity_profile(database_url, name, description or None)
        )
        click.echo(f"\n  Identity profile created: {name} (id: {profile_id})")
    except Exception as exc:
        click.echo(f"\n  Failed to create identity profile: {exc}")


def _step6_token(database_url: str) -> None:
    """Step 6: Generate and store owner access token."""
    click.echo("\n Step 6: Access Token\n")
    click.echo("Generating your owner access token...\n")

    raw_token = "engram_" + secrets.token_urlsafe(32)

    try:
        asyncio.run(_create_access_token(database_url, raw_token))
    except Exception as exc:
        click.echo(f"  Failed to create access token: {exc}")
        return

    # Display token prominently
    border = "=" * 56
    click.echo(f"  {border}  ")
    click.echo("    Your owner token (save this -- shown only once!):   ")
    click.echo("                                                        ")
    click.echo(f"    {raw_token}")
    click.echo(f"  {border}  ")
    click.echo("")
    click.echo("  Token saved. Use this to authenticate API requests.")


def _step7_verify() -> None:
    """Step 7: Verification checks."""
    click.echo("\n Step 7: Verification\n")
    click.echo("Testing engram...")

    database_url = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
    try:
        ok = asyncio.run(_check_database_exists(database_url))
        if ok:
            click.echo("  Database connection works")
        else:
            click.echo("  Database connection failed")
    except Exception:
        click.echo("  Database connection check failed")

    click.echo("")
    click.echo("  Your engram is ready!\n")
    click.echo("Start the server:  engram server")
    click.echo("Start MCP server:  engram mcp")


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------

@cli.command()
def init():
    """Interactive setup wizard."""
    click.echo("\nWelcome to Engram Setup!\n")

    # Step 1: Infrastructure
    if not _step1_infrastructure():
        return

    # Step 2: LLM Providers
    anthropic_key, openai_key = _step2_llm_providers()

    # Step 3: Config
    database_url = _step3_config(anthropic_key, openai_key)

    # Reload settings so downstream code picks up .env
    os.environ.setdefault("DATABASE_URL", database_url)

    # Step 4: Database migration
    if not _step4_database():
        click.echo("Database setup failed. Please fix the issues above and try again.")
        return

    # Step 5: Identity profile
    _step5_identity(database_url)

    # Step 6: Access token
    _step6_token(database_url)

    # Step 7: Verify
    _step7_verify()
