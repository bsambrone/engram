"""Import free identity signals from Facebook exports.

These require NO LLM calls — just direct database inserts for people,
relationships, life events, preferences, and topics.
"""

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from engram.config import settings
from engram.identity.repository import IdentityRepository
from engram.memory.repository import MemoryRepository
from engram.models.memory import Person, Topic
from engram.models.social import LifeEvent, Relationship

DATABASE_URL = settings.database_url

# Facebook export root
FB_ROOT = Path("/home/bsambrone/engram-data/facebook")

# Data paths
FB_FRIENDS = FB_ROOT / "connections" / "friends" / "your_friends.json"
FB_EVENTS = FB_ROOT / "your_facebook_activity" / "events" / "your_event_responses.json"
FB_INTERESTS = FB_ROOT / "your_facebook_activity" / "ai" / "interest_categories.json"
FB_PAGES = (
    FB_ROOT
    / "your_facebook_activity"
    / "pages"
    / "pages_and_profiles_you_follow.json"
)
FB_GROUPS = (
    FB_ROOT
    / "your_facebook_activity"
    / "groups"
    / "your_group_membership_activity.json"
)
FB_MESSAGES_DIR = FB_ROOT / "your_facebook_activity" / "messages"

USER_DISPLAY_NAME = "Bill Sambrone"


