"""Tests for photo API routes."""

from __future__ import annotations

import io
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from engram.photos.repository import PhotoRepository


async def _create_test_photo(
    db_session: AsyncSession, **overrides
) -> uuid.UUID:
    """Helper to create a photo directly via repo for testing."""
    defaults = {
        "file_path": "/tmp/test-photo.jpg",
        "source": "upload",
        "is_reference": False,
    }
    defaults.update(overrides)
    repo = PhotoRepository(db_session)
    photo = await repo.create(**defaults)
    return photo.id


async def test_upload_photo(test_client: AsyncClient, db_session: AsyncSession):
    """POST /api/photos/upload saves file and returns photo data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("engram.photos.service.settings") as mock_settings:
            mock_settings.photo_storage_dir = tmpdir
            mock_settings.openai_api_key = "test-key"

            resp = await test_client.post(
                "/api/photos/upload",
                files={"file": ("test.jpg", io.BytesIO(b"fake image"), "image/jpeg")},
                params={"source": "test", "is_reference": "false"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["source"] == "test"
    assert body["is_reference"] is False


async def test_list_photos(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/photos returns a list of photos."""
    await _create_test_photo(db_session)
    await db_session.flush()

    resp = await test_client.get("/api/photos")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1


async def test_list_photos_filter_reference(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/photos?is_reference=true filters by reference flag."""
    await _create_test_photo(db_session, is_reference=True, file_path="/tmp/ref-photo.jpg")
    await _create_test_photo(db_session, is_reference=False, file_path="/tmp/nonref-photo.jpg")
    await db_session.flush()

    resp = await test_client.get("/api/photos?is_reference=true")
    assert resp.status_code == 200
    body = resp.json()
    assert all(p["is_reference"] for p in body)


async def test_get_photo_by_id(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/photos/{id} returns a single photo."""
    photo_id = await _create_test_photo(
        db_session, description="Detail test", tags=["tag1"]
    )
    await db_session.flush()

    resp = await test_client.get(f"/api/photos/{photo_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(photo_id)
    assert body["description"] == "Detail test"
    assert body["tags"] == ["tag1"]


async def test_get_photo_not_found(test_client: AsyncClient):
    """GET /api/photos/{id} returns 404 for unknown photo."""
    resp = await test_client.get(f"/api/photos/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_update_photo(test_client: AsyncClient, db_session: AsyncSession):
    """PUT /api/photos/{id} updates metadata."""
    photo_id = await _create_test_photo(db_session, is_reference=False)
    await db_session.flush()

    resp = await test_client.put(
        f"/api/photos/{photo_id}",
        json={"is_reference": True, "description": "Now a reference"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_reference"] is True
    assert body["description"] == "Now a reference"


async def test_update_photo_not_found(test_client: AsyncClient):
    """PUT /api/photos/{id} returns 404 for unknown photo."""
    resp = await test_client.put(
        f"/api/photos/{uuid.uuid4()}",
        json={"description": "nope"},
    )
    assert resp.status_code == 404


async def test_delete_photo(test_client: AsyncClient, db_session: AsyncSession):
    """DELETE /api/photos/{id} removes the photo record."""
    photo_id = await _create_test_photo(db_session)
    await db_session.flush()

    resp = await test_client.delete(f"/api/photos/{photo_id}")
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Photo deleted"

    # Verify it's gone
    resp2 = await test_client.get(f"/api/photos/{photo_id}")
    assert resp2.status_code == 404


async def test_delete_photo_not_found(test_client: AsyncClient):
    """DELETE /api/photos/{id} returns 404 for unknown photo."""
    resp = await test_client.delete(f"/api/photos/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_imagine(test_client: AsyncClient):
    """POST /api/engram/imagine generates an image from scenario."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_image_data = MagicMock()
        mock_image_data.b64_json = "aW1hZ2VkYXRh"
        mock_image_data.url = None

        mock_response = MagicMock()
        mock_response.data = [mock_image_data]

        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(return_value=mock_response)

        with (
            patch("engram.photos.service.settings") as mock_settings,
            patch("engram.photos.service.AsyncOpenAI", return_value=mock_client),
        ):
            mock_settings.photo_storage_dir = tmpdir
            mock_settings.openai_api_key = "test-key"

            resp = await test_client.post(
                "/api/engram/imagine",
                json={"scenario": "A robot painting a sunset", "style": "oil painting"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["scenario"] == "A robot painting a sunset"


async def test_imagine_requires_scenario(test_client: AsyncClient):
    """POST /api/engram/imagine returns 422 without scenario."""
    resp = await test_client.post("/api/engram/imagine", json={})
    assert resp.status_code == 422
