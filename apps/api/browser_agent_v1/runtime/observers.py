"""Observer helpers for Browser Agent V1 runtime."""

from __future__ import annotations

from typing import Any


async def capture_screenshot_bytes(page: Any) -> bytes:
    """Capture a PNG screenshot for audit artifacts."""

    return await page.screenshot(type="png", full_page=True)


async def capture_dom_snapshot(page: Any) -> str:
    """Capture the current DOM HTML for post-run debugging and replay."""

    return str(await page.content())
