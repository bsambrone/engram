"""Tests for config API endpoints."""

from httpx import AsyncClient


async def test_get_config(test_client: AsyncClient):
    """GET /api/config returns 200 with config values and redacted keys."""
    resp = await test_client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()

    # Redacted keys should show "***"
    assert body["anthropic_api_key"] == "***"
    assert body["openai_api_key"] == "***"

    # Non-secret config values should be present
    assert "database_url" in body
    assert "redis_url" in body
    assert "chunk_size_tokens" in body
    assert "chunk_overlap_tokens" in body
    assert "memory_decay_halflife_days" in body
    assert "embedding_model" in body
    assert "embedding_dimensions" in body
    assert "generation_provider" in body
    assert "generation_model" in body
    assert "photo_storage_dir" in body
    assert "server_host" in body
    assert "server_port" in body
    assert "log_level" in body

    # Verify actual values from defaults
    assert isinstance(body["chunk_size_tokens"], int)
    assert isinstance(body["server_port"], int)


async def test_update_api_keys(test_client: AsyncClient):
    """PUT /api/config/keys updates runtime API keys and returns status."""
    resp = await test_client.put(
        "/api/config/keys",
        json={
            "anthropic_api_key": "sk-ant-new-key",
            "openai_api_key": "sk-openai-new-key",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "updated"}
