"""Tests for enhanced ingest API endpoints (jobs list + export validation)."""

import uuid

from httpx import AsyncClient


# -- GET /api/ingest/jobs --------------------------------------------------


async def test_list_jobs_empty(test_client: AsyncClient):
    """GET /api/ingest/jobs returns an empty list when no jobs exist."""
    resp = await test_client.get("/api/ingest/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


async def test_list_jobs_with_data(test_client: AsyncClient):
    """GET /api/ingest/jobs returns jobs after creating some."""
    # Create a job via file upload
    resp = await test_client.post(
        "/api/ingest/file",
        files={"file": ("test.txt", b"test content", "text/plain")},
    )
    assert resp.status_code == 202
    created_id = resp.json()["id"]

    resp = await test_client.get("/api/ingest/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1

    # The job we created should appear
    ids = [j["id"] for j in body]
    assert created_id in ids

    # Check shape of returned job objects
    job = next(j for j in body if j["id"] == created_id)
    assert job["source_type"] == "file"
    assert job["status"] == "pending"
    assert "items_processed" in job
    assert "items_failed" in job
    assert "created_at" in job


async def test_list_jobs_status_filter(test_client: AsyncClient):
    """GET /api/ingest/jobs?status=pending filters correctly."""
    # Create a job
    resp = await test_client.post(
        "/api/ingest/file",
        files={"file": ("filter.txt", b"filter test", "text/plain")},
    )
    assert resp.status_code == 202

    # Filter by pending
    resp = await test_client.get("/api/ingest/jobs?status=pending")
    assert resp.status_code == 200
    body = resp.json()
    assert all(j["status"] == "pending" for j in body)

    # Filter by a status that shouldn't match anything
    resp = await test_client.get("/api/ingest/jobs?status=completed")
    assert resp.status_code == 200
    body = resp.json()
    # All returned jobs (if any) should have status=completed
    assert all(j["status"] == "completed" for j in body)


async def test_list_jobs_limit(test_client: AsyncClient):
    """GET /api/ingest/jobs?limit=1 respects the limit parameter."""
    # Create two jobs
    await test_client.post(
        "/api/ingest/file",
        files={"file": ("a.txt", b"a", "text/plain")},
    )
    await test_client.post(
        "/api/ingest/file",
        files={"file": ("b.txt", b"b", "text/plain")},
    )

    resp = await test_client.get("/api/ingest/jobs?limit=1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1


# -- POST /api/ingest/export/validate --------------------------------------


async def test_validate_export_unknown_platform(test_client: AsyncClient):
    """POST /api/ingest/export/validate returns valid=False for unknown platform."""
    resp = await test_client.post(
        "/api/ingest/export/validate",
        json={"platform": "myspace", "export_path": "/some/path"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert "Unknown platform" in body["error"]


async def test_validate_export_invalid_path(test_client: AsyncClient):
    """POST /api/ingest/export/validate returns valid=False for nonexistent path."""
    fake_path = f"/tmp/nonexistent-{uuid.uuid4().hex}"
    resp = await test_client.post(
        "/api/ingest/export/validate",
        json={"platform": "gmail", "export_path": fake_path},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["platform"] == "gmail"
    assert body["export_path"] == fake_path


async def test_validate_export_valid_gmail(test_client: AsyncClient, tmp_path):
    """POST /api/ingest/export/validate returns valid=True for valid Gmail export."""
    # Create a minimal valid Gmail export structure
    mbox_file = tmp_path / "All mail Including Spam and Trash.mbox"
    mbox_file.write_bytes(b"")

    resp = await test_client.post(
        "/api/ingest/export/validate",
        json={"platform": "gmail", "export_path": str(tmp_path)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["platform"] == "gmail"


async def test_validate_export_valid_reddit(test_client: AsyncClient, tmp_path):
    """POST /api/ingest/export/validate returns valid=True for valid Reddit export."""
    # Reddit parser expects posts.csv or comments.csv in the directory
    (tmp_path / "posts.csv").write_text("id,permalink,date,title,body,url\n")

    resp = await test_client.post(
        "/api/ingest/export/validate",
        json={"platform": "reddit", "export_path": str(tmp_path)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["platform"] == "reddit"
