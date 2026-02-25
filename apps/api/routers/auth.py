"""Authentication API routes."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import get_db
from core.rate_limiter import check_rate_limit, get_client_ip
from schemas.auth import (
    AuthMessage,
    ForgotRequest,
    LoginRequest,
    RegisterRequest,
    ResendRequest,
    ResetRequest,
    TokenResponse,
    VerifyRequest,
)
from services.auth_service import (
    AuthError,
    get_google_oauth_url,
    get_redis_client,
    handle_google_callback,
    login_user,
    logout_user,
    refresh_access_token,
    register_user,
    request_password_reset,
    resend_verification_email,
    reset_password,
    verify_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE_NAME = "apex_refresh_token"


def _cookie_domain() -> str | None:
    domain = (settings.COOKIE_DOMAIN or "").strip()
    if domain in {"", "localhost", "127.0.0.1"}:
        return None
    return domain


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    cookie_args = {
        "key": COOKIE_NAME,
        "value": refresh_token,
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
        "max_age": 30 * 86400,
    }
    domain = _cookie_domain()
    if domain:
        cookie_args["domain"] = domain
    response.set_cookie(**cookie_args)


def _clear_refresh_cookie(response: Response) -> None:
    cookie_args = {
        "key": COOKIE_NAME,
        "path": "/",
        "secure": settings.COOKIE_SECURE,
        "samesite": "lax",
    }
    domain = _cookie_domain()
    if domain:
        cookie_args["domain"] = domain
    response.delete_cookie(**cookie_args)


def _redis() -> redis.Redis:
    return get_redis_client()


@router.post("/register", response_model=AuthMessage, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)) -> AuthMessage:
    redis_client = _redis()
    ip = get_client_ip(request)
    await check_rate_limit(
        redis_client,
        key=f"rl:register:{ip}",
        max_attempts=settings.RATE_LIMIT_REGISTER_MAX,
        window_seconds=settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS,
    )
    try:
        result = await register_user(payload.email, payload.password, payload.full_name, db, ip)
        return AuthMessage(**result)
    except AuthError as exc:
        if exc.code == "validation_error":
            raise HTTPException(status_code=422, detail=exc.args[0]) from exc
        if exc.code == "account_exists":
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if exc.code == "email_delivery_failed":
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email_endpoint(payload: VerifyRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    try:
        token_pair = await verify_email(payload.token, db, ip=ip, user_agent=user_agent)
        _set_refresh_cookie(response, token_pair["refresh_token"])
        return TokenResponse(
            access_token=token_pair["access_token"],
            token_type=token_pair["token_type"],
            expires_in=token_pair["expires_in"],
            user=token_pair["user"],
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    redis_client = _redis()
    ip = get_client_ip(request)
    await check_rate_limit(
        redis_client,
        key=f"rl:login:{ip}",
        max_attempts=settings.RATE_LIMIT_LOGIN_MAX,
        window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    )
    user_agent = request.headers.get("user-agent", "")
    try:
        token_pair = await login_user(payload.email, payload.password, db, redis_client, ip, user_agent)
        _set_refresh_cookie(response, token_pair["refresh_token"])
        return TokenResponse(
            access_token=token_pair["access_token"],
            token_type=token_pair["token_type"],
            expires_in=token_pair["expires_in"],
            user=token_pair["user"],
        )
    except AuthError as exc:
        if exc.code == "email_not_verified":
            raise HTTPException(status_code=403, detail={"error": "email_not_verified", "message": str(exc)}) from exc
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/google")
async def google_auth() -> RedirectResponse:
    redis_client = _redis()
    url = await get_google_oauth_url(redis_client)
    return RedirectResponse(url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    redis_client = _redis()
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    try:
        token_pair = await handle_google_callback(code, state, db, redis_client, ip, user_agent)
        redirect = RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?token={quote_plus(token_pair['access_token'])}",
            status_code=302,
        )
        _set_refresh_cookie(redirect, token_pair["refresh_token"])
        return redirect
    except AuthError as exc:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/login?error={quote_plus(str(exc))}",
            status_code=302,
        )


@router.post("/forgot-password", response_model=AuthMessage)
async def forgot_password(payload: ForgotRequest, request: Request, db: AsyncSession = Depends(get_db)) -> AuthMessage:
    redis_client = _redis()
    ip = get_client_ip(request)
    await check_rate_limit(
        redis_client,
        key=f"rl:forgot:{ip}",
        max_attempts=settings.RATE_LIMIT_RESET_MAX,
        window_seconds=settings.RATE_LIMIT_RESET_WINDOW_SECONDS,
    )
    result = await request_password_reset(payload.email, db, ip)
    return AuthMessage(**result)


@router.post("/reset-password", response_model=AuthMessage)
async def reset_password_endpoint(payload: ResetRequest, request: Request, db: AsyncSession = Depends(get_db)) -> AuthMessage:
    ip = get_client_ip(request)
    try:
        result = await reset_password(payload.token, payload.new_password, db, ip)
        return AuthMessage(**result)
    except AuthError as exc:
        if exc.code == "validation_error":
            raise HTTPException(status_code=422, detail=exc.args[0]) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    refresh_cookie = request.cookies.get(COOKIE_NAME)
    if not refresh_cookie:
        raise HTTPException(status_code=401, detail="Missing refresh token.")
    redis_client = _redis()
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    try:
        token_pair = await refresh_access_token(refresh_cookie, db, redis_client, ip, user_agent)
        _set_refresh_cookie(response, token_pair["refresh_token"])
        return TokenResponse(
            access_token=token_pair["access_token"],
            token_type=token_pair["token_type"],
            expires_in=token_pair["expires_in"],
            user=token_pair["user"],
        )
    except AuthError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout", response_model=AuthMessage)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> AuthMessage:
    refresh_cookie = request.cookies.get(COOKIE_NAME)
    ip = get_client_ip(request)
    result = await logout_user(refresh_cookie, db, ip)
    _clear_refresh_cookie(response)
    return AuthMessage(**result)


@router.post("/resend-verification", response_model=AuthMessage)
async def resend_verification(payload: ResendRequest, request: Request, db: AsyncSession = Depends(get_db)) -> AuthMessage:
    redis_client = _redis()
    ip = get_client_ip(request)
    await check_rate_limit(
        redis_client,
        key=f"rl:resend:{ip}",
        max_attempts=settings.RATE_LIMIT_REGISTER_MAX,
        window_seconds=settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS,
    )
    try:
        result = await resend_verification_email(payload.email, db, ip)
        return AuthMessage(**result)
    except AuthError as exc:
        if exc.code == "email_delivery_failed":
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
