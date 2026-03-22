"""Config API endpoints — owner-only."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from engram.api.deps import require_owner
from engram.config import settings
from engram.models.auth import AccessToken

router = APIRouter(prefix="/config", tags=["config"])

REDACTED_KEYS = {"anthropic_api_key", "openai_api_key"}

EXPOSED_KEYS = [
    "database_url",
    "redis_url",
    "chunk_size_tokens",
    "chunk_overlap_tokens",
    "memory_decay_halflife_days",
    "embedding_model",
    "embedding_dimensions",
    "generation_provider",
    "generation_model",
    "photo_storage_dir",
    "server_host",
    "server_port",
    "log_level",
]


class KeyUpdate(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


@router.get("")
async def get_config(
    _owner: AccessToken = Depends(require_owner),
) -> dict:
    """Return current settings with API keys redacted."""
    result: dict = {}
    for key in EXPOSED_KEYS:
        result[key] = getattr(settings, key)
    for key in REDACTED_KEYS:
        result[key] = "***"
    return result


@router.put("/keys")
async def update_keys(
    body: KeyUpdate,
    _owner: AccessToken = Depends(require_owner),
) -> dict:
    """Update runtime API key settings."""
    if body.anthropic_api_key is not None:
        settings.anthropic_api_key = body.anthropic_api_key
    if body.openai_api_key is not None:
        settings.openai_api_key = body.openai_api_key
    return {"status": "updated"}
