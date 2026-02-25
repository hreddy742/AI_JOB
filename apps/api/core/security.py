"""Security utilities for password and token handling."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

# Used to equalize verification time for unknown users.
TIMING_PREVENTION_HASH = "$2b$12$4j8M40VQnJ0z6A6WQv2rJuUPmrmM3M3Yy40f4M3W3z8Nn4O.GoQ7O"


class TokenPayload(BaseModel):
    """Typed JWT claims consumed by routers/services."""

    sub: str
    role: str
    tid: str
    exp: int
    iat: int
    type: str

    @property
    def tenant_id(self) -> str:
        """Compatibility accessor used by existing routers."""

        return self.tid

    @property
    def token_type(self) -> str:
        """Compatibility accessor used by existing routers."""

        return self.type


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    password_bytes = plain.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash using passlib constant-time checks."""

    password_bytes = plain.encode("utf-8")
    hashed_bytes = hashed.encode("utf-8")
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (UnknownHashError, ValueError):
        # Fall back to passlib to preserve compatibility with any legacy formats.
        try:
            return pwd_context.verify(plain, hashed)
        except (UnknownHashError, ValueError):
            logger.warning("invalid_password_hash_format")
            return False


def validate_password_strength(password: str) -> list[str]:
    """Validate password complexity requirements."""

    errors: list[str] = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if re.search(r"[A-Z]", password) is None:
        errors.append("Password must include at least one uppercase letter.")
    if re.search(r"[a-z]", password) is None:
        errors.append("Password must include at least one lowercase letter.")
    if re.search(r"\d", password) is None:
        errors.append("Password must include at least one digit.")
    if re.search(r"[!@#$%^&*()_+\-=\[\]{}|;':\",.<>?/\\]", password) is None:
        errors.append("Password must include at least one special character.")
    return errors


def generate_secure_token() -> str:
    """Generate a secure one-time token."""

    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a raw token for DB persistence."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_secret() -> str:
    return settings.JWT_SECRET_KEY or settings.SECRET_KEY


def create_access_token(user_id: str, role_or_tenant: str, tenant_or_role: str) -> str:
    """Create signed access token with strict payload shape.

    Accepts both argument orders for backward compatibility:
    1) (user_id, role, tenant_id)
    2) (user_id, tenant_id, role)
    """

    known_roles = {"admin", "user", "coach"}
    if role_or_tenant in known_roles and tenant_or_role not in known_roles:
        role = role_or_tenant
        tenant_id = tenant_or_role
    else:
        tenant_id = role_or_tenant
        role = tenant_or_role

    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "tid": tenant_id,
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "iat": int(now.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _token_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate access token payload."""

    payload = jwt.decode(token, _token_secret(), algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def create_refresh_token_value() -> str:
    """Generate raw refresh token value before hashing."""

    return secrets.token_urlsafe(48)


# Backward compatibility wrappers used across existing code paths.
def get_password_hash(password: str) -> str:
    """Compatibility alias for hash_password."""

    return hash_password(password)


def create_refresh_token(subject: str, tenant_id: str, role: str) -> str:
    """Compatibility helper for legacy tests, creates JWT refresh token."""

    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "tid": tenant_id,
        "exp": int((now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
        "iat": int(now.timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, _token_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Compatibility decode for legacy consumers."""

    payload = jwt.decode(token, _token_secret(), algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") not in {"access", "refresh"}:
        raise JWTError("Invalid token type")
    return TokenPayload(**payload)
