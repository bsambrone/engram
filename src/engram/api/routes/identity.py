"""Identity API routes — beliefs, preferences, style, inference, snapshots."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import get_current_token, require_owner
from engram.db import get_session
from engram.identity.repository import IdentityRepository
from engram.identity.service import IdentityService
from engram.models.auth import AccessToken

router = APIRouter(prefix="/identity", tags=["identity"])


# ---- Pydantic schemas -------------------------------------------------------


class ProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class BeliefCreate(BaseModel):
    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None


class BeliefOut(BaseModel):
    id: uuid.UUID
    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class BeliefSharedOut(BaseModel):
    """Belief output for shared tokens — no source field."""

    id: uuid.UUID
    topic: str
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None

    model_config = {"from_attributes": True}


class BeliefUpdate(BaseModel):
    topic: str | None = None
    stance: str | None = None
    nuance: str | None = None
    confidence: float | None = None


class PreferenceCreate(BaseModel):
    category: str
    value: str | None = None
    strength: float | None = None


class PreferenceOut(BaseModel):
    id: uuid.UUID
    category: str
    value: str | None = None
    strength: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    category: str | None = None
    value: str | None = None
    strength: float | None = None


class StyleOut(BaseModel):
    tone: str | None = None
    humor_level: float | None = None
    verbosity: float | None = None
    formality: float | None = None
    vocabulary_notes: str | None = None
    communication_patterns: str | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class StyleUpdate(BaseModel):
    tone: str | None = None
    humor_level: float | None = None
    verbosity: float | None = None
    formality: float | None = None
    vocabulary_notes: str | None = None
    communication_patterns: str | None = None


class SnapshotCreate(BaseModel):
    label: str | None = None


class SnapshotOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    snapshot_data: dict
    label: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


# ---- Helpers -----------------------------------------------------------------


async def _get_profile_id(session: AsyncSession) -> uuid.UUID:
    """Get or create the default profile and return its ID."""
    service = IdentityService(session)
    profile = await service.get_or_create_default_profile()
    return profile.id


# ---- Profile routes ----------------------------------------------------------


@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    session: AsyncSession = Depends(get_session),
    _token: AccessToken = Depends(get_current_token),
):
    """Get the identity profile (accessible to both shared and owner tokens)."""
    service = IdentityService(session)
    profile = await service.get_or_create_default_profile()
    return profile


@router.put("/profile", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Update the identity profile name/description (owner only)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    profile = await repo.update_profile(profile_id, **updates)
    return profile


# ---- Belief routes -----------------------------------------------------------


@router.get("/beliefs")
async def list_beliefs(
    topic: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    token: AccessToken = Depends(get_current_token),
):
    """List beliefs. Shared tokens get no source field; owner tokens get full output."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    beliefs = await repo.list_beliefs(profile_id, topic=topic)
    if token.access_level == "owner":
        return [BeliefOut.model_validate(b).model_dump() for b in beliefs]
    return [BeliefSharedOut.model_validate(b).model_dump() for b in beliefs]


@router.post("/beliefs", status_code=201, response_model=BeliefOut)
async def create_belief(
    body: BeliefCreate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Create a manual belief (owner only, source=user)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    belief = await repo.create_belief(
        profile_id,
        topic=body.topic,
        stance=body.stance,
        nuance=body.nuance,
        confidence=body.confidence,
        source="user",
    )
    return belief


@router.put("/beliefs/{belief_id}", response_model=BeliefOut)
async def update_belief(
    belief_id: uuid.UUID,
    body: BeliefUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Update a belief (owner only, sets source=user)."""
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_unset=True)
    updates["source"] = "user"
    belief = await repo.update_belief(belief_id, **updates)
    if belief is None:
        raise HTTPException(status_code=404, detail="Belief not found")
    return belief


@router.delete("/beliefs/{belief_id}")
async def delete_belief(
    belief_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Delete a belief (owner only)."""
    repo = IdentityRepository(session)
    deleted = await repo.delete_belief(belief_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Belief not found")
    return {"deleted": True}


# ---- Preference routes -------------------------------------------------------


@router.get("/preferences", response_model=list[PreferenceOut])
async def list_preferences(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List preferences (owner only)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    prefs = await repo.list_preferences(profile_id)
    return prefs


@router.post("/preferences", status_code=201, response_model=PreferenceOut)
async def create_preference(
    body: PreferenceCreate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Create a manual preference (owner only, source=user)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    pref = await repo.create_preference(
        profile_id,
        category=body.category,
        value=body.value,
        strength=body.strength,
        source="user",
    )
    return pref


@router.put("/preferences/{preference_id}", response_model=PreferenceOut)
async def update_preference(
    preference_id: uuid.UUID,
    body: PreferenceUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Update a preference (owner only)."""
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_unset=True)
    updates["source"] = "user"
    pref = await repo.update_preference(preference_id, **updates)
    if pref is None:
        raise HTTPException(status_code=404, detail="Preference not found")
    return pref


@router.delete("/preferences/{preference_id}")
async def delete_preference(
    preference_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Delete a preference (owner only)."""
    repo = IdentityRepository(session)
    deleted = await repo.delete_preference(preference_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"deleted": True}


# ---- Style routes ------------------------------------------------------------


@router.get("/style", response_model=StyleOut)
async def get_style(
    session: AsyncSession = Depends(get_session),
    _token: AccessToken = Depends(get_current_token),
):
    """Get style profile (accessible to both shared and owner)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    style = await repo.get_style(profile_id)
    if style is None:
        return StyleOut()
    return style


@router.put("/style", response_model=StyleOut)
async def upsert_style(
    body: StyleUpdate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Upsert style (owner only, source=user)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    updates = body.model_dump(exclude_unset=True)
    updates["source"] = "user"
    style = await repo.upsert_style(profile_id, **updates)
    return style


# ---- Inference route ---------------------------------------------------------


@router.post("/infer")
async def trigger_inference(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Trigger LLM-powered identity inference from memories (owner only)."""
    from engram.identity.inference import run_inference

    profile_id = await _get_profile_id(session)
    result = await run_inference(session, profile_id)
    await session.commit()
    return result


# ---- Snapshot routes ---------------------------------------------------------


@router.post("/snapshot", status_code=201, response_model=SnapshotOut)
async def create_snapshot(
    body: SnapshotCreate | None = None,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Create an identity snapshot (owner only)."""
    profile_id = await _get_profile_id(session)
    service = IdentityService(session)
    label = body.label if body else None
    snapshot = await service.take_snapshot(profile_id, label=label)
    return SnapshotOut(
        id=snapshot.id,
        profile_id=snapshot.profile_id,
        snapshot_data=snapshot.snapshot_data,
        label=snapshot.label,
        created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
    )


@router.get("/snapshots", response_model=list[SnapshotOut])
async def list_snapshots(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List identity snapshots (owner only)."""
    profile_id = await _get_profile_id(session)
    repo = IdentityRepository(session)
    snapshots = await repo.list_snapshots(profile_id)
    return [
        SnapshotOut(
            id=s.id,
            profile_id=s.profile_id,
            snapshot_data=s.snapshot_data,
            label=s.label,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in snapshots
    ]


@router.get("/snapshot/{snapshot_id}", response_model=SnapshotOut)
async def get_snapshot(
    snapshot_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Get a specific identity snapshot (owner only)."""
    repo = IdentityRepository(session)
    snapshot = await repo.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return SnapshotOut(
        id=snapshot.id,
        profile_id=snapshot.profile_id,
        snapshot_data=snapshot.snapshot_data,
        label=snapshot.label,
        created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
    )
