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
        client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=5,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True, "Claude API key works!"
    except Exception as exc:
        return False, f"Anthropic validation failed: {exc}"


def validate_openai_key(api_key: str) -> tuple[bool, str]:
    """Validate an OpenAI API key by creating a test embedding.

    Returns (success, message).
    """
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        client.embeddings.create(input=["test"], model="text-embedding-3-small")
        return True, "OpenAI API key works!"
    except Exception as exc:
        return False, f"OpenAI validation failed: {exc}"


def fetch_openai_models(api_key: str) -> tuple[list[str], list[str]]:
    """Fetch available generation and embedding models from the OpenAI API.

    Filters out deprecated, non-chat, and specialty models.
    Returns (generation_models, embedding_models) sorted alphabetically.
    """
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        all_models = [m.id for m in client.models.list()]

        # Exclude specialty/non-chat model types
        skip_keywords = (
            "realtime", "audio", "tts", "transcribe", "search",
            "diarize", "instruct", "dall-e", "gpt-image", "chatgpt-image",
            "whisper", "davinci", "babbage", "curie",
        )

        # Deprecated models
        deprecated = {
            "gpt-3.5-turbo", "gpt-3.5-turbo-0125", "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo-16k", "gpt-3.5-turbo-instruct",
            "gpt-3.5-turbo-instruct-0914",
            "gpt-4-0125-preview", "gpt-4-0613", "gpt-4-1106-preview",
            "gpt-4-turbo-preview",
            "gpt-4o-2024-05-13",
        }

        # Also skip: date-stamped variants (e.g. gpt-4.1-2025-04-14),
        # -chat-latest, -codex, -codex-max, -codex-mini aliases
        skip_suffixes = ("-chat-latest", "-codex", "-codex-max", "-codex-mini")

        import re
        date_pattern = re.compile(r"-\d{4}-\d{2}-\d{2}$")

        def _is_chat_model(name: str) -> bool:
            return (
                name.startswith(("gpt-", "o1", "o3", "o4"))
                and not any(kw in name for kw in skip_keywords)
                and name not in deprecated
                and not any(name.endswith(s) for s in skip_suffixes)
                and not date_pattern.search(name)
            )

        generation = sorted(m for m in all_models if _is_chat_model(m))

        # Embedding models
        embedding = sorted(m for m in all_models if "embedding" in m)

        return generation, embedding
    except Exception:
        return [], []


def validate_openai_generation(api_key: str, model: str) -> tuple[bool, str]:
    """Validate that an OpenAI model works for chat generation.

    Returns (success, message).
    """
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return True, f"{model} works!"
    except Exception as exc:
        return False, f"OpenAI generation validation failed: {exc}"


def validate_anthropic_generation(api_key: str, model: str) -> tuple[bool, str]:
    """Validate that an Anthropic model works for generation.

    Returns (success, message).
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model=model,
            max_tokens=5,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True, f"{model} works!"
    except Exception as exc:
        return False, f"Anthropic generation validation failed: {exc}"


def validate_openai_embedding(api_key: str, model: str) -> tuple[bool, str]:
    """Validate that an OpenAI embedding model works.

    Returns (success, message).
    """
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        client.embeddings.create(input=["test"], model=model)
        return True, f"{model} works!"
    except Exception as exc:
        return False, f"OpenAI embedding validation failed: {exc}"


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


async def _list_pending_exports(database_url: str) -> list[dict]:
    """Return a list of dicts for all registered DataExport rows."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from engram.models.connector import DataExport

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await session.execute(select(DataExport))
            rows = result.scalars().all()
            return [
                {
                    "platform": r.platform,
                    "export_path": r.export_path,
                    "status": r.status,
                }
                for r in rows
            ]
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
    from engram.mcp.server import main as mcp_main

    asyncio.run(mcp_main())


