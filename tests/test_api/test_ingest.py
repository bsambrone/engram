"""Tests for ingest API endpoints."""

import uuid

from httpx import AsyncClient


async def test_upload_file(test_client: AsyncClient):
    """POST /api/ingest/file returns 202 with a job_id."""
    resp = await test_client.post(
        "/api/ingest/file",
        files={"file": ("hello.txt", b"Hello, ingestion!", "text/plain")},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "id" in body
    assert body["source_type"] == "file"
    assert body["status"] == "pending"
    # Ensure job_id is a valid UUID
    uuid.UUID(body["id"])


async def test_get_job_status(test_client: AsyncClient):
    """GET /api/ingest/status?job_id= returns the job."""
    # First create a job
    resp = await test_client.post(
        "/api/ingest/file",
        files={"file": ("test.md", b"# Test", "text/plain")},
    )
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    # Then query status
    resp = await test_client.get(f"/api/ingest/status?job_id={job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == job_id
    assert body["status"] == "pending"


async def test_get_job_status_not_found(test_client: AsyncClient):
    """GET /api/ingest/status with invalid job_id returns 404."""
    fake_id = uuid.uuid4()
    resp = await test_client.get(f"/api/ingest/status?job_id={fake_id}")
    assert resp.status_code == 404


async def test_register_export(test_client: AsyncClient):
    """POST /api/ingest/export registers an export path."""
    resp = await test_client.post(
        "/api/ingest/export",
        json={"platform": "gmail", "export_path": "/data/gmail-export"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["platform"] == "gmail"
    assert body["export_path"] == "/data/gmail-export"
    assert body["status"] == "pending"
    uuid.UUID(body["id"])


async def test_list_exports(test_client: AsyncClient):
    """GET /api/ingest/exports returns registered exports."""
    # Register one
    await test_client.post(
        "/api/ingest/export",
        json={"platform": "reddit", "export_path": "/data/reddit-export"},
    )

    resp = await test_client.get("/api/ingest/exports")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    platforms = {e["platform"] for e in body}
    assert "reddit" in platforms
