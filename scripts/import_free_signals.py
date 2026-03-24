"""Import free identity signals from Instagram and Reddit exports.

These require NO LLM calls (except the profile photo vision analysis) —
just direct database inserts for topics, preferences, people, and one photo.
"""

import asyncio
import csv
import json
import re
import uuid
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from engram.config import settings
from engram.identity.repository import IdentityRepository
from engram.memory.repository import MemoryRepository
from engram.photos.service import PhotoService

DATABASE_URL = settings.database_url

# Data paths
REDDIT_SUBREDDITS = Path("/home/bsambrone/engram-data/reddit/subscribed_subreddits.csv")
REDDIT_SAVED_POSTS = Path("/home/bsambrone/engram-data/reddit/saved_posts.csv")
IG_INTERESTS = Path(
    "/home/bsambrone/engram-data/instagram/your_instagram_activity/ai/interest_categories.json"
)
IG_LOCATIONS = Path(
    "/home/bsambrone/engram-data/instagram/personal_information/information_about_you/locations_of_interest.json"
)
IG_CLOSE_FRIENDS = Path(
    "/home/bsambrone/engram-data/instagram/connections/followers_and_following/close_friends.json"
)
IG_CONTACTS = Path(
    "/home/bsambrone/engram-data/instagram/connections/contacts/synced_contacts.json"
)
IG_PROFILE_PHOTO = Path(
    "/home/bsambrone/engram-data/instagram/media/profile/202105/18219345889058161.jpg"
)


async def get_profile_id(session: AsyncSession) -> uuid.UUID:
    """Get the single identity profile ID."""
    result = await session.execute(text("SELECT id FROM identity_profiles LIMIT 1"))
    row = result.fetchone()
    if row is None:
        raise RuntimeError("No identity profile found")
    return row[0]


