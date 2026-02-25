from __future__ import annotations

from core.security import create_access_token, create_refresh_token, decode_token, get_password_hash, verify_password


def test_password_hash_and_verify() -> None:
    password = "StrongPassw0rd!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True


def test_access_token_contains_identity_claims() -> None:
    token = create_access_token("user-id", "tenant-id", "admin")
    payload = decode_token(token)
    assert payload.sub == "user-id"
    assert payload.tenant_id == "tenant-id"
    assert payload.role == "admin"
    assert payload.token_type == "access"


def test_refresh_token_type() -> None:
    token = create_refresh_token("user-id", "tenant-id", "user")
    payload = decode_token(token)
    assert payload.token_type == "refresh"