@cli.command()
def ingest():
    """Run data ingestion from configured exports."""
    click.echo("Processing registered data exports...")

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/engram",
    )

    try:
        exports = asyncio.run(_list_pending_exports(database_url))
    except Exception as exc:
        click.echo(f"Error querying exports: {exc}")
        return

    if not exports:
        click.echo("No pending data exports found. Use 'engram init' to configure data sources.")
        return

    for exp in exports:
        click.echo(f"  [{exp['platform']}] {exp['export_path']} (status: {exp['status']})")

    click.echo(f"\n{len(exports)} export(s) registered.")


@cli.command()
def status():
    """Show engram statistics."""
    click.echo("Status not yet implemented. Coming in a later task.")


# ---------------------------------------------------------------------------
# Init wizard helpers (one function per step, called sequentially)
# ---------------------------------------------------------------------------

def _prompt_api_key(
    provider_name: str,
    validate_fn,
) -> str | None:
    """Prompt the user for an API key and validate it.

    Returns the validated API key, or None if the user gives up.
    """
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


# Preferred models shown at the top when available (order matters)
PREFERRED_GENERATION = ["gpt-5.2", "gpt-4.1", "gpt-4o", "gpt-4o-mini", "o3", "o3-mini", "o4-mini"]
PREFERRED_EMBEDDING = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]


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


def _step2_llm_providers() -> dict:
    """Step 2: LLM Provider Setup.

    Returns a dict with keys:
        openai_key, anthropic_key, generation_provider, generation_model, embedding_model
    """
    click.echo("\n Step 2: LLM Provider Setup\n")
    click.echo(
        "Engram needs an OpenAI API key for embeddings (required) "
        "and a generation model for analysis."
    )

    # --- OpenAI API Key ---
    click.echo("\n--- OpenAI API Key ---")
    openai_key = _prompt_api_key("OpenAI", validate_openai_key)
    if not openai_key:
        click.echo("OpenAI API key is required.")
        return {
            "openai_key": None,
            "anthropic_key": None,
            "generation_provider": "openai",
            "generation_model": "gpt-4.1",
            "embedding_model": "text-embedding-3-small",
        }

    # Fetch available models from the API
    click.echo("\nFetching available models from OpenAI...")
    gen_models, emb_models = fetch_openai_models(openai_key)

    # --- Generation Model ---
    if gen_models:
        # Show preferred models first, then the rest
        ordered = [m for m in PREFERRED_GENERATION if m in gen_models]
        remaining = [m for m in gen_models if m not in ordered]
        display_models = ordered + remaining

        click.echo(f"\nAvailable generation models ({len(display_models)}):")
        for i, name in enumerate(display_models, 1):
            label = " (recommended)" if i == 1 else ""
            click.echo(f"  [{i}] {name}{label}")
        other_idx = len(display_models) + 1
        click.echo(f"  [{other_idx}] Other (enter model name)")

        valid_choices = [str(i) for i in range(1, other_idx + 1)]
        choice = click.prompt("Choice", default="1", type=click.Choice(valid_choices))
        choice_int = int(choice)

        if choice_int <= len(display_models):
            generation_model = display_models[choice_int - 1]
        else:
            generation_model = click.prompt("Enter model name")
    else:
        click.echo("\nCould not fetch models. Enter a model name manually.")
        generation_model = click.prompt("Generation model", default="gpt-5.2")

    click.echo(f"Validating {generation_model}... ", nl=False)
    ok, msg = validate_openai_generation(openai_key, generation_model)
    if ok:
        click.echo(f"  {msg}")
    else:
        click.echo(f"  {msg}")
        click.echo("Continuing with selected model anyway.")

    # --- Embedding Model ---
    if emb_models:
        ordered_emb = [m for m in PREFERRED_EMBEDDING if m in emb_models]
        remaining_emb = [m for m in emb_models if m not in ordered_emb]
        display_emb = ordered_emb + remaining_emb

        click.echo(f"\nAvailable embedding models ({len(display_emb)} found):")
        for i, name in enumerate(display_emb, 1):
            label = " (recommended)" if i == 1 else ""
            click.echo(f"  [{i}] {name}{label}")

        valid_choices = [str(i) for i in range(1, len(display_emb) + 1)]
        choice = click.prompt("Choice", default="1", type=click.Choice(valid_choices))
        embedding_model = display_emb[int(choice) - 1]
    else:
        click.echo("\nCould not fetch embedding models. Enter a model name manually.")
        embedding_model = click.prompt("Embedding model", default="text-embedding-3-small")

    click.echo(f"Validating {embedding_model}... ", nl=False)
    ok, msg = validate_openai_embedding(openai_key, embedding_model)
    if ok:
        click.echo(f"  {msg}")
    else:
        click.echo(f"  {msg}")
        click.echo("Continuing with selected model anyway.")

    return {
        "openai_key": openai_key,
        "anthropic_key": None,
        "generation_provider": "openai",
        "generation_model": generation_model,
        "embedding_model": embedding_model,
    }


