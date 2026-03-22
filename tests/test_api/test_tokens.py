"""Tests for auth system and tokens CRUD API."""

import hashlib
import uuid

from httpx import ASGITransport, AsyncClient

from engram.models.auth import AccessToken


async def test_create_owner_token(test_client: AsyncClient):
    """POST /api/tokens with access_level=owner returns 201 with raw token."""
    resp = await test_client.post(
        "/api/tokens",
        json={"name": "my-owner-token", "access_level": "owner"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "token" in body
    assert body["name"] == "my-owner-token"
    assert body["access_level"] == "owner"
    assert body["id"] is not None
    # Raw token should be a non-empty string
    assert len(body["token"]) > 0


async def test_create_shared_token(test_client: AsyncClient):
    """POST /api/tokens with access_level=shared returns 201."""
    resp = await test_client.post(
        "/api/tokens",
        json={"name": "my-shared-token", "access_level": "shared"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_level"] == "shared"
    assert body["name"] == "my-shared-token"
    assert "token" in body


async def test_list_tokens(test_client: AsyncClient):
    """GET /api/tokens returns active tokens without token_hash."""
    # Create a token first
    await test_client.post(
        "/api/tokens",
        json={"name": "list-test-token", "access_level": "shared"},
    )

    resp = await test_client.get("/api/tokens")
    assert resp.status_code == 200
    tokens = resp.json()
    assert isinstance(tokens, list)
    assert len(tokens) >= 1
    # No token should expose the hash
    for t in tokens:
        assert "token_hash" not in t
        assert "token" not in t
        assert "id" in t
        assert "name" in t
        assert "access_level" in t


async def test_revoke_token(test_client: AsyncClient):
    """DELETE /api/tokens/{id} sets revoked_at (soft delete)."""
    # Create a token
    create_resp = await test_client.post(
        "/api/tokens",
        json={"name": "to-revoke", "access_level": "shared"},
    )
    token_id = create_resp.json()["id"]

    # Revoke it
    resp = await test_client.delete(f"/api/tokens/{token_id}")
    assert resp.status_code == 200
    assert resp.json()["revoked_at"] is not None

    # It should no longer appear in the list
    list_resp = await test_client.get("/api/tokens")
    ids = [t["id"] for t in list_resp.json()]
    assert token_id not in ids


async def test_unauthenticated_request(db_session):
    """Request without Authorization header returns 401."""
    from engram.db import get_session
    from engram.main import app

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tokens")
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_shared_token_cannot_manage_tokens(db_session):
    """A shared-level token cannot access owner-only token endpoints (403)."""
    from engram.db import get_session
    from engram.main import app

    # Create a shared token directly in the DB
    raw_token = "shared-test-" + uuid.uuid4().hex[:16]
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    shared_token = AccessToken(
        name="shared-for-test",
        token_hash=token_hash,
        access_level="shared",
    )
    db_session.add(shared_token)
    await db_session.flush()

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {raw_token}"},
        ) as client:
            # Shared token should get 403 on POST /api/tokens
            resp = await client.post(
                "/api/tokens",
                json={"name": "sneaky", "access_level": "owner"},
            )
            assert resp.status_code == 403

            # Shared token should get 403 on GET /api/tokens
            resp = await client.get("/api/tokens")
            assert resp.status_code == 403

            # Shared token should get 403 on DELETE /api/tokens/{id}
            resp = await client.delete(f"/api/tokens/{shared_token.id}")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
