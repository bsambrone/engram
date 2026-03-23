"""Engram conversation API routes — ask, topics, opinions, summarize, simulate, compare."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import get_current_token, require_owner
from engram.db import get_session
from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService
from engram.llm.providers import generate
from engram.llm.rag import ask_engram
from engram.models.auth import AccessToken
from engram.models.memory import Memory, MemoryTopic, Topic

router = APIRouter(prefix="/engram", tags=["engram"])


# ---- Pydantic schemas -------------------------------------------------------


class AskRequest(BaseModel):
    query: str


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
    result = await ask_engram(session, body.query, is_owner=is_owner)
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