def _step3_config(
    llm_config: dict,
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
        f"OPENAI_API_KEY={llm_config.get('openai_key') or ''}",
        f"ANTHROPIC_API_KEY={llm_config.get('anthropic_key') or ''}",
        f"ENGRAM_ENCRYPTION_KEY={encryption_key}",
        f"GENERATION_PROVIDER={llm_config.get('generation_provider', 'openai')}",
        f"GENERATION_MODEL={llm_config.get('generation_model', 'gpt-4.1')}",
        "CHUNK_SIZE_TOKENS=500",
        "CHUNK_OVERLAP_TOKENS=50",
        "MEMORY_DECAY_HALFLIFE_DAYS=365",
        f"EMBEDDING_MODEL={llm_config.get('embedding_model', 'text-embedding-3-small')}",
        "EMBEDDING_DIMENSIONS=1536",
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


def _step4_data_sources(database_url: str) -> int:
    """Step 4: Data Export Setup. Returns the number of sources configured."""
    click.echo("\n Step 4: Data Sources\n")

    platforms = {
        "1": {
            "name": "Gmail",
            "label": "Gmail (Google Takeout)",
            "parser_cls": "GmailExportParser",
            "parser_module": "engram.ingestion.parsers.gmail",
            "platform_key": "gmail",
            "instructions": (
                "To export your Gmail data:\n"
                "  1. Go to https://takeout.google.com\n"
                "  2. Deselect all, then select only \"Mail\"\n"
                "  3. Choose .mbox format\n"
                "  4. Click \"Create export\" and wait for email\n"
                "  5. Download and extract the ZIP archive"
            ),
            "success_hint": "MBOX files detected",
        },
        "2": {
            "name": "Reddit",
            "label": "Reddit (Data Request)",
            "parser_cls": "RedditExportParser",
            "parser_module": "engram.ingestion.parsers.reddit",
            "platform_key": "reddit",
            "instructions": (
                "To export your Reddit data:\n"
                "  1. Go to https://www.reddit.com/settings/data-request\n"
                "  2. Click \"Request data\"\n"
                "  3. Wait for the email (can take up to 30 days)\n"
                "  4. Download and extract the archive"
            ),
            "success_hint": "posts.json detected",
        },
        "3": {
            "name": "Facebook",
            "label": "Facebook (Download Your Information)",
            "parser_cls": "FacebookExportParser",
            "parser_module": "engram.ingestion.parsers.facebook",
            "platform_key": "facebook",
            "instructions": (
                "To export your Facebook data:\n"
                "  1. Go to Facebook Settings > Your Information > Download Your Information\n"
                "  2. Select format: JSON\n"
                "  3. Select data to include (Posts, Comments, Messages recommended)\n"
                "  4. Click \"Request Download\" and wait for notification\n"
                "  5. Download and extract the archive"
            ),
            "success_hint": "posts/comments/messages directories detected",
        },
        "4": {
            "name": "Instagram",
            "label": "Instagram (Download Your Data)",
            "parser_cls": "InstagramExportParser",
            "parser_module": "engram.ingestion.parsers.instagram",
            "platform_key": "instagram",
            "instructions": (
                "To export your Instagram data:\n"
                "  1. Go to Instagram Settings > Privacy and Security > Download Your Data\n"
                "  2. Select format: JSON\n"
                "  3. Click \"Request Download\" and wait for email\n"
                "  4. Download and extract the archive"
            ),
            "success_hint": "content/messages directories detected",
        },
    }

    click.echo("Which platforms do you have data to import?")
    for key, info in platforms.items():
        click.echo(f"  [{key}] {info['label']}")
    click.echo("  [5] Skip for now")
    click.echo("")

    raw = click.prompt("Select platforms (comma-separated, e.g. 1,2,3)", default="5")
    selections = [s.strip() for s in raw.split(",")]

    if "5" in selections or not any(s in platforms for s in selections):
        click.echo("\nSkipping data source setup.")
        return 0

    configured = 0
    for sel in selections:
        if sel not in platforms:
            continue
        info = platforms[sel]
        click.echo(f"\n--- {info['name']} ---")
        click.echo(info["instructions"])
        click.echo("")

        export_path_str = click.prompt(
            f"Enter path to your {info['name']} export (or press Enter to skip)",
            default="",
            show_default=False,
        )
        if not export_path_str:
            click.echo(f"Skipping {info['name']}.")
            continue

        export_path = Path(export_path_str).expanduser().resolve()

        # Dynamically import and instantiate the parser
        import importlib

        mod = importlib.import_module(info["parser_module"])
        parser = getattr(mod, info["parser_cls"])()

        click.echo("Validating... ", nl=False)
        if parser.validate(export_path):
            click.echo(
                f"Found valid {info['name']} export ({info['success_hint']})"
            )
            # Register the export in the database
            try:
                asyncio.run(
                    _register_data_export(
                        database_url, info["platform_key"], str(export_path)
                    )
                )
                configured += 1
            except Exception as exc:
                click.echo(f"  Warning: could not register export: {exc}")
                click.echo("  You can register it later with 'engram ingest'.")
        else:
            click.echo(
                f"Could not validate {info['name']} export at {export_path}"
            )
            if click.confirm("Register anyway?", default=False):
                try:
                    asyncio.run(
                        _register_data_export(
                            database_url, info["platform_key"], str(export_path)
                        )
                    )
                    configured += 1
                except Exception as exc:
                    click.echo(f"  Warning: could not register export: {exc}")

    click.echo(f"\n{configured} data source(s) configured")
    return configured


async def _register_data_export(
    database_url: str, platform: str, export_path: str
) -> None:
    """Create a DataExport row for a validated export directory."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from engram.models.connector import DataExport

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            export = DataExport(
                platform=platform, export_path=export_path, status="pending"
            )
            session.add(export)
            await session.commit()
    finally:
        await engine.dispose()


def _step5_database() -> bool:
    """Step 5: Run Alembic migrations. Returns True on success."""
    click.echo("\n Step 5: Database Setup\n")
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


def _step6_identity(database_url: str) -> None:
    """Step 6: Create identity profile."""
    click.echo("\n Step 6: Identity Profile\n")

    name = click.prompt("What's your name?")
    description = click.prompt("Description (optional)", default="", show_default=False)

    try:
        profile_id = asyncio.run(
            _create_identity_profile(database_url, name, description or None)
        )
        click.echo(f"\n  Identity profile created: {name} (id: {profile_id})")
    except Exception as exc:
        click.echo(f"\n  Failed to create identity profile: {exc}")


def _step7_token(database_url: str) -> None:
    """Step 7: Generate and store owner access token."""
    click.echo("\n Step 7: Access Token\n")
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


def _step8_verify() -> None:
    """Step 8: Verification checks."""
    click.echo("\n Step 8: Verification\n")
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
    llm_config = _step2_llm_providers()

    # Step 3: Config
    database_url = _step3_config(llm_config)

    # Reload settings so downstream code picks up .env
    os.environ.setdefault("DATABASE_URL", database_url)

    # Step 4: Data Sources
    _step4_data_sources(database_url)

    # Step 5: Database migration
    if not _step5_database():
        click.echo("Database setup failed. Please fix the issues above and try again.")
        return

    # Step 6: Identity profile
    _step6_identity(database_url)

    # Step 7: Access token
    _step7_token(database_url)

    # Step 8: Verify
    _step8_verify()
