"""Request dependencies for auth and database access."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import TokenPayload, decode_access_token, decode_token
from db.models.user import User
from db.session import get_async_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    """Yield an async database session."""

    async for session in get_async_session():
        yield session


async def apply_tenant_rls(db: AsyncSession, tenant_id: UUID) -> None:
    """Set tenant context for PostgreSQL RLS in the active transaction."""

    await db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})


async def apply_user_rls(db: AsyncSession, user_id: UUID) -> None:
    """Set user context for PostgreSQL RLS in the active transaction."""

    await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve active user from access token."""

    if credentials is None:
        raise HTTPException(status_code=401, detail={"error": "not_authenticated"})
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Token is invalid or expired."},
        ) from exc

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": "user_not_found"})

    await db.execute(text("SET LOCAL app.tenant_id = :tenant_id"), {"tenant_id": str(user.tenant_id)})
    await db.execute(text("SET LOCAL app.user_id = :user_id"), {"user_id": str(user.id)})
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role for endpoint access."""

    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


async def get_current_user_ws(token: str, db: AsyncSession) -> User:
    """Resolve user from token for WebSocket handshakes."""

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise ValueError("user_not_found")
        return user
    except Exception as exc:
        raise ValueError("invalid_token") from exc


# Backward-compatible dependency consumed by existing routers.
async def get_current_token(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)) -> TokenPayload:
    """Decode bearer token and return typed payload for legacy routes."""

    if credentials is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    try:
        return decode_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc
