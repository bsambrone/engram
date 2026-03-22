"""Tokens CRUD endpoints — all require owner access."""

import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.api.deps import generate_raw_token, require_owner
from engram.db import get_session
from engram.models.auth import AccessToken

router = APIRouter(prefix="/tokens", tags=["tokens"])


class TokenCreate(BaseModel):
    name: str
    access_level: str = "shared"


class TokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    access_level: str
    created_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class TokenCreateResponse(TokenResponse):
    token: str  # Raw token, shown only once


@router.post("", status_code=201, response_model=TokenCreateResponse)
async def create_token(
    body: TokenCreate,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Create a new access token. The raw token is returned only once."""
    raw_token = generate_raw_token()
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    access_token = AccessToken(
        name=body.name,
        token_hash=token_hash,
        access_level=body.access_level,
    )
    session.add(access_token)
    await session.flush()
    await session.refresh(access_token)

    return TokenCreateResponse(
        id=access_token.id,
        name=access_token.name,
        access_level=access_token.access_level,
        created_at=access_token.created_at,
        expires_at=access_token.expires_at,
        revoked_at=access_token.revoked_at,
        token=raw_token,
    )


@router.get("", response_model=list[TokenResponse])
async def list_tokens(
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """List all active (non-revoked) tokens."""
    result = await session.execute(
        select(AccessToken).where(AccessToken.revoked_at.is_(None))
    )
    tokens = result.scalars().all()
    return tokens


@router.delete("/{token_id}", response_model=TokenResponse)
async def revoke_token(
    token_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _owner: AccessToken = Depends(require_owner),
):
    """Soft-delete a token by setting revoked_at."""
    from sqlalchemy import func

    result = await session.execute(
        select(AccessToken).where(AccessToken.id == token_id)
    )
    token = result.scalar_one_or_none()
    if token is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Token not found")

    token.revoked_at = func.now()
    await session.flush()
    await session.refresh(token)
    return token
