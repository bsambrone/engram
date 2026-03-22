"""FastAPI dependencies for authentication and authorization."""

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.db import get_session
from engram.models.auth import AccessToken


def generate_raw_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


async def get_current_token(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AccessToken:
    """Extract and validate bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    raw_token = auth_header.removeprefix("Bearer ").strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    result = await session.execute(
        select(AccessToken).where(AccessToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    if token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    if token.expires_at is not None and token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token has expired")

    return token


async def require_owner(
    token: AccessToken = Depends(get_current_token),
) -> AccessToken:
    """Require the authenticated token to have owner access level."""
    if token.access_level != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return token
