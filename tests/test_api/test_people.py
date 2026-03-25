"""Tests for people API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from engram.models.memory import Memory, MemoryPerson, MemoryTopic, Person, Topic
from engram.models.photo import Photo, PhotoPerson
from engram.models.social import Relationship


# ---- Helpers -----------------------------------------------------------------


async def _create_person(
    session: AsyncSession,
    name: str = "Alice",
    relationship_type: str | None = "friend",
) -> Person:
    person = Person(name=name, relationship_type=relationship_type)
    session.add(person)
    await session.flush()
    await session.refresh(person)
    return person


async def _create_relationship(
    session: AsyncSession,
    person_id: uuid.UUID,
    platform: str = "discord",
    message_count: int = 10,
    interaction_score: float = 0.5,
    connected_since: datetime | None = None,
) -> Relationship:
    rel = Relationship(
        person_id=person_id,
        platform=platform,
        message_count=message_count,
        interaction_score=interaction_score,
        connected_since=connected_since,
    )
    session.add(rel)
    await session.flush()
    await session.refresh(rel)
    return rel


async def _create_memory(
    session: AsyncSession,
    content: str = "Test memory",
    source: str = "test",
) -> Memory:
    memory = Memory(content=content, source=source, timestamp=datetime.now())
    session.add(memory)
    await session.flush()
    await session.refresh(memory)
    return memory


async def _link_memory_person(
    session: AsyncSession,
    memory_id: uuid.UUID,
    person_id: uuid.UUID,
) -> None:
    session.add(MemoryPerson(memory_id=memory_id, person_id=person_id))
    await session.flush()


async def _create_topic(session: AsyncSession, name: str) -> Topic:
    topic = Topic(name=name)
    session.add(topic)
    await session.flush()
    await session.refresh(topic)
    return topic


async def _link_memory_topic(
    session: AsyncSession,
    memory_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> None:
    session.add(MemoryTopic(memory_id=memory_id, topic_id=topic_id))
    await session.flush()


# ---- Tests: List People ------------------------------------------------------


async def test_list_people_empty(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/people returns empty list when no people exist."""
    resp = await test_client.get("/api/people")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