def _fix_encoding(text: str) -> str:
    """Fix Facebook's UTF-8-as-latin-1 encoding quirk."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


async def get_profile_id(session: AsyncSession) -> uuid.UUID:
    """Get the single identity profile ID."""
    result = await session.execute(text("SELECT id FROM identity_profiles LIMIT 1"))
    row = result.fetchone()
    if row is None:
        raise RuntimeError("No identity profile found")
    return row[0]


# ------------------------------------------------------------------
# 1. Friends -> People + Relationships
# ------------------------------------------------------------------


async def import_friends(session: AsyncSession) -> dict:
    """Import Facebook friends as People + Relationship records."""
    repo = MemoryRepository(session)
    new_people = 0
    existing_people = 0
    relationships_created = 0

    with open(FB_FRIENDS, encoding="utf-8") as f:
        data = json.load(f)

    friends = data.get("friends_v2", [])
    for friend in friends:
        name = _fix_encoding(friend.get("name", "")).strip()
        if not name:
            continue
        ts = friend.get("timestamp")
        connected_since = (
            datetime.fromtimestamp(ts, tz=UTC).replace(tzinfo=None) if ts else None
        )

        # Check if person already exists
        result = await session.execute(select(Person).where(Person.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            existing_people += 1
        else:
            new_people += 1

        person = await repo.get_or_create_person(name, relationship_type="friend")

        # Create Relationship record (skip if already exists for this platform)
        result = await session.execute(
            select(Relationship).where(
                Relationship.person_id == person.id,
                Relationship.platform == "facebook",
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(
                Relationship(
                    person_id=person.id,
                    platform="facebook",
                    relationship_type="friend",
                    connected_since=connected_since,
                )
            )
            relationships_created += 1

    await session.commit()
    total = new_people + existing_people
    return {
        "total_friends": total,
        "new_people": new_people,
        "existing_people": existing_people,
        "relationships_created": relationships_created,
    }


# ------------------------------------------------------------------
# 2. Events -> LifeEvents
# ------------------------------------------------------------------


async def import_events(session: AsyncSession) -> dict:
    """Import Facebook event responses as LifeEvent records."""
    count = 0

    with open(FB_EVENTS, encoding="utf-8") as f:
        data = json.load(f)

    responses = data.get("event_responses_v2", {})
    # responses is a dict with keys: events_joined, events_declined, events_interested
    for response_type, events in responses.items():
        if not isinstance(events, list):
            continue
        for event in events:
            name = _fix_encoding(event.get("name", "")).strip()
            if not name:
                continue
            ts = event.get("start_timestamp")
            event_date = (
                datetime.fromtimestamp(ts, tz=UTC).replace(tzinfo=None) if ts else None
            )

            # Check if already exists
            result = await session.execute(
                select(LifeEvent).where(
                    LifeEvent.title == name,
                    LifeEvent.source == "facebook",
                )
            )
            if result.scalar_one_or_none() is not None:
                continue

            session.add(
                LifeEvent(
                    title=name,
                    event_date=event_date,
                    source="facebook",
                    source_ref=f"facebook-event-{response_type}",
                    event_type="social",
                    description=f"Response: {response_type.replace('events_', '')}",
                )
            )
            count += 1

    await session.commit()
    return {"count": count}


# ------------------------------------------------------------------
# 3. AI Interest Categories -> Preferences
# ------------------------------------------------------------------


async def import_interests(
    session: AsyncSession, profile_id: uuid.UUID
) -> dict:
    """Import Facebook AI interest categories as preferences."""
    repo = IdentityRepository(session)
    count = 0

    with open(FB_INTERESTS, encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        label_values = item.get("label_values", [])
        for lv in label_values:
            if lv.get("label") == "Interest":
                value = _fix_encoding(lv.get("value", "")).strip()
                if not value:
                    continue
                await repo.create_preference(
                    profile_id=profile_id,
                    category="facebook_interest",
                    value=value,
                    strength=0.7,
                    source="inferred",
                )
                count += 1

    await session.commit()
    return {"count": count}


# ------------------------------------------------------------------
# 4. Pages followed -> Topics
# ------------------------------------------------------------------


async def import_pages(session: AsyncSession) -> dict:
    """Import followed Facebook pages as topics."""
    repo = MemoryRepository(session)
    new_count = 0
    existing_count = 0

    with open(FB_PAGES, encoding="utf-8") as f:
        data = json.load(f)

    pages = data.get("pages_followed_v2", [])
    for page in pages:
        name = _fix_encoding(page.get("title", "")).strip()
        if not name:
            # Try data[0].name
            page_data = page.get("data", [])
            if page_data and isinstance(page_data, list):
                name = _fix_encoding(page_data[0].get("name", "")).strip()
        if not name:
            continue

        result = await session.execute(select(Topic).where(Topic.name == name))
        if result.scalar_one_or_none():
            existing_count += 1
        else:
            new_count += 1
        await repo.get_or_create_topic(name)

    await session.commit()
    total = new_count + existing_count
    return {"total": total, "new": new_count, "existing": existing_count}


# ------------------------------------------------------------------
# 5. Groups -> Topics
# ------------------------------------------------------------------


async def import_groups(session: AsyncSession) -> dict:
    """Import Facebook group memberships as topics."""
    repo = MemoryRepository(session)
    new_count = 0
    existing_count = 0

    with open(FB_GROUPS, encoding="utf-8") as f:
        data = json.load(f)

    groups = data.get("groups_joined_v2", [])
    for group in groups:
        # Extract group name from data[0].name or title
        group_data = group.get("data", [])
        name = ""
        if group_data and isinstance(group_data, list):
            name = _fix_encoding(group_data[0].get("name", "")).strip()
        if not name:
            # Fall back to title, but strip boilerplate
            title = _fix_encoding(group.get("title", "")).strip()
            # Title looks like "You became a member of CVMC Dads."
            match = re.search(r"member of (.+?)\.?$", title)
            if match:
                name = match.group(1).strip()
        if not name:
            continue

        result = await session.execute(select(Topic).where(Topic.name == name))
        if result.scalar_one_or_none():
            existing_count += 1
        else:
            new_count += 1
        await repo.get_or_create_topic(name)

    await session.commit()
    total = new_count + existing_count
    return {"total": total, "new": new_count, "existing": existing_count}


# ------------------------------------------------------------------
# 6. Message conversation partners -> People + Relationships
# ------------------------------------------------------------------


async def import_message_partners(session: AsyncSession) -> dict:
    """Scan message files to create People and Relationship records."""
    repo = MemoryRepository(session)
    new_people = 0
    existing_people = 0
    relationships_created = 0

    # Collect partner message counts
    partner_counts: dict[str, int] = {}

    for subfolder in ("inbox", "message_requests"):
        folder = FB_MESSAGES_DIR / subfolder
        if not folder.is_dir():
            continue
        for convo_dir in sorted(folder.iterdir()):
            if not convo_dir.is_dir():
                continue
            for json_file in sorted(convo_dir.glob("message_*.json")):
                try:
                    with open(json_file, encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue

                participants = data.get("participants", [])
                messages = data.get("messages", [])
                if not isinstance(participants, list) or not isinstance(messages, list):
                    continue

                # Find non-user participants
                partner_names = []
                for p in participants:
                    name = _fix_encoding(str(p.get("name", "") or "")).strip()
                    if name and name != USER_DISPLAY_NAME:
                        partner_names.append(name)

                # Count messages per partner in this conversation
                msg_count = len(messages)
                for name in partner_names:
                    partner_counts[name] = partner_counts.get(name, 0) + msg_count

    # Create People and Relationships
    for name, msg_count in partner_counts.items():
        if not name:
            continue

        result = await session.execute(select(Person).where(Person.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            existing_people += 1
        else:
            new_people += 1

        person = await repo.get_or_create_person(name)

        # Create or update Relationship
        result = await session.execute(
            select(Relationship).where(
                Relationship.person_id == person.id,
                Relationship.platform == "facebook",
            )
        )
        rel = result.scalar_one_or_none()
        if rel is None:
            session.add(
                Relationship(
                    person_id=person.id,
                    platform="facebook",
                    relationship_type="message_contact",
                    message_count=msg_count,
                )
            )
            relationships_created += 1
        else:
            # Update message count if higher
            if msg_count > rel.message_count:
                rel.message_count = msg_count

    await session.commit()
    total = new_people + existing_people
    return {
        "total_partners": total,
        "new_people": new_people,
        "existing_people": existing_people,
        "relationships_created": relationships_created,
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


async def main():
    engine = create_async_engine(DATABASE_URL, pool_size=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("\n" + "=" * 60)
    print("  Importing Facebook Free Signals")
    print("=" * 60)

    # Get profile ID
    async with factory() as session:
        profile_id = await get_profile_id(session)
    print(f"\n  Profile ID: {profile_id}")

    # 1. Friends
    print("\n=== Facebook Friends ===")
    async with factory() as session:
        result = await import_friends(session)
    print(
        f"  Friends: {result['total_friends']} "
        f"({result['new_people']} new people, "
        f"{result['existing_people']} existing, "
        f"{result['relationships_created']} relationships created)"
    )

    # 2. Events
    print("\n=== Facebook Events ===")
    async with factory() as session:
        result = await import_events(session)
    print(f"  Life events created: {result['count']}")

    # 3. AI Interest Categories
    print("\n=== Facebook AI Interest Categories ===")
    async with factory() as session:
        profile_id = await get_profile_id(session)
        result = await import_interests(session, profile_id)
    print(f"  Interest preferences created: {result['count']}")

    # 4. Pages followed
    print("\n=== Facebook Pages Followed ===")
    async with factory() as session:
        result = await import_pages(session)
    print(
        f"  Topics from pages: {result['total']} "
        f"({result['new']} new, {result['existing']} existing)"
    )

    # 5. Groups
    print("\n=== Facebook Groups ===")
    async with factory() as session:
        result = await import_groups(session)
    print(
        f"  Topics from groups: {result['total']} "
        f"({result['new']} new, {result['existing']} existing)"
    )

    # 6. Message conversation partners
    print("\n=== Facebook Message Partners ===")
    async with factory() as session:
        result = await import_message_partners(session)
    print(
        f"  Message partners: {result['total_partners']} "
        f"({result['new_people']} new people, "
        f"{result['existing_people']} existing, "
        f"{result['relationships_created']} relationships created)"
    )

    # Summary
    print("\n" + "=" * 60)
    print("  Facebook Import Complete!")
    print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
