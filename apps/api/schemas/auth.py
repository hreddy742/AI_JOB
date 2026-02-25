"""Authentication schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Register request payload."""

    email: EmailStr
    password: str
    full_name: str = Field(min_length=2, max_length=255)


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class ForgotRequest(BaseModel):
    """Forgot-password request payload."""

    email: EmailStr


class ResetRequest(BaseModel):
    """Reset-password request payload."""

    token: str
    new_password: str


class ResendRequest(BaseModel):
    """Resend-verification request payload."""

    email: EmailStr


class VerifyRequest(BaseModel):
    """Verify-email request payload."""

    token: str


class UserAuthProfile(BaseModel):
    """Authenticated user payload."""

    id: str
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    role: str
    email_verified: bool
    auth_provider: str


class TokenResponse(BaseModel):
    """Access token payload returned by auth endpoints."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    user: UserAuthProfile


class AuthMessage(BaseModel):
    """Generic auth message response."""

    message: str