async def test_list_people_with_data(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/people returns people with aggregated relationship data."""
    person = await _create_person(db_session, name="Bob", relationship_type="colleague")
    await _create_relationship(
        db_session,
        person.id,
        platform="slack",
        message_count=50,
        interaction_score=0.8,
    )
    await _create_relationship(
        db_session,
        person.id,
        platform="email",
        message_count=20,
        interaction_score=0.3,
    )

    resp = await test_client.get("/api/people")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1

    bob = next((p for p in body if p["name"] == "Bob"), None)
    assert bob is not None
    assert bob["relationship_type"] == "colleague"
    assert set(bob["platforms"]) == {"slack", "email"}
    # sum of message counts
    assert bob["message_count"] == 70
    # max interaction score
    assert bob["interaction_score"] == 0.8


async def test_list_people_search(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/people?q=ali returns matching people."""
    await _create_person(db_session, name="Alice Smith")
    await _create_person(db_session, name="Charlie")

    resp = await test_client.get("/api/people?q=ali")
    assert resp.status_code == 200
    body = resp.json()
    names = [p["name"] for p in body]
    assert "Alice Smith" in names
    assert "Charlie" not in names


async def test_list_people_sort_by_interaction(
    test_client: AsyncClient, db_session: AsyncSession
):
    """GET /api/people?sort=interaction sorts by max interaction_score desc."""
    p1 = await _create_person(db_session, name="HighScore")
    p2 = await _create_person(db_session, name="LowScore")
    await _create_relationship(db_session, p1.id, interaction_score=0.9)
    await _create_relationship(db_session, p2.id, interaction_score=0.1)

    resp = await test_client.get("/api/people?sort=interaction")
    assert resp.status_code == 200
    body = resp.json()
    # Find both in the results
    high_idx = next(i for i, p in enumerate(body) if p["name"] == "HighScore")
    low_idx = next(i for i, p in enumerate(body) if p["name"] == "LowScore")
    assert high_idx < low_idx


# ---- Tests: Get Person Detail ------------------------------------------------


async def test_get_person_detail(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/people/{id} returns person with relationships and memory count."""
    person = await _create_person(db_session, name="DetailPerson")
    await _create_relationship(
        db_session, person.id, platform="telegram", message_count=5
    )

    # Create memory linked to this person
    memory = await _create_memory(db_session, content="Talked about AI")
    await _link_memory_person(db_session, memory.id, person.id)

    # Create topic linked to that memory
    topic = await _create_topic(db_session, "artificial-intelligence")
    await _link_memory_topic(db_session, memory.id, topic.id)

    resp = await test_client.get(f"/api/people/{person.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "DetailPerson"
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["platform"] == "telegram"
    assert body["memory_count"] == 1
    assert len(body["top_topics"]) == 1
    assert body["top_topics"][0]["name"] == "artificial-intelligence"
    assert body["top_topics"][0]["count"] == 1


async def test_get_person_not_found(test_client: AsyncClient):
    """GET /api/people/{id} returns 404 for unknown person."""
    resp = await test_client.get(f"/api/people/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---- Tests: Update Person ----------------------------------------------------


async def test_update_person(test_client: AsyncClient, db_session: AsyncSession):
    """PUT /api/people/{id} updates name and relationship_type."""
    person = await _create_person(db_session, name="OldName", relationship_type="acquaintance")

    resp = await test_client.put(
        f"/api/people/{person.id}",
        json={"name": "NewName", "relationship_type": "friend"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "NewName"
    assert body["relationship_type"] == "friend"


async def test_update_person_not_found(test_client: AsyncClient):
    """PUT /api/people/{id} returns 404 for unknown person."""
    resp = await test_client.put(
        f"/api/people/{uuid.uuid4()}",
        json={"name": "Nope"},
    )
    assert resp.status_code == 404


async def test_update_person_no_fields(test_client: AsyncClient, db_session: AsyncSession):
    """PUT /api/people/{id} returns 400 when no fields provided."""
    person = await _create_person(db_session, name="NoChange")

    resp = await test_client.put(f"/api/people/{person.id}", json={})
    assert resp.status_code == 400


# ---- Tests: Person Memories --------------------------------------------------


async def test_get_person_memories(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/people/{id}/memories returns memories linked to person."""
    person = await _create_person(db_session, name="MemPerson")
    m1 = await _create_memory(db_session, content="Memory one for MemPerson")
    m2 = await _create_memory(db_session, content="Memory two for MemPerson")
    await _link_memory_person(db_session, m1.id, person.id)
    await _link_memory_person(db_session, m2.id, person.id)

    resp = await test_client.get(f"/api/people/{person.id}/memories")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    contents = {m["content"] for m in body}
    assert "Memory one for MemPerson" in contents
    assert "Memory two for MemPerson" in contents


async def test_get_person_memories_not_found(test_client: AsyncClient):
    """GET /api/people/{id}/memories returns 404 for unknown person."""
    resp = await test_client.get(f"/api/people/{uuid.uuid4()}/memories")
    assert resp.status_code == 404


async def test_get_person_memories_pagination(
    test_client: AsyncClient, db_session: AsyncSession
):
    """GET /api/people/{id}/memories respects limit and offset."""
    person = await _create_person(db_session, name="PaginPerson")
    for i in range(5):
        m = await _create_memory(db_session, content=f"PaginPerson memory {i}")
        await _link_memory_person(db_session, m.id, person.id)

    resp = await test_client.get(f"/api/people/{person.id}/memories?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp2 = await test_client.get(f"/api/people/{person.id}/memories?limit=2&offset=3")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 2


# ---- Tests: Graph Endpoint ---------------------------------------------------


async def test_graph_format(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/people/graph returns correct graph structure."""
    person = await _create_person(db_session, name="GraphPerson")
    await _create_relationship(
        db_session, person.id, platform="github", interaction_score=0.7
    )

    resp = await test_client.get("/api/people/graph")
    assert resp.status_code == 200
    body = resp.json()

    assert "nodes" in body
    assert "edges" in body

    # Should have the "self" center node
    node_ids = [n["id"] for n in body["nodes"]]
    assert "self" in node_ids

    # Should have the person as a node
    person_node = next(
        (n for n in body["nodes"] if n["name"] == "GraphPerson"), None
    )
    assert person_node is not None
    assert person_node["score"] == 0.7
    assert person_node["platform"] == "github"

    # Should have an edge from self to person
    edge = next(
        (e for e in body["edges"] if e["target"] == str(person.id)), None
    )
    assert edge is not None
    assert edge["source"] == "self"
    assert edge["weight"] == 0.7


async def test_graph_excludes_zero_score(
    test_client: AsyncClient, db_session: AsyncSession
):
    """GET /api/people/graph excludes people with interaction_score = 0."""
    person = await _create_person(db_session, name="ZeroScorePerson")
    await _create_relationship(
        db_session, person.id, platform="email", interaction_score=0.0
    )

    resp = await test_client.get("/api/people/graph")
    assert resp.status_code == 200
    body = resp.json()

    person_node = next(
        (n for n in body["nodes"] if n["name"] == "ZeroScorePerson"), None
    )
    assert person_node is None


# ---- Tests: Photos with person_id filter ------------------------------------


async def test_list_photos_by_person(test_client: AsyncClient, db_session: AsyncSession):
    """GET /api/photos?person_id=... filters photos by person."""
    person = await _create_person(db_session, name="PhotoPerson")

    # Create a photo linked to the person
    photo = Photo(file_path="/tmp/person-photo.jpg", source="test")
    db_session.add(photo)
    await db_session.flush()
    await db_session.refresh(photo)

    db_session.add(PhotoPerson(photo_id=photo.id, person_id=person.id))
    await db_session.flush()

    # Create another photo NOT linked to the person
    other_photo = Photo(file_path="/tmp/other-photo.jpg", source="test")
    db_session.add(other_photo)
    await db_session.flush()

    resp = await test_client.get(f"/api/photos?person_id={person.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert all(p["file_path"] == "/tmp/person-photo.jpg" for p in body)
