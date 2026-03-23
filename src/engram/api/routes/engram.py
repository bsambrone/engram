"""Engram API routes — ask, topics, opinions, summarize, simulate, compare, export, import."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engram.api.deps import get_current_token, require_owner
from engram.db import get_session
from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService
from engram.llm.providers import generate
from engram.llm.rag import ask_engram
from engram.memory.repository import MemoryRepository
from engram.models.auth import AccessToken
from engram.models.memory import Memory, MemoryTopic, Topic
from engram.photos.repository import PhotoRepository

router = APIRouter(prefix="/engram", tags=["engram"])


# ---- Pydantic schemas -------------------------------------------------------


class AskRequest(BaseModel):
    query: str
    as_of_date: str | None = None


class AskResponse(BaseModel):
    answer: str
    confidence: float
    memory_refs: list[str] | None = None
    belief_refs: list[str] | None = None
    caveats: list[str] = []


class TopicCount(BaseModel):
    name: str
    memory_count: int


class OpinionOut(BaseModel):
    id: uuid.UUID
    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class OpinionSharedOut(BaseModel):
    """Opinion output for shared tokens — no source or id."""

    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None

    model_config = {"from_attributes": True}


class SummarizeResponse(BaseModel):
    summary: str


class SimulateRequest(BaseModel):
    scenario: str


class SimulateResponse(BaseModel):
    decision: str


class CompareRequest(BaseModel):
    topic: str
    stance: str


class CompareResponse(BaseModel):
    analysis: str


class ImagineRequest(BaseModel):
    scenario: str
    style: str | None = None


class ImagineResponse(BaseModel):
    id: str
    file_path: str
    scenario: str


class ExplainBeliefResponse(BaseModel):
    belief_id: str
    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None
    source: str | None = None
    supporting_memory_ids: list[str]


# ---- Export / Import schemas ------------------------------------------------


class ExportPersonIn(BaseModel):
    name: str
    relationship_type: str | None = None


class ExportMemoryIn(BaseModel):
    content: str
    intent: str | None = None
    meaning: str | None = None
    timestamp: str | None = None
    source: str | None = None
    source_ref: str | None = None
    authorship: str | None = None
    importance_score: float | None = None
    confidence: float | None = None
    reinforcement_count: int = 0
    status: str = "active"
    visibility: str = "active"
    topics: list[str] = []
    people: list[ExportPersonIn] = []


class ExportBeliefIn(BaseModel):
    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None
    source: str | None = None


class ExportPreferenceIn(BaseModel):
    category: str
    value: str | None = None
    strength: float | None = None
    source: str | None = None


class ExportStyleIn(BaseModel):
    tone: str | None = None
    humor_level: float | None = None
    verbosity: float | None = None
    formality: float | None = None
    vocabulary_notes: str | None = None
    communication_patterns: str | None = None
    source: str | None = None


class ExportPhotoIn(BaseModel):
    description: str | None = None
    tags: list[str] | None = None
    is_reference: bool = False


class ImportPayload(BaseModel):
    version: str = "1.0"
    exported_at: str | None = None
    profile: dict[str, Any] | None = None
    memories: list[ExportMemoryIn] = []
    beliefs: list[ExportBeliefIn] = []
    preferences: list[ExportPreferenceIn] = []
    style_profile: ExportStyleIn | None = None
    photos: list[ExportPhotoIn] = []


class ImportSummary(BaseModel):
    memories_imported: int = 0
    beliefs_imported: int = 0
    preferences_imported: int = 0
    style_imported: bool = False
    topics_linked: int = 0
    people_linked: int = 0


# ---- Helpers -----------------------------------------------------------------


async def _get_profile_id(session: AsyncSession) -> uuid.UUID:
    """Get or create the default profile and return its ID."""
    service = IdentityService(session)
    profile = await service.get_or_create_default_profile()
    return profile.id


# ---- Routes ------------------------------------------------------------------


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    token: AccessToken = Depends(get_current_token),
):
    """Ask the engram a question. Owner gets citations, shared doesn't."""
    is_owner = token.access_level == "owner"
    parsed_date = None
    if body.as_of_date:
        try:
            parsed_date = datetime.fromisoformat(body.as_of_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid as_of_date format. Use ISO 8601.")
    result = await ask_engram(session, body.query, is_owner=is_owner, as_of_date=parsed_date)
    return AskResponse(
        answer=result.answer,
        confidence=result.confidence,
        memory_refs=result.memory_refs,
        belief_refs=result.belief_refs,
        caveats=result.caveats,
    )


@router.get("/topics", response_model=list[TopicCount])
async def list_topics(
    session: AsyncSession = Depends(get_session),
    _token: AccessToken = Depends(get_current_token),
):
    """List topics with memory counts."""
    result = await session.execute(
        select(Topic.name, func.count(MemoryTopic.memory_id))
        .join(MemoryTopic, Topic.id == MemoryTopic.topic_id)
        .join(Memory, Memory.id == MemoryTopic.memory_id)
        .where(Memory.status == "active")
        .group_by(Topic.name)
        .order_by(func.count(MemoryTopic.memory_id).desc())
    )
    rows = result.all()
    return [TopicCount(name=name, memory_count=count) for name, count in rows]


@router.get("/opinions")
async def get_opinions(
    topic: str = Query(...),
    session: AsyncSession = Depends(get_session),
    token: AccessToken = Depends(get_current_token),
):
    """Get beliefs/opinions on a topic. Shared: no source or id fields."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    beliefs = await repo.list_beliefs(profile_id, topic=topic)

    if token.access_level == "owner":
        return [OpinionOut.model_validate(b).model_dump() for b in beliefs]
    return [OpinionSharedOut.model_validate(b).model_dump() for b in beliefs]


@router.get("/summarize", response_model=SummarizeResponse)
async def summarize(
    session: AsyncSession = Depends(get_session),
    _token: AccessToken = Depends(get_current_token),
):
    """Generate a 'who am I?' narrative summary using LLM."""
    identity_svc = IdentityService(session)
    profile = await identity_svc.get_or_create_default_profile()
    identity = await identity_svc.get_full_identity(profile.id)

    parts = [f"Name: {profile.name}"]

    if identity["beliefs"]:
        parts.append("Beliefs:")
        for b in identity["beliefs"]:
            parts.append(f"  - {b['topic']}: {b.get('stance', 'no stance')}")

    if identity["preferences"]:
        parts.append("Preferences:")
        for p in identity["preferences"]:
            parts.append(f"  - {p['category']}: {p.get('value', 'unknown')}")

    if identity["style"]:
        s = identity["style"]
        parts.append(f"Communication style: tone={s.get('tone')}, formality={s.get('formality')}")

    identity_text = "\n".join(parts)

    system = (
        "You are summarizing a person's identity into a short, first-person narrative. "
        "Write 2-4 sentences capturing who they are based on the data provided."
    )
    user = (
        "Create a first-person narrative summary based on this identity data:"
        f"\n\n{identity_text}"
    )

    summary = await generate(system=system, user=user)
    return SummarizeResponse(summary=summary)


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(
    body: SimulateRequest,
    session: AsyncSession = Depends(get_session),
    _token: AccessToken = Depends(get_current_token),
):
    """Simulate how this person would decide in a given scenario."""
    identity_svc = IdentityService(session)
    profile = await identity_svc.get_or_create_default_profile()
    identity = await identity_svc.get_full_identity(profile.id)

    parts = [f"Person: {profile.name}"]
    if identity["beliefs"]:
        for b in identity["beliefs"]:
            parts.append(f"Belief: {b['topic']} — {b.get('stance', '')}")
    if identity["preferences"]:
        for p in identity["preferences"]:
            parts.append(f"Preference: {p['category']} — {p.get('value', '')}")

    identity_text = "\n".join(parts)

    system = (
        "You are simulating how a specific person would make a decision. "
        "Based on their beliefs and preferences, explain what they would likely decide "
        "and why. Respond in first person as that person."
    )
    user = (
        f"Given this identity:\n{identity_text}\n\n"
        f"How would this person decide in this scenario: {body.scenario}"
    )

    decision = await generate(system=system, user=user)
    return SimulateResponse(decision=decision)


@router.post("/compare", response_model=CompareResponse)
async def compare(
    body: CompareRequest,
    session: AsyncSession = Depends(get_session),
    _token: AccessToken = Depends(get_current_token),
):
    """Compare a stance with this person's perspective on a topic."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    beliefs = await repo.list_beliefs(profile_id, topic=body.topic)

    belief_text = ""
    if beliefs:
        lines = []
        for b in beliefs:
            lines.append(f"- Stance: {b.stance}, Nuance: {b.nuance}, Confidence: {b.confidence}")
        belief_text = "\n".join(lines)
    else:
        belief_text = "No specific beliefs recorded on this topic."

    system = (
        "You are analyzing how a person's existing beliefs compare to a given stance. "
        "Explain whether they would agree, disagree, or have a nuanced view. "
        "Be specific about where they align and diverge."
    )
    user = (
        f"Topic: {body.topic}\n"
        f"Proposed stance: {body.stance}\n\n"
        f"This person's existing beliefs on this topic:\n{belief_text}\n\n"
        "How does this person's perspective compare to the proposed stance?"
    )

    analysis = await generate(system=system, user=user)
    return CompareResponse(analysis=analysis)


@router.get("/explain-belief/{belief_id}", response_model=ExplainBeliefResponse)
async def explain_belief(
    belief_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Trace a belief back to its supporting memories (owner only)."""
    repo = IdentityRepository(session)
    belief = await repo.get_belief(belief_id)
    if belief is None:
        raise HTTPException(status_code=404, detail="Belief not found")

    # Load supporting memories via the relationship
    from sqlalchemy.orm import selectinload

    from engram.models.identity import Belief

    result = await session.execute(
        select(Belief)
        .where(Belief.id == belief_id)
        .options(selectinload(Belief.supporting_memories))
    )
    belief_with_memories = result.scalar_one()

    return ExplainBeliefResponse(
        belief_id=str(belief_with_memories.id),
        topic=belief_with_memories.topic,
        stance=belief_with_memories.stance,
        nuance=belief_with_memories.nuance,
        confidence=belief_with_memories.confidence,
        source=belief_with_memories.source,
        supporting_memory_ids=[str(m.id) for m in belief_with_memories.supporting_memories],
    )


@router.post("/imagine", response_model=ImagineResponse)
async def imagine(
    body: ImagineRequest,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Generate an image from a scenario description."""
    from engram.photos.service import PhotoService

    service = PhotoService(session)
    result = await service.imagine(scenario=body.scenario, style=body.style)
    await session.commit()
    return ImagineResponse(**result)


# ---- Export / Import routes -------------------------------------------------


@router.post("/export")
async def export_engram(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Export the entire engram as JSON (owner only).

    Includes profile, memories (with topics/people), beliefs, preferences,
    style profile, and photo metadata. Excludes API keys, access tokens,
    embeddings, ingestion jobs, and data_exports records.
    """
    identity_svc = IdentityService(session)
    profile = await identity_svc.get_or_create_default_profile()
    identity = await identity_svc.get_full_identity(profile.id)

    # Fetch all active memories with topics and people
    result = await session.execute(
        select(Memory)
        .where(Memory.status == "active")
        .options(selectinload(Memory.topics), selectinload(Memory.people))
        .order_by(Memory.created_at)
    )
    memories = list(result.scalars().all())

    # Fetch photos metadata (no binary data)
    photo_repo = PhotoRepository(session)
    photos = await photo_repo.list_photos()

    # Build export
    exported_memories = []
    for m in memories:
        exported_memories.append(
            {
                "content": m.content,
                "intent": m.intent,
                "meaning": m.meaning,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "source": m.source,
                "source_ref": m.source_ref,
                "authorship": m.authorship,
                "importance_score": m.importance_score,
                "confidence": m.confidence,
                "reinforcement_count": m.reinforcement_count,
                "status": m.status,
                "visibility": m.visibility,
                "topics": [t.name for t in m.topics],
                "people": [
                    {"name": p.name, "relationship_type": p.relationship_type}
                    for p in m.people
                ],
            }
        )

    exported_beliefs = []
    for b in identity["beliefs"]:
        exported_beliefs.append(
            {
                "topic": b["topic"],
                "stance": b.get("stance"),
                "nuance": b.get("nuance"),
                "confidence": b.get("confidence"),
                "source": b.get("source"),
            }
        )

    exported_preferences = []
    for p in identity["preferences"]:
        exported_preferences.append(
            {
                "category": p["category"],
                "value": p.get("value"),
                "strength": p.get("strength"),
                "source": p.get("source"),
            }
        )

    exported_photos = []
    for ph in photos:
        exported_photos.append(
            {
                "description": ph.description,
                "tags": ph.tags,
                "is_reference": ph.is_reference,
            }
        )

    return {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {"name": profile.name, "description": profile.description},
        "memories": exported_memories,
        "beliefs": exported_beliefs,
        "preferences": exported_preferences,
        "style_profile": identity["style"],
        "photos": exported_photos,
    }


@router.post("/import", response_model=ImportSummary)
async def import_engram(
    body: ImportPayload,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Import engram data from JSON (owner only).

    Creates identity profile, memories (with topics/people linkage),
    beliefs, preferences, and style profile. Embeddings are set to null
    (re-embedding is a future enhancement).
    """
    identity_svc = IdentityService(session)
    identity_repo = IdentityRepository(session)
    memory_repo = MemoryRepository(session)

    # 1. Update profile if provided
    profile = await identity_svc.get_or_create_default_profile()
    if body.profile:
        if body.profile.get("name"):
            profile.name = body.profile["name"]
        if body.profile.get("description") is not None:
            profile.description = body.profile.get("description")
        await session.flush()

    summary = ImportSummary()

    # 2. Import memories with topics and people
    total_topics_linked = 0
    total_people_linked = 0
    for mem_data in body.memories:
        mem_kwargs: dict[str, Any] = {
            "content": mem_data.content,
            "intent": mem_data.intent,
            "meaning": mem_data.meaning,
            "source": mem_data.source,
            "source_ref": mem_data.source_ref,
            "authorship": mem_data.authorship,
            "importance_score": mem_data.importance_score,
            "confidence": mem_data.confidence,
            "reinforcement_count": mem_data.reinforcement_count,
            "status": mem_data.status,
            "visibility": mem_data.visibility,
        }
        if mem_data.timestamp:
            mem_kwargs["timestamp"] = datetime.fromisoformat(mem_data.timestamp)

        memory = await memory_repo.create(**mem_kwargs)

        # Link topics
        if mem_data.topics:
            topic_ids = []
            for topic_name in mem_data.topics:
                topic = await memory_repo.get_or_create_topic(topic_name)
                topic_ids.append(topic.id)
            await memory_repo.link_topics(memory.id, topic_ids)
            total_topics_linked += len(topic_ids)

        # Link people
        if mem_data.people:
            person_ids = []
            for person_data in mem_data.people:
                person = await memory_repo.get_or_create_person(person_data.name)
                if person_data.relationship_type and not person.relationship_type:
                    person.relationship_type = person_data.relationship_type
                    await session.flush()
                person_ids.append(person.id)
            await memory_repo.link_people(memory.id, person_ids)
            total_people_linked += len(person_ids)

        summary.memories_imported += 1

    summary.topics_linked = total_topics_linked
    summary.people_linked = total_people_linked

    # 3. Import beliefs
    for belief_data in body.beliefs:
        await identity_repo.create_belief(
            profile.id,
            topic=belief_data.topic,
            stance=belief_data.stance,
            nuance=belief_data.nuance,
            confidence=belief_data.confidence,
            source=belief_data.source,
        )
        summary.beliefs_imported += 1

    # 4. Import preferences
    for pref_data in body.preferences:
        await identity_repo.create_preference(
            profile.id,
            category=pref_data.category,
            value=pref_data.value,
            strength=pref_data.strength,
            source=pref_data.source,
        )
        summary.preferences_imported += 1

    # 5. Import style profile
    if body.style_profile:
        style_kwargs = body.style_profile.model_dump(exclude_unset=True)
        if style_kwargs:
            await identity_repo.upsert_style(profile.id, **style_kwargs)
            summary.style_imported = True

    return summary
