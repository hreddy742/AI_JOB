"""Browser session wrapper for Browser Agent V1."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Protocol


class BrowserPage(Protocol):
    async def goto(self, url: str, **kwargs: Any) -> Any: ...
    async def title(self) -> str: ...
    async def evaluate(self, script: str, arg: Any | None = None) -> Any: ...
    async def screenshot(self, **kwargs: Any) -> bytes: ...
    def locator(self, selector: str) -> Any: ...


class BrowserSession:
    """Thin wrapper around a Playwright page and lifecycle."""

    def __init__(self, playwright: Any, browser: Any, context: Any, page: BrowserPage):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page

    async def close(self) -> None:
        if self.context is not None:
            await self.context.close()
        if self.browser is not None:
            await self.browser.close()
        if self.playwright is not None:
            await self.playwright.stop()


@asynccontextmanager
async def open_browser_session(headless: bool = True):
    """Open a Playwright Chromium session for the isolated browser agent."""

    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
    page = await context.new_page()
    session = BrowserSession(playwright, browser, context, page)
    try:
        yield session
    finally:
        await session.close()
