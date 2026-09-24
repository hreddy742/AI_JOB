"""Tenant-scoped runtime feature flags."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import settings
from core.redis import get_redis

_RERANK_KEY_PREFIX = "flags:rerank"
_BROWSER_AGENT_KEY_PREFIX = "flags:browser_agent_v1"
_CACHE_TTL_SECONDS = 30
_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}


def _cache_key(prefix: str, tenant_id: str, user_id: str | None = None) -> str:
    if user_id:
        return f"{prefix}:{tenant_id}:{user_id}"
    return f"{prefix}:{tenant_id}"


def _redis_key(prefix: str, tenant_id: str) -> str:
    return f"{prefix}:{tenant_id}"


def _parse_flag(raw: Any) -> bool | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_percent(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return max(0, min(100, int(raw)))
    except Exception:
        return None


def _parse_allowlist(raw: str) -> set[str]:
    return {item.strip().lower() for item in str(raw or "").split(",") if item.strip()}


def _stable_rollout_bucket(tenant_id: str, user_id: str | None) -> int:
    seed = f"{tenant_id}:{user_id or 'anonymous'}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    return int(digest[:8], 16) % 100


async def get_tenant_rerank_state(tenant_id: str) -> dict[str, bool | None]:
    """Return default, override, and effective rerank enabled state for tenant."""

    now = datetime.now(UTC)
    cached = _cache.get(_cache_key(_RERANK_KEY_PREFIX, tenant_id))
    if cached and cached[0] > now:
        return dict(cached[1])

    override: bool | None = None
    try:
        raw = await get_redis().get(_redis_key(_RERANK_KEY_PREFIX, tenant_id))
        override = _parse_flag(raw)
    except Exception:
        override = None

    payload = {
        "default_enabled": bool(settings.ENABLE_RERANKING),
        "tenant_override": override,
        "effective_enabled": bool(settings.ENABLE_RERANKING) if override is None else bool(override),
    }
    _cache[_cache_key(_RERANK_KEY_PREFIX, tenant_id)] = (now + timedelta(seconds=_CACHE_TTL_SECONDS), payload)
    return dict(payload)


async def set_tenant_rerank_override(tenant_id: str, enabled: bool | None) -> dict[str, bool | None]:
    """Set or clear tenant override for reranking."""

    try:
        redis = get_redis()
        if enabled is None:
            await redis.delete(_redis_key(_RERANK_KEY_PREFIX, tenant_id))
        else:
            await redis.set(_redis_key(_RERANK_KEY_PREFIX, tenant_id), "1" if enabled else "0")
    except Exception:
        pass

    _cache.pop(_cache_key(_RERANK_KEY_PREFIX, tenant_id), None)
    return await get_tenant_rerank_state(tenant_id)


async def get_tenant_browser_agent_v1_state(
    tenant_id: str,
    *,
    user_id: str | None = None,
    user_email: str | None = None,
    user_role: str | None = None,
    user_opt_in: bool = False,
    provider: str | None = None,
) -> dict[str, Any]:
    """Return deterministic browser-agent rollout policy for one tenant/user."""

    now = datetime.now(UTC)
    cache_id = _cache_key(_BROWSER_AGENT_KEY_PREFIX, tenant_id, user_id)
    cached = _cache.get(cache_id)
    if cached and cached[0] > now and not user_opt_in:
        return dict(cached[1])

    allowlist = _parse_allowlist(settings.BROWSER_AGENT_V1_INTERNAL_ALLOWLIST)
    disabled_providers = _parse_allowlist(settings.BROWSER_AGENT_V1_DISABLED_PROVIDERS)
    pilot_providers = _parse_allowlist(settings.BROWSER_AGENT_V1_PILOT_PROVIDERS)
    pilot_tenants = _parse_allowlist(settings.BROWSER_AGENT_V1_PILOT_TENANTS)
    normalized_user_id = str(user_id or "").strip().lower()
    normalized_email = str(user_email or "").strip().lower()
    normalized_provider = str(provider or "").strip().lower() or "generic"
    normalized_tenant_id = str(tenant_id or "").strip().lower()
    internal_allowlisted = bool(
        (user_role or "").strip().lower() == "admin"
        or normalized_user_id in allowlist
        or normalized_email in allowlist
    )

    tenant_override: dict[str, Any] | None = None
    try:
        raw = await get_redis().get(_redis_key(_BROWSER_AGENT_KEY_PREFIX, tenant_id))
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                tenant_override = parsed
    except Exception:
        tenant_override = None

    override_enabled = _parse_flag((tenant_override or {}).get("enabled"))
    override_shadow = _parse_flag((tenant_override or {}).get("shadow_mode"))
    override_percent = _parse_percent((tenant_override or {}).get("percent_rollout"))
    override_internal_only = _parse_flag((tenant_override or {}).get("internal_only"))
    override_disabled_providers_raw = (tenant_override or {}).get("disabled_providers")
    override_disabled_providers = (
        {str(item).strip().lower() for item in override_disabled_providers_raw if str(item).strip()}
        if isinstance(override_disabled_providers_raw, list)
        else set()
    )

    subsystem_enabled = bool(settings.ENABLE_BROWSER_AGENT_V1)
    default_enabled = bool(settings.BROWSER_AGENT_V1_ENABLED)
    percent_rollout = (
        override_percent if override_percent is not None else max(0, min(100, int(settings.BROWSER_AGENT_V1_PERCENT_ROLLOUT)))
    )
    pilot_percent_rollout = max(0, min(100, int(settings.BROWSER_AGENT_V1_PILOT_PERCENT_ROLLOUT)))
    rollout_bucket = _stable_rollout_bucket(tenant_id, user_id)
    within_percent_rollout = rollout_bucket < percent_rollout
    within_pilot_rollout = rollout_bucket < pilot_percent_rollout
    shadow_mode = (
        bool(settings.BROWSER_AGENT_V1_SHADOW_MODE) if override_shadow is None else bool(override_shadow)
    )
    internal_only = bool(override_internal_only) if override_internal_only is not None else False
    enabled_base = default_enabled if override_enabled is None else bool(override_enabled)
    effective_disabled_providers = disabled_providers | override_disabled_providers
    provider_disabled = bool(normalized_provider and normalized_provider in effective_disabled_providers)
    browser_primary_enabled = bool(settings.BROWSER_AGENT_V1_BROWSER_PRIMARY_ENABLED)
    pilot_provider_allowed = bool(normalized_provider and normalized_provider in pilot_providers)
    pilot_tenant_allowed = not pilot_tenants or normalized_tenant_id in pilot_tenants
    browser_primary_candidate = (
        browser_primary_enabled
        and pilot_provider_allowed
        and pilot_tenant_allowed
        and within_pilot_rollout
        and not provider_disabled
    )
    eligible_for_browser_agent = subsystem_enabled and enabled_base and (
        internal_allowlisted or not internal_only or within_percent_rollout
    )
    effective_enabled = (
        eligible_for_browser_agent
        and not provider_disabled
        and (internal_allowlisted or within_percent_rollout or user_opt_in or not internal_only)
    )
    offer_browser_agent = effective_enabled and not shadow_mode
    run_shadow = subsystem_enabled and shadow_mode and not provider_disabled and (enabled_base or internal_allowlisted or within_percent_rollout)
    prefer_browser_agent_primary = bool(browser_primary_candidate and not shadow_mode)

    effective_mode = "legacy_only"
    if prefer_browser_agent_primary:
        effective_mode = "browser_primary_pilot"
    elif run_shadow:
        effective_mode = "shadow"
    elif offer_browser_agent and user_opt_in:
        effective_mode = "beta_opt_in"
    elif offer_browser_agent:
        effective_mode = "opt_in"
    elif internal_only and not internal_allowlisted:
        effective_mode = "internal_only"

    payload: dict[str, Any] = {
        "subsystem_enabled": subsystem_enabled,
        "default_enabled": default_enabled,
        "tenant_override": tenant_override,
        "shadow_mode": shadow_mode,
        "percent_rollout": percent_rollout,
        "rollout_bucket": rollout_bucket,
        "within_percent_rollout": within_percent_rollout,
        "pilot_percent_rollout": pilot_percent_rollout,
        "within_pilot_rollout": within_pilot_rollout,
        "internal_only": internal_only,
        "internal_allowlisted": internal_allowlisted,
        "disabled_providers": sorted(effective_disabled_providers),
        "provider": normalized_provider or None,
        "provider_disabled": provider_disabled,
        "browser_primary_enabled": browser_primary_enabled,
        "pilot_provider_allowed": pilot_provider_allowed,
        "pilot_tenant_allowed": pilot_tenant_allowed,
        "prefer_browser_agent_primary": prefer_browser_agent_primary,
        "user_opt_in": bool(user_opt_in),
        "effective_enabled": effective_enabled,
        "offer_browser_agent": offer_browser_agent,
        "run_shadow": run_shadow,
        "effective_mode": effective_mode,
        "decision_reason": (
            "subsystem_disabled"
            if not subsystem_enabled
            else "provider_disabled"
            if provider_disabled
            else "browser_primary_pilot"
            if prefer_browser_agent_primary
            else "shadow_mode"
            if run_shadow
            else "eligible"
            if offer_browser_agent
            else "internal_only_blocked"
            if internal_only and not internal_allowlisted
            else "rollout_not_enabled"
        ),
    }
    _cache[cache_id] = (now + timedelta(seconds=_CACHE_TTL_SECONDS), payload)
    return dict(payload)


async def set_tenant_browser_agent_v1_override(
    tenant_id: str,
    *,
    enabled: bool | None = None,
    shadow_mode: bool | None = None,
    percent_rollout: int | None = None,
    internal_only: bool | None = None,
    disabled_providers: list[str] | None = None,
) -> dict[str, Any]:
    """Set or clear tenant override for browser-agent rollout."""

    payload = {
        "enabled": enabled,
        "shadow_mode": shadow_mode,
        "percent_rollout": _parse_percent(percent_rollout),
        "internal_only": internal_only,
        "disabled_providers": (
            [str(item).strip().lower() for item in disabled_providers if str(item).strip()]
            if disabled_providers is not None
            else None
        ),
    }
    try:
        redis = get_redis()
        if all(value is None for value in payload.values()):
            await redis.delete(_redis_key(_BROWSER_AGENT_KEY_PREFIX, tenant_id))
        else:
            await redis.set(_redis_key(_BROWSER_AGENT_KEY_PREFIX, tenant_id), json.dumps(payload))
    except Exception:
        pass

    keys_to_clear = [key for key in _cache if key.startswith(f"{_BROWSER_AGENT_KEY_PREFIX}:{tenant_id}")]
    for key in keys_to_clear:
        _cache.pop(key, None)
    return await get_tenant_browser_agent_v1_state(tenant_id)
