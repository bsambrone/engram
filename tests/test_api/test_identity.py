"""Tests for identity REST API endpoints."""

from httpx import AsyncClient


async def test_get_profile(test_client: AsyncClient):
    """GET /api/identity/profile returns a profile."""
    resp = await test_client.get("/api/identity/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "name" in body


async def test_update_profile(test_client: AsyncClient):
    """PUT /api/identity/profile updates name/description."""
    # Ensure profile exists
    await test_client.get("/api/identity/profile")

    resp = await test_client.put(
        "/api/identity/profile",
        json={"name": "updated-name", "description": "updated desc"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "updated-name"
    assert body["description"] == "updated desc"


async def test_belief_crud(test_client: AsyncClient):
    """POST + GET + PUT + DELETE beliefs."""
    # Create
    resp = await test_client.post(
        "/api/identity/beliefs",
        json={"topic": "testing", "stance": "important", "confidence": 0.95},
    )
    assert resp.status_code == 201
    belief = resp.json()
    assert belief["topic"] == "testing"
    assert belief["source"] == "user"
    belief_id = belief["id"]

    # List
    resp = await test_client.get("/api/identity/beliefs")
    assert resp.status_code == 200
    beliefs = resp.json()
    assert any(b["id"] == belief_id for b in beliefs)
    # Owner should see source field
    assert "source" in beliefs[0]

    # List with topic filter
    resp = await test_client.get("/api/identity/beliefs?topic=testing")
    assert resp.status_code == 200
    filtered = resp.json()
    assert len(filtered) >= 1
    assert all(b["topic"] == "testing" for b in filtered)

    # Update
    resp = await test_client.put(
        f"/api/identity/beliefs/{belief_id}",
        json={"stance": "very important"},
    )
    assert resp.status_code == 200
    assert resp.json()["stance"] == "very important"
    assert resp.json()["source"] == "user"

    # Delete
    resp = await test_client.delete(f"/api/identity/beliefs/{belief_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


async def test_preference_crud(test_client: AsyncClient):
    """POST + GET preferences."""
    # Create
    resp = await test_client.post(
        "/api/identity/preferences",
        json={"category": "editor", "value": "vim", "strength": 0.9},
    )
    assert resp.status_code == 201
    pref = resp.json()
    assert pref["category"] == "editor"
    assert pref["source"] == "user"

    # List
    resp = await test_client.get("/api/identity/preferences")
    assert resp.status_code == 200
    prefs = resp.json()
    assert any(p["id"] == pref["id"] for p in prefs)


async def test_preference_update_delete(test_client: AsyncClient):
    """PUT + DELETE preferences."""
    # Create
    resp = await test_client.post(
        "/api/identity/preferences",
        json={"category": "os", "value": "linux"},
    )
    pref_id = resp.json()["id"]

    # Update
    resp = await test_client.put(
        f"/api/identity/preferences/{pref_id}",
        json={"value": "NixOS"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "NixOS"

    # Delete
    resp = await test_client.delete(f"/api/identity/preferences/{pref_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


async def test_style_upsert_and_get(test_client: AsyncClient):
    """PUT + GET style."""
    # Upsert
    resp = await test_client.put(
        "/api/identity/style",
        json={"tone": "casual", "humor_level": 0.6, "formality": 0.3},
    )
    assert resp.status_code == 200
    style = resp.json()
    assert style["tone"] == "casual"
    assert style["humor_level"] == 0.6
    assert style["source"] == "user"

    # Get
    resp = await test_client.get("/api/identity/style")
    assert resp.status_code == 200
    style = resp.json()
    assert style["tone"] == "casual"


async def test_snapshot_create_and_list(test_client: AsyncClient):
    """POST + GET snapshots."""
    # Create a belief first so snapshot has data
    await test_client.post(
        "/api/identity/beliefs",
        json={"topic": "snapshot-test", "stance": "exists"},
    )

    # Create snapshot
    resp = await test_client.post(
        "/api/identity/snapshot",
        json={"label": "test-snap"},
    )
    assert resp.status_code == 201
    snap = resp.json()
    assert snap["label"] == "test-snap"
    assert "snapshot_data" in snap
    snap_id = snap["id"]

    # List snapshots
    resp = await test_client.get("/api/identity/snapshots")
    assert resp.status_code == 200
    snaps = resp.json()
    assert any(s["id"] == snap_id for s in snaps)

    # Get specific snapshot
    resp = await test_client.get(f"/api/identity/snapshot/{snap_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == snap_id
    assert resp.json()["label"] == "test-snap"