async def import_reddit_subreddits(session: AsyncSession) -> dict:
    """Import subscribed subreddits as topics."""
    from engram.models.memory import Topic

    repo = MemoryRepository(session)
    new_count = 0
    existing_count = 0

    with open(REDDIT_SUBREDDITS, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["subreddit"].strip()
            if not name:
                continue
            result = await session.execute(select(Topic).where(Topic.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                existing_count += 1
            else:
                new_count += 1
            await repo.get_or_create_topic(name)

    await session.commit()
    total = new_count + existing_count
    return {"total": total, "new": new_count, "existing": existing_count}


async def import_reddit_saved_posts(session: AsyncSession) -> dict:
    """Extract subreddit names from saved post permalinks and import as topics."""
    from engram.models.memory import Topic

    repo = MemoryRepository(session)
    new_count = 0
    existing_count = 0
    subreddit_pattern = re.compile(r"/r/([^/]+)/")

    with open(REDDIT_SAVED_POSTS, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            permalink = row.get("permalink", "")
            match = subreddit_pattern.search(permalink)
            if not match:
                continue
            name = match.group(1)

            result = await session.execute(select(Topic).where(Topic.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                existing_count += 1
            else:
                new_count += 1
            await repo.get_or_create_topic(name)

    await session.commit()
    total = new_count + existing_count
    return {"total": total, "new": new_count, "existing": existing_count}


async def import_instagram_interests(
    session: AsyncSession, profile_id: uuid.UUID
) -> dict:
    """Import Instagram interest categories as preferences."""
    repo = IdentityRepository(session)
    count = 0

    with open(IG_INTERESTS) as f:
        data = json.load(f)

    for item in data:
        label_values = item.get("label_values", [])
        for lv in label_values:
            if lv.get("label") == "Interest":
                value = lv.get("value", "").strip()
                if not value:
                    continue
                await repo.create_preference(
                    profile_id=profile_id,
                    category="instagram_interest",
                    value=value,
                    strength=0.7,
                    source="inferred",
                )
                count += 1

    await session.commit()
    return {"count": count}


async def import_instagram_locations(
    session: AsyncSession, profile_id: uuid.UUID
) -> dict:
    """Import Instagram locations of interest as preferences."""
    repo = IdentityRepository(session)
    count = 0

    with open(IG_LOCATIONS) as f:
        data = json.load(f)

    label_values = data.get("label_values", [])
    for lv in label_values:
        if lv.get("label") == "Locations of interest":
            locations = lv.get("vec", [])
            for loc in locations:
                value = loc.get("value", "").strip()
                if not value:
                    continue
                await repo.create_preference(
                    profile_id=profile_id,
                    category="location_of_interest",
                    value=value,
                    strength=0.8,
                    source="inferred",
                )
                count += 1

    await session.commit()
    return {"count": count}


async def import_instagram_close_friends(session: AsyncSession) -> dict:
    """Import Instagram close friends as people."""
    from engram.models.memory import Person

    repo = MemoryRepository(session)
    new_count = 0
    existing_count = 0

    with open(IG_CLOSE_FRIENDS) as f:
        data = json.load(f)

    friends = data.get("relationships_close_friends", [])
    for friend_entry in friends:
        string_list = friend_entry.get("string_list_data", [])
        for item in string_list:
            name = item.get("value", "").strip()
            if not name:
                continue

            result = await session.execute(select(Person).where(Person.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                existing_count += 1
            else:
                new_count += 1
            await repo.get_or_create_person(name, relationship_type="close_friend")

    await session.commit()
    total = new_count + existing_count
    return {"total": total, "new": new_count, "existing": existing_count}


async def import_instagram_contacts(session: AsyncSession) -> dict:
    """Import Instagram synced contacts as people."""
    from engram.models.memory import Person

    repo = MemoryRepository(session)
    new_count = 0
    existing_count = 0

    with open(IG_CONTACTS) as f:
        data = json.load(f)

    contacts = data.get("contacts_contact_info", [])
    for contact in contacts:
        string_map = contact.get("string_map_data", {})
        first_name = string_map.get("First Name", {}).get("value", "").strip()
        last_name = string_map.get("Last Name", {}).get("value", "").strip()

        if not first_name and not last_name:
            continue

        name = f"{first_name} {last_name}".strip()

        result = await session.execute(select(Person).where(Person.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            existing_count += 1
        else:
            new_count += 1
        await repo.get_or_create_person(name, relationship_type="contact")

    await session.commit()
    total = new_count + existing_count
    return {"total": total, "new": new_count, "existing": existing_count}


async def import_profile_photo(
    session: AsyncSession, profile_id: uuid.UUID
) -> dict:
    """Upload the Instagram profile photo as a reference image and analyze it."""
    photo_service = PhotoService(session)

    file_content = IG_PROFILE_PHOTO.read_bytes()
    photo_result = await photo_service.upload_photo(
        file_content=file_content,
        filename=IG_PROFILE_PHOTO.name,
        profile_id=profile_id,
        source="instagram",
        is_reference=True,
    )

    photo_id = uuid.UUID(photo_result["id"])

    # Run vision analysis (this IS the one LLM call)
    analysis = await photo_service.analyze_photo(photo_id)

    await session.commit()

    return {
        "photo_id": str(photo_id),
        "file_path": photo_result["file_path"],
        "description": analysis.get("description", ""),
        "tags": analysis.get("tags", []),
    }


async def main():
    engine = create_async_engine(DATABASE_URL, pool_size=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("\n" + "=" * 60)
    print("  Importing Free Identity Signals")
    print("=" * 60)

    # Get profile ID
    async with factory() as session:
        profile_id = await get_profile_id(session)
    print(f"\n  Profile ID: {profile_id}")

    # 1. Reddit subscribed subreddits
    print("\n=== Reddit Subreddits ===")
    async with factory() as session:
        result = await import_reddit_subreddits(session)
    print(
        f"  Imported {result['total']} subreddits as topics "
        f"({result['new']} new, {result['existing']} already existed)"
    )

    # 2. Reddit saved posts (subreddit extraction)
    print("\n=== Reddit Saved Posts (subreddits) ===")
    async with factory() as session:
        result = await import_reddit_saved_posts(session)
    print(
        f"  Imported {result['total']} subreddits from saved posts "
        f"({result['new']} new, {result['existing']} already existed)"
    )

    # 3. Instagram interest categories
    print("\n=== Instagram Interest Categories ===")
    async with factory() as session:
        profile_id = await get_profile_id(session)
        result = await import_instagram_interests(session, profile_id)
    print(f"  Imported {result['count']} interest preferences")

    # 4. Instagram locations of interest
    print("\n=== Instagram Locations ===")
    async with factory() as session:
        profile_id = await get_profile_id(session)
        result = await import_instagram_locations(session, profile_id)
    print(f"  Imported {result['count']} location preferences")

    # 5. Instagram close friends
    print("\n=== Instagram Close Friends ===")
    async with factory() as session:
        result = await import_instagram_close_friends(session)
    print(
        f"  Imported {result['total']} close friends "
        f"({result['new']} new, {result['existing']} already existed)"
    )

    # 6. Instagram synced contacts
    print("\n=== Instagram Synced Contacts ===")
    async with factory() as session:
        result = await import_instagram_contacts(session)
    print(
        f"  Imported {result['total']} contacts "
        f"({result['new']} new, {result['existing']} already existed)"
    )

    # 7. Instagram profile photo
    print("\n=== Instagram Profile Photo ===")
    async with factory() as session:
        profile_id = await get_profile_id(session)
        result = await import_profile_photo(session, profile_id)
    print(f"  Uploaded as reference photo: {result['photo_id']}")
    print(f"  Description: {result['description']}")
    print(f"  Tags: {result['tags']}")

    # Summary
    print("\n" + "=" * 60)
    print("  Import Complete!")
    print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
