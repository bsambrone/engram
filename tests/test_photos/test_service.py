"""Tests for photo service — upload, analyze, imagine."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from engram.photos.service import PhotoService


async def test_upload_photo(db_session: AsyncSession):
    """upload_photo saves file and creates DB record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("engram.photos.service.settings") as mock_settings:
            mock_settings.photo_storage_dir = tmpdir
            mock_settings.openai_api_key = "test-key"

            service = PhotoService(db_session)
            result = await service.upload_photo(
                file_content=b"fake image content",
                filename="test_photo.jpg",
                source="upload",
                is_reference=False,
            )

        assert "id" in result
        assert "file_path" in result
        assert result["source"] == "upload"
        assert result["is_reference"] is False

        # Verify file was written
        assert os.path.exists(result["file_path"])
        with open(result["file_path"], "rb") as f:
            assert f.read() == b"fake image content"


async def test_upload_photo_creates_directory(db_session: AsyncSession):
    """upload_photo creates storage directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = os.path.join(tmpdir, "sub", "photos")
        with patch("engram.photos.service.settings") as mock_settings:
            mock_settings.photo_storage_dir = nested
            mock_settings.openai_api_key = "test-key"

            service = PhotoService(db_session)
            result = await service.upload_photo(
                file_content=b"data",
                filename="nested.png",
            )

        assert os.path.isdir(nested)
        assert os.path.exists(result["file_path"])


async def test_upload_photo_preserves_extension(db_session: AsyncSession):
    """upload_photo preserves the original file extension."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("engram.photos.service.settings") as mock_settings:
            mock_settings.photo_storage_dir = tmpdir
            mock_settings.openai_api_key = "test-key"

            service = PhotoService(db_session)
            result = await service.upload_photo(
                file_content=b"png data",
                filename="image.png",
            )

        assert result["file_path"].endswith(".png")


async def test_analyze_photo(db_session: AsyncSession):
    """analyze_photo calls OpenAI vision and updates photo record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("engram.photos.service.settings") as mock_settings:
            mock_settings.photo_storage_dir = tmpdir
            mock_settings.openai_api_key = "test-key"

            service = PhotoService(db_session)

            # First upload a photo
            result = await service.upload_photo(
                file_content=b"fake jpg data",
                filename="analyze_me.jpg",
            )
            photo_id = result["id"]

        # Mock the OpenAI client for vision analysis
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"description": "A sunny landscape",'
                        ' "tags": ["nature", "sun"], "people": []}'
                    )
                )
            )
        ]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("engram.photos.service.settings") as mock_settings,
            patch("engram.photos.service.AsyncOpenAI", return_value=mock_client),
        ):
            mock_settings.photo_storage_dir = tmpdir
            mock_settings.openai_api_key = "test-key"

            service = PhotoService(db_session)
            analysis = await service.analyze_photo(photo_id)

        assert analysis["description"] == "A sunny landscape"
        assert "nature" in analysis["tags"]
        assert "sun" in analysis["tags"]

        # Verify the DB record was updated
        from engram.photos.repository import PhotoRepository

        repo = PhotoRepository(db_session)
        photo = await repo.get_by_id(photo_id)
        assert photo is not None
        assert photo.description == "A sunny landscape"
        assert photo.tags == ["nature", "sun"]


async def test_imagine(db_session: AsyncSession):
    """imagine calls OpenAI image generation and saves result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the OpenAI client for image generation
        mock_image_data = MagicMock()
        mock_image_data.b64_json = "aW1hZ2VkYXRh"  # base64 of "imagedata"
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

            service = PhotoService(db_session)
            result = await service.imagine(
                scenario="A robot painting a sunset",
                style="watercolor",
            )

        assert "id" in result
        assert "file_path" in result
        assert result["scenario"] == "A robot painting a sunset"

        # Verify the file was saved
        assert os.path.exists(result["file_path"])

        # Verify OpenAI was called with correct params
        mock_client.images.generate.assert_called_once()
        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "gpt-image-1"
        assert "watercolor" in call_kwargs["prompt"]
        assert "robot painting a sunset" in call_kwargs["prompt"]


async def test_imagine_without_style(db_session: AsyncSession):
    """imagine works without a style parameter."""
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

            service = PhotoService(db_session)
            result = await service.imagine(scenario="A cat in space")

        assert result["scenario"] == "A cat in space"
        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert call_kwargs["prompt"] == "Generate image: A cat in space"
