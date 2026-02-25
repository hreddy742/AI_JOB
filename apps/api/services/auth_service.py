"""Authentication business logic service."""

from __future__ import annotations

import logging
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import (
    TIMING_PREVENTION_HASH,
    create_access_token,
    create_refresh_token_value,
    generate_secure_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from db.models.auth_event import AuthEvent
from db.models.email_verification import EmailVerification
from db.models.refresh_token import RefreshToken
from db.models.password_reset import PasswordReset
from db.models.tenant import Tenant
from db.models.user import User
from db.models.enums import RoleEnum
from db.session import AsyncSessionFactory
from services.ingestion_service import run_default_ingestion_cycle, run_ingestion_for_sources
from services.email_service import (
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)

logger = logging.getLogger(__name__)


class AuthError(ValueError):
    """Typed auth domain exception."""

    def __init__(self, message: str, code: str = "auth_error") -> None:
        super().__init__(message)
        self.code = code


def get_redis_client() -> redis.Redis:
    """Create Redis client for auth state operations."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def register_user(email: str, password: str, full_name: str, db: AsyncSession, ip: str) -> dict[str, str]:
    """Register a new user with verification flow."""

    errors = validate_password_strength(password)
    if errors:
        raise AuthError({"field": "password", "errors": errors}, code="validation_error")

    email_norm = email.lower().strip()
    existing = await db.execute(select(User).where(User.email == email_norm))
    existing_user = existing.scalar_one_or_none()
    if existing_user is not None:
        if existing_user.email_verified:
            await _log_event(
                db,
                existing_user.id,
                existing_user.tenant_id,
                "register",
                ip,
                {"duplicate": True, "already_verified": True},
            )
            await db.commit()
            raise AuthError("Account already exists. Please sign in.", code="account_exists")

        await db.execute(
            update(EmailVerification)
            .where(and_(EmailVerification.user_id == existing_user.id, EmailVerification.used_at.is_(None)))
            .values(used_at=datetime.now(UTC))
        )

        raw_token = generate_secure_token()
        db.add(
            EmailVerification(
                user_id=existing_user.id,
                token_hash=hash_token(raw_token),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )

        await _log_event(
            db,
            existing_user.id,
            existing_user.tenant_id,
            "register",
            ip,
            {"duplicate": True, "verification_resent": True},
        )
        await db.commit()

        sent = await send_verification_email(existing_user.email, existing_user.full_name, raw_token)
        if not sent:
            await _log_event(
                db,
                existing_user.id,
                existing_user.tenant_id,
                "email_delivery_failed",
                ip,
                {"flow": "register_duplicate_verification"},
            )
            await db.commit()
            raise AuthError(
                "Could not deliver verification email. Please check SMTP setup, then use resend verification.",
                code="email_delivery_failed",
            )

        return {"message": "Account exists but is not verified. A new verification email has been sent."}

    tenant_name = full_name.strip()[:64] if full_name.strip() else email_norm.split("@")[0]
    tenant = Tenant(name=f"{tenant_name} Workspace")
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=email_norm,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=RoleEnum.admin,
        auth_provider="email",
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    raw_token = generate_secure_token()
    db.add(
        EmailVerification(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

    await _log_event(db, user.id, user.tenant_id, "register", ip)
    await db.commit()

    sent = await send_verification_email(user.email, user.full_name, raw_token)
    if not sent:
        await _log_event(
            db,
            user.id,
            user.tenant_id,
            "email_delivery_failed",
            ip,
            {"flow": "register_verification"},
        )
        await db.commit()
        raise AuthError(
            "Could not deliver verification email. Please check SMTP setup, then use resend verification.",
            code="email_delivery_failed",
        )
    return {"message": "Account created! Check your email to verify."}


async def verify_email(token: str, db: AsyncSession, ip: str = "0.0.0.0", user_agent: str | None = None) -> dict[str, Any]:
    """Verify email token and return login token pair."""

    token_hash = hash_token(token)
    result = await db.execute(
        select(EmailVerification).where(
            and_(EmailVerification.token_hash == token_hash, EmailVerification.used_at.is_(None))
        )
    )
    ev = result.scalar_one_or_none()
    if ev is None:
        raise AuthError("Invalid or already-used link.", code="invalid_token")
    if ev.expires_at < datetime.now(UTC):
        raise AuthError("Link expired. Request a new one.", code="expired_token")

    user_result = await db.execute(select(User).where(User.id == ev.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise AuthError("Invalid or already-used link.", code="invalid_token")

    ev.used_at = datetime.now(UTC)
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    await _log_event(db, user.id, user.tenant_id, "email_verified", ip, user_agent=user_agent)
    await db.commit()
    await _prime_tenant_feed(db, user.tenant_id)
    _schedule_initial_tenant_ingestion(user.tenant_id)

    await send_welcome_email(user.email, user.full_name)
    return await _create_token_pair(user, db, ip, user_agent)


async def login_user(
    email: str,
    password: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    ip: str,
    user_agent: str,
) -> dict[str, Any]:
    """Authenticate a user and issue session tokens."""

    email_norm = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()

    if user is None:
        verify_password("timing_prevention", TIMING_PREVENTION_HASH)
        raise AuthError("Invalid email or password.", code="invalid_credentials")

    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() // 60) + 1
        await _log_event(db, user.id, user.tenant_id, "login_locked", ip, {"minutes": remaining}, user_agent)
        await db.commit()
        raise AuthError(f"Account locked. Try again in {remaining} minutes.", code="account_locked")

    if not user.password_hash or not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
            await _log_event(db, user.id, user.tenant_id, "account_locked", ip, user_agent=user_agent)
        await _log_event(db, user.id, user.tenant_id, "login_failed", ip, user_agent=user_agent)
        await db.commit()
        raise AuthError("Invalid email or password.", code="invalid_credentials")

    if not user.email_verified:
        await _log_event(db, user.id, user.tenant_id, "login_failed", ip, {"reason": "email_not_verified"}, user_agent)
        await db.commit()
        err = AuthError("Please verify your email first.", code="email_not_verified")
        raise err

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = ip
    await _log_event(db, user.id, user.tenant_id, "login", ip, user_agent=user_agent)
    await db.commit()

    return await _create_token_pair(user, db, ip, user_agent)


async def get_google_oauth_url(redis_client: redis.Redis) -> str:
    """Generate Google OAuth authorization URL with CSRF state."""

    state = generate_secure_token()
    await redis_client.setex(f"oauth_state:{state}", 600, "valid")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def handle_google_callback(
    code: str,
    state: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    ip: str,
    user_agent: str,
) -> dict[str, Any]:
    """Process Google OAuth callback and return token pair."""

    state_key = f"oauth_state:{state}"
    state_value = await redis_client.get(state_key)
    if state_value is None:
        raise AuthError("Invalid OAuth state. Try again.", code="invalid_oauth_state")
    await redis_client.delete(state_key)

    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise AuthError("Google auth failed. Try again.", code="google_auth_failed")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise AuthError("Google auth failed. Try again.", code="google_auth_failed")

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise AuthError("Google auth failed. Try again.", code="google_auth_failed")

    payload = userinfo_resp.json()
    google_id = payload.get("id", "")
    g_email = (payload.get("email") or "").lower().strip()
    name = payload.get("name") or g_email.split("@")[0]
    avatar_url = payload.get("picture")

    if not google_id or not g_email:
        raise AuthError("Google did not provide email. Use email/password.", code="google_email_missing")

    result = await db.execute(select(User).where(or_(User.google_id == google_id, User.email == g_email)))
    user = result.scalar_one_or_none()

    now = datetime.now(UTC)
    if user and user.google_id:
        user.last_login_at = now
        user.last_login_ip = ip
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
        event = "google_oauth_login"
    elif user and not user.google_id:
        user.google_id = google_id
        user.auth_provider = "google"
        user.email_verified = True
        user.email_verified_at = user.email_verified_at or now
        user.last_login_at = now
        user.last_login_ip = ip
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
        event = "google_oauth_login"
    else:
        tenant = Tenant(name=f"{name[:64]} Workspace")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=g_email,
            full_name=name,
            avatar_url=avatar_url,
            google_id=google_id,
            auth_provider="google",
            email_verified=True,
            email_verified_at=now,
            role=RoleEnum.admin,
            is_active=True,
            last_login_at=now,
            last_login_ip=ip,
        )
        db.add(user)
        await db.flush()
        event = "google_oauth_register"

    await _log_event(db, user.id, user.tenant_id, event, ip, user_agent=user_agent)
    await db.commit()

    if event == "google_oauth_register":
        await _prime_tenant_feed(db, user.tenant_id)
        _schedule_initial_tenant_ingestion(user.tenant_id)
        await send_welcome_email(user.email, user.full_name)

    return await _create_token_pair(user, db, ip, user_agent)


async def request_password_reset(email: str, db: AsyncSession, ip: str) -> dict[str, str]:
    """Request password reset without revealing account existence."""

    response = {"message": "If that email has an account, a reset link is on its way."}
    email_norm = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()
    if user is None:
        return response

    await db.execute(
        update(PasswordReset)
        .where(and_(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)))
        .values(used_at=datetime.now(UTC))
    )

    raw_token = generate_secure_token()
    db.add(
        PasswordReset(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            ip_address=ip,
        )
    )

    await _log_event(db, user.id, user.tenant_id, "password_reset_requested", ip)
    await db.commit()

    await send_password_reset_email(user.email, user.full_name, raw_token, ip)
    return response


async def reset_password(token: str, new_password: str, db: AsyncSession, ip: str) -> dict[str, str]:
    """Consume reset token and set new password."""

    errors = validate_password_strength(new_password)
    if errors:
        raise AuthError({"field": "password", "errors": errors}, code="validation_error")

    result = await db.execute(
        select(PasswordReset).where(
            and_(PasswordReset.token_hash == hash_token(token), PasswordReset.used_at.is_(None))
        )
    )
    pr = result.scalar_one_or_none()
    if pr is None:
        raise AuthError("Invalid or already-used link.", code="invalid_token")
    if pr.expires_at < datetime.now(UTC):
        raise AuthError("This link expired. Request a new one.", code="expired_token")

    user_result = await db.execute(select(User).where(User.id == pr.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise AuthError("Invalid or already-used link.", code="invalid_token")

    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    pr.used_at = datetime.now(UTC)

    await db.execute(
        update(RefreshToken)
        .where(and_(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)))
        .values(revoked_at=datetime.now(UTC), revoked_reason="password_reset")
    )

    await _log_event(db, user.id, user.tenant_id, "password_reset_completed", ip)
    await db.commit()

    await send_password_changed_email(user.email, user.full_name)
    return {"message": "Password updated. Please log in with your new password."}


async def refresh_access_token(
    refresh_token_value: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    ip: str,
    user_agent: str,
) -> dict[str, Any]:
    """Rotate refresh token and issue new access/refresh pair."""

    token_hash_value = hash_token(refresh_token_value)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash_value))
    stored = result.scalar_one_or_none()
    if stored is None:
        raise AuthError("Invalid refresh token.", code="invalid_refresh")

    if stored.revoked_at is not None:
        await db.execute(
            update(RefreshToken)
            .where(and_(RefreshToken.family_id == stored.family_id, RefreshToken.revoked_at.is_(None)))
            .values(revoked_at=datetime.now(UTC), revoked_reason="suspicious")
        )
        user_result = await db.execute(select(User).where(User.id == stored.user_id))
        user = user_result.scalar_one_or_none()
        await _log_event(
            db,
            stored.user_id,
            user.tenant_id if user else None,
            "suspicious_token_reuse",
            ip,
            {"family_id": str(stored.family_id)},
            user_agent,
        )
        await db.commit()
        raise AuthError("Session expired. Please log in again.", code="suspicious_reuse")

    if stored.expires_at < datetime.now(UTC):
        raise AuthError("Session expired. Log in again.", code="session_expired")

    stored.revoked_at = datetime.now(UTC)
    stored.revoked_reason = "rotation"

    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        await db.commit()
        raise AuthError("Account deactivated.", code="account_deactivated")

    await db.commit()
    return await _create_token_pair(user, db, ip, user_agent, family_id=stored.family_id)


async def logout_user(refresh_token_value: str | None, db: AsyncSession, ip: str) -> dict[str, str]:
    """Revoke refresh token on logout."""

    if not refresh_token_value:
        return {"message": "Logged out successfully."}

    token_hash_value = hash_token(refresh_token_value)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash_value))
    token = result.scalar_one_or_none()
    tenant_id = None
    user_id = None

    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        token.revoked_reason = "logout"
        user_result = await db.execute(select(User).where(User.id == token.user_id))
        user = user_result.scalar_one_or_none()
        user_id = token.user_id
        tenant_id = user.tenant_id if user else None

    await _log_event(db, user_id, tenant_id, "logout", ip)
    await db.commit()
    return {"message": "Logged out successfully."}


async def resend_verification_email(email: str, db: AsyncSession, ip: str) -> dict[str, str]:
    """Resend email verification token with anti-enumeration behavior."""

    response = {"message": "If the account exists, a verification email has been sent."}
    email_norm = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()
    if user is None or user.email_verified:
        return response

    await db.execute(
        update(EmailVerification)
        .where(and_(EmailVerification.user_id == user.id, EmailVerification.used_at.is_(None)))
        .values(used_at=datetime.now(UTC))
    )

    raw_token = generate_secure_token()
    db.add(
        EmailVerification(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

    await _log_event(db, user.id, user.tenant_id, "email_verification_resent", ip)
    await db.commit()

    sent = await send_verification_email(user.email, user.full_name, raw_token)
    if not sent:
        await _log_event(
            db,
            user.id,
            user.tenant_id,
            "email_delivery_failed",
            ip,
            {"flow": "resend_verification"},
        )
        await db.commit()
        raise AuthError(
            "Could not deliver verification email. Please check SMTP setup and try again.",
            code="email_delivery_failed",
        )
    return response


async def _create_token_pair(
    user: User,
    db: AsyncSession,
    ip: str,
    user_agent: str | None,
    family_id: UUID | None = None,
) -> dict[str, Any]:
    """Create access token and persisted rotating refresh token."""

    access_token = create_access_token(str(user.id), user.role.value if hasattr(user.role, "value") else str(user.role), str(user.tenant_id))
    raw_refresh = create_refresh_token_value()
    fid = family_id or uuid4()

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            family_id=fid,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip,
            user_agent=user_agent,
        )
    )
    await db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 15 * 60,
        "refresh_token": raw_refresh,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "email_verified": user.email_verified,
            "auth_provider": user.auth_provider,
        },
    }


async def _log_event(
    db: AsyncSession,
    user_id: UUID | None,
    tenant_id: UUID | None,
    event_type: str,
    ip: str,
    metadata: dict[str, Any] | None = None,
    user_agent: str | None = None,
) -> None:
    """Write auth audit event without interrupting caller flow."""

    try:
        db.add(
            AuthEvent(
                user_id=user_id,
                tenant_id=tenant_id,
                event_type=event_type,
                ip_address=ip,
                user_agent=user_agent,
                event_metadata=metadata or {},
            )
        )
        await db.flush()
    except Exception:
        logger.exception("auth_event_log_failed", extra={"event_type": event_type})


def _schedule_initial_tenant_ingestion(tenant_id: UUID) -> None:
    """Run first ingestion cycle asynchronously for new/verified tenants."""

    async def _run() -> None:
        try:
            async with AsyncSessionFactory() as bg_db:
                await run_default_ingestion_cycle(bg_db, tenant_id)
        except Exception:
            logger.exception("initial_tenant_ingestion_failed", extra={"tenant_id": str(tenant_id)})

    asyncio.create_task(_run())


async def _prime_tenant_feed(db: AsyncSession, tenant_id: UUID) -> None:
    """Run a lightweight ingest so first search has real data quickly."""

    try:
        await run_ingestion_for_sources(db, tenant_id, ["remoteok"], min_age_hours=0)
    except Exception:
        logger.exception("tenant_feed_prime_failed", extra={"tenant_id": str(tenant_id)})
