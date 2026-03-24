"""Photo service — upload, vision analysis, and image generation."""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from engram.config import settings
from engram.memory.repository import MemoryRepository
from engram.photos.repository import PhotoRepository


class PhotoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PhotoRepository(session)

    def _get_storage_dir(self) -> Path:
        """Return the photo storage directory, creating it if necessary."""
        storage_dir = Path(os.path.expanduser(settings.photo_storage_dir))
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    async def upload_photo(
        self,
        file_content: bytes,
        filename: str,
        profile_id: uuid.UUID | None = None,
        source: str | None = None,
        is_reference: bool = False,
    ) -> dict:
        """Save file to storage and create a DB record."""
        storage_dir = self._get_storage_dir()

        # Determine extension from original filename
        ext = Path(filename).suffix or ".jpg"
        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = storage_dir / unique_name

        file_path.write_bytes(file_content)

        photo = await self.repo.create(
            file_path=str(file_path),
            source=source,
            profile_id=profile_id,
            is_reference=is_reference,
        )

        return {
            "id": str(photo.id),
            "file_path": photo.file_path,
            "source": photo.source,
            "is_reference": photo.is_reference,
        }

    async def analyze_photo(self, photo_id: uuid.UUID) -> dict:
        """Use OpenAI vision to generate description and tags for a photo."""
        photo = await self.repo.get_by_id(photo_id)
        if photo is None:
            raise ValueError(f"Photo {photo_id} not found")

        # Read file and encode as base64
        file_path = Path(photo.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Photo file not found: {photo.file_path}")

        image_data = file_path.read_bytes()
        base64_image = base64.b64encode(image_data).decode("utf-8")

        # Determine MIME type from extension
        ext = file_path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
        mime_type = mime_map.get(ext, "image/jpeg")

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze personal photos to extract identity signals. "
                        "Go beyond literal description — infer what this photo reveals about "
                        "the person's interests, relationships, lifestyle, and values. "
                        "Return valid JSON only, no markdown fences."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this personal photo. Return JSON:\n"
                                "{\n"
                                '  "description": "What is literally in the photo",\n'
                                '  "intent": "Why this photo was likely taken/shared (e.g. showing off cooking, documenting a trip, capturing a moment with friends)",\n'
                                '  "meaning": "What this reveals about the person — their interests, skills, values, lifestyle",\n'
                                '  "people": [{"name": "unknown", "description": "short physical/contextual description", "relationship_guess": "friend/family/colleague/self/unknown"}],\n'
                                '  "tags": ["tag1", "tag2"],\n'
                                '  "topics": ["broader topic this relates to"],\n'
                                '  "importance_score": 0.0-1.0\n'
                                "}"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                },
            ],
        )

        content = response.choices[0].message.content or "{}"
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            analysis = json.loads(content)
        except json.JSONDecodeError:
            analysis = {"description": content, "tags": [], "people": []}

        # Update photo with analysis results
        await self.repo.update(
            photo_id,
            description=analysis.get("description"),
            tags=analysis.get("tags", []),
        )

        # Link people found in the photo
        people_data = analysis.get("people", [])
        if people_data:
            memory_repo = MemoryRepository(self.session)
            for person_data in people_data:
                name = person_data.get("name", "unknown")
                if name.lower() in ("unknown", "unidentified", ""):
                    name = person_data.get("description", "unknown person")[:100]
                relationship = person_data.get("relationship_guess")
                person = await memory_repo.get_or_create_person(
                    name=name, relationship_type=relationship
                )
                # Link person to photo via photo_people
                from engram.models.photo import PhotoPerson
                from sqlalchemy import select
                existing = await self.session.execute(
                    select(PhotoPerson).where(
                        PhotoPerson.photo_id == photo_id,
                        PhotoPerson.person_id == person.id,
                    )
                )
                if not existing.scalar_one_or_none():
                    self.session.add(PhotoPerson(photo_id=photo_id, person_id=person.id))

            await self.session.flush()

        return analysis

    async def imagine(self, scenario: str, style: str | None = None) -> dict:
        """Use OpenAI image generation to create an image from a scenario."""
        prompt = f"Generate image: {scenario}"
        if style:
            prompt = f"Generate image in {style} style: {scenario}"

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1024",
        )

        image_data = response.data[0]

        # Save generated image to storage
        storage_dir = self._get_storage_dir()
        unique_name = f"{uuid.uuid4()}.png"
        file_path = storage_dir / unique_name

        # gpt-image-1 returns b64_json by default
        if image_data.b64_json:
            img_bytes = base64.b64decode(image_data.b64_json)
            file_path.write_bytes(img_bytes)
        elif image_data.url:
            # If URL is returned instead, store the URL reference
            file_path.write_text(image_data.url)

        # Create DB record for the generated image
        photo = await self.repo.create(
            file_path=str(file_path),
            source="generated",
            source_ref=scenario[:500],
            description=scenario,
            tags=["generated", "imagined"],
        )

        return {
            "id": str(photo.id),
            "file_path": str(file_path),
            "scenario": scenario,
        }
