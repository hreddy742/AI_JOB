"""Deterministic browser actions for Browser Agent V1."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from services.autofill.actions import click, select_option, type_text, upload_file, wait_for
from sqlalchemy.ext.asyncio import AsyncSession

from browser_agent_v1.runtime.selectors import discover_similar_selectors, ordered_selector_candidates, record_selector_result


async def _upload_confirmation_state(
    page: Any,
    *,
    selector: str,
    expected_filename: str,
    confirmation_selectors: list[str],
    confirmation_timeout_ms: int,
) -> dict[str, Any]:
    file_names: list[str] = []
    input_has_file = False
    try:
        file_names = await page.locator(selector).first.evaluate(
            "(el) => Array.from(el.files || []).map((file) => String(file.name || '').trim()).filter(Boolean)"
        )
        input_has_file = bool(file_names)
    except Exception:
        file_names = []
        input_has_file = False

    normalized_expected = expected_filename.lower().strip()
    filename_visible = False
    if normalized_expected:
        try:
            body_text = await page.locator("body").first.text_content(timeout=confirmation_timeout_ms)
            filename_visible = normalized_expected in str(body_text or "").lower()
        except Exception:
            filename_visible = False

    provider_marker_visible = False
    for confirmation_selector in confirmation_selectors:
        try:
            visible = await page.locator(str(confirmation_selector)).first.is_visible(timeout=confirmation_timeout_ms)
        except Exception:
            visible = False
        if visible:
            provider_marker_visible = True
            break

    upload_confirmed = input_has_file and (provider_marker_visible or filename_visible or not confirmation_selectors)
    return {
        "upload_confirmed": upload_confirmed,
        "input_has_file": input_has_file,
        "input_file_names": file_names,
        "filename_visible": filename_visible,
        "provider_marker_visible": provider_marker_visible,
    }


async def _selector_attempts(
    page: Any,
    *,
    kind: str,
    payload: dict[str, Any],
    db: AsyncSession | None,
    tenant_id: UUID | None,
    provider: str,
) -> dict[str, Any]:
    selectors = payload.get("selectors") or [payload.get("selector") or ""]
    ordered = await ordered_selector_candidates(
        db,
        tenant_id=tenant_id,
        provider=provider,
        action_kind=kind,
        selectors=[str(item) for item in selectors],
    )
    hint = str(payload.get("hint") or payload.get("selector") or payload.get("label") or "").strip()
    if hint:
        for discovered in await discover_similar_selectors(page, hint=hint):
            if discovered not in ordered:
                ordered.append(discovered)

    attempts: list[dict[str, Any]] = []
    for selector in ordered:
        ok = False
        if kind == "click":
            ok = await click(page, selector, timeout_ms=int(payload.get("timeout_ms") or 5000))
        elif kind == "type":
            ok = await type_text(page, selector, str(payload.get("value") or ""), timeout_ms=int(payload.get("timeout_ms") or 5000))
        elif kind == "select":
            ok = await select_option(page, selector, str(payload.get("value") or ""), timeout_ms=int(payload.get("timeout_ms") or 5000))
        elif kind == "upload":
            ok = await upload_file(page, selector, str(payload.get("path") or ""), timeout_ms=int(payload.get("timeout_ms") or 5000))
        elif kind == "wait_for":
            ok = await wait_for(page, selector, timeout_ms=int(payload.get("timeout_ms") or 5000))
        attempts.append({"selector": selector, "ok": ok})
        await record_selector_result(db, tenant_id=tenant_id, provider=provider, action_kind=kind, selector=selector, ok=ok)
        if ok:
            return {"ok": True, "selector": selector, "attempts": attempts, "fallback_used": selector != ordered[0]}
    return {"ok": False, "selector": ordered[0] if ordered else "", "attempts": attempts, "fallback_used": len(attempts) > 1}


async def execute_action(
    page: Any,
    kind: str,
    payload: dict[str, Any],
    *,
    db: AsyncSession | None = None,
    tenant_id: UUID | None = None,
    provider: str = "generic",
) -> dict[str, Any]:
    """Execute a deterministic browser action and return a structured result."""

    if kind == "navigate":
        url = str(payload.get("url") or "").strip()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        return {"ok": True, "navigated_to": url}

    if kind == "click":
        return await _selector_attempts(page, kind="click", payload=payload, db=db, tenant_id=tenant_id, provider=provider)

    if kind == "check":
        selector = str(payload.get("selector") or "").strip()
        try:
            await page.locator(selector).first.check(timeout=int(payload.get("timeout_ms") or 5000))
            return {"ok": True, "selector": selector}
        except Exception:
            return {"ok": False, "selector": selector}

    if kind == "type":
        return await _selector_attempts(page, kind="type", payload=payload, db=db, tenant_id=tenant_id, provider=provider)

    if kind == "select":
        return await _selector_attempts(page, kind="select", payload=payload, db=db, tenant_id=tenant_id, provider=provider)

    if kind == "upload":
        result = await _selector_attempts(page, kind="upload", payload=payload, db=db, tenant_id=tenant_id, provider=provider)
        if result.get("ok"):
            expected_filename = Path(str(payload.get("path") or "")).name
            confirmation = await _upload_confirmation_state(
                page,
                selector=str(result.get("selector") or payload.get("selector") or ""),
                expected_filename=expected_filename,
                confirmation_selectors=[str(item) for item in (payload.get("confirmation_selectors") or []) if str(item).strip()],
                confirmation_timeout_ms=int(payload.get("confirmation_timeout_ms") or payload.get("timeout_ms") or 3000),
            )
            result.update(confirmation)
            if not result.get("upload_confirmed"):
                result["ok"] = False
                result["reason"] = "upload_confirmation_uncertain"
        return result

    if kind == "wait_for":
        return await _selector_attempts(page, kind="wait_for", payload=payload, db=db, tenant_id=tenant_id, provider=provider)

    raise ValueError(f"Unsupported browser action: {kind}")
