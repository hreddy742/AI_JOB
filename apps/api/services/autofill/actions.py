"""Typed Playwright action wrappers for ATS automation stability."""

from __future__ import annotations

from typing import Any

from services.autofill.fuzzy import best_fuzzy_match

Target = Any


async def wait_for(target: Target, selector: str, *, timeout_ms: int = 5000) -> bool:
    try:
        await target.wait_for_selector(selector, timeout=timeout_ms)
        return True
    except Exception:
        return False


async def click(target: Target, selector: str, *, timeout_ms: int = 5000) -> bool:
    try:
        await target.locator(selector).first.click(timeout=timeout_ms)
        return True
    except Exception:
        return False


async def type_text(target: Target, selector: str, value: str, *, timeout_ms: int = 5000) -> bool:
    try:
        locator = target.locator(selector).first
        await locator.fill("")
        await locator.type(str(value), delay=35, timeout=timeout_ms)
        return True
    except Exception:
        return False


async def scroll(target: Target, selector: str = "body") -> bool:
    try:
        await target.locator(selector).first.scroll_into_view_if_needed(timeout=2000)
        return True
    except Exception:
        return False


async def extract(target: Target, selector: str, *, timeout_ms: int = 3000) -> str:
    try:
        text = await target.locator(selector).first.text_content(timeout=timeout_ms)
        return (text or "").strip()
    except Exception:
        return ""


async def select_option(target: Target, selector: str, value: str, *, timeout_ms: int = 5000) -> bool:
    try:
        locator = target.locator(selector).first
        candidate = str(value or "").strip()
        if not candidate:
            return False

        # Fast exact path first.
        try:
            await locator.select_option(label=candidate, timeout=timeout_ms)
            return True
        except Exception:
            pass

        try:
            await locator.select_option(value=candidate, timeout=timeout_ms)
            return True
        except Exception:
            pass

        # Fuzzy fallback using visible option labels.
        options = await locator.evaluate(
            "(el) => Array.from(el.options || []).map(o => ({label: (o.label || o.text || '').trim(), value: (o.value || '').trim()}))"
        )
        labels = [str(item.get("label") or "") for item in (options or []) if isinstance(item, dict)]
        match = best_fuzzy_match(candidate, labels)
        if match is None:
            return False

        selected_value = ""
        for item in (options or []):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "")
            if label == match.value:
                selected_value = str(item.get("value") or "")
                break

        if selected_value:
            await locator.select_option(value=selected_value, timeout=timeout_ms)
            return True
        await locator.select_option(label=match.value, timeout=timeout_ms)
        return True
    except Exception:
        return False


async def upload_file(target: Target, selector: str, path: str, *, timeout_ms: int = 5000) -> bool:
    try:
        locator = target.locator(selector).first
        await locator.set_input_files(path, timeout=timeout_ms)
        return True
    except Exception:
        return False
