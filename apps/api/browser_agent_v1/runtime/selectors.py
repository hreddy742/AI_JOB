"""Selector fallback and persistence helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.browser_agent_selector_memory import BrowserAgentSelectorMemory

_DOM_FALLBACK_SCRIPT = """
(needle) => {
  const normalizedNeedle = String(needle || '').trim().toLowerCase();
  const nodes = Array.from(document.querySelectorAll('button, a, input, textarea, select, label, [role="button"]'));
  const ranked = nodes.map((node) => {
    const id = node.getAttribute('id') || '';
    const name = node.getAttribute('name') || '';
    const aria = node.getAttribute('aria-label') || '';
    const text = (node.textContent || node.getAttribute('value') || '').trim();
    const haystack = `${id} ${name} ${aria} ${text}`.toLowerCase();
    let selector = '';
    if (id) selector = `#${id}`;
    else if (name) selector = `${(node.tagName || '').toLowerCase()}[name="${name.replace(/"/g, '\\"')}"]`;
    else selector = (node.tagName || '').toLowerCase();
    let score = 0;
    if (normalizedNeedle && haystack.includes(normalizedNeedle)) score += 10;
    if (normalizedNeedle && text.toLowerCase().includes(normalizedNeedle)) score += 20;
    if (selector && normalizedNeedle && selector.toLowerCase().includes(normalizedNeedle)) score += 5;
    return {selector, score};
  }).filter((item) => item.selector).sort((a, b) => b.score - a.score);
  return ranked.slice(0, 5).map((item) => item.selector);
}
"""


async def ordered_selector_candidates(
    db: AsyncSession | None,
    *,
    tenant_id: UUID | None,
    provider: str,
    action_kind: str,
    selectors: list[str],
) -> list[str]:
    """Return selectors ordered by observed success history first, then defaults."""

    normalized = [str(item or "").strip() for item in selectors if str(item or "").strip()]
    if db is None or tenant_id is None or not normalized:
        return normalized
    rows = (
        await db.execute(
            select(BrowserAgentSelectorMemory).where(
                BrowserAgentSelectorMemory.tenant_id == tenant_id,
                BrowserAgentSelectorMemory.provider == str(provider or "generic"),
                BrowserAgentSelectorMemory.action_kind == action_kind,
                BrowserAgentSelectorMemory.selector.in_(normalized),
            )
        )
    ).scalars().all()
    rank = {
        row.selector: ((int(row.success_count or 0) - int(row.failure_count or 0)), int(row.success_count or 0))
        for row in rows
    }
    return sorted(normalized, key=lambda item: (-(rank.get(item, (0, 0))[0]), -(rank.get(item, (0, 0))[1]), normalized.index(item)))


async def discover_similar_selectors(page: Any, *, hint: str) -> list[str]:
    """Return lightweight DOM-derived fallback selectors."""

    try:
        rows = await page.evaluate(_DOM_FALLBACK_SCRIPT, hint)
    except Exception:
        return []
    return [str(item) for item in rows if str(item or "").strip()]


async def record_selector_result(
    db: AsyncSession | None,
    *,
    tenant_id: UUID | None,
    provider: str,
    action_kind: str,
    selector: str,
    ok: bool,
) -> None:
    """Persist selector success/failure counters."""

    if db is None or tenant_id is None or not selector:
        return
    row = (
        await db.execute(
            select(BrowserAgentSelectorMemory).where(
                BrowserAgentSelectorMemory.tenant_id == tenant_id,
                BrowserAgentSelectorMemory.provider == str(provider or "generic"),
                BrowserAgentSelectorMemory.action_kind == action_kind,
                BrowserAgentSelectorMemory.selector == selector,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = BrowserAgentSelectorMemory(
            tenant_id=tenant_id,
            provider=str(provider or "generic"),
            action_kind=action_kind,
            selector=selector,
            success_count=1 if ok else 0,
            failure_count=0 if ok else 1,
            last_status="success" if ok else "failed",
        )
        db.add(row)
        return
    if ok:
        row.success_count = int(row.success_count or 0) + 1
        row.last_status = "success"
    else:
        row.failure_count = int(row.failure_count or 0) + 1
        row.last_status = "failed"
