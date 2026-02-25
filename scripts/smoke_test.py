"""Local API smoke test for APEX APPLY core flows."""

from __future__ import annotations

import json
import random
import re
import string
import time
import sys
from typing import Any

import requests

BASE = "http://localhost:8001"
MAILPIT_BASE = "http://localhost:8025"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _rand() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def _get_verification_token(email: str, timeout_seconds: int = 30) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        messages_resp = requests.get(f"{MAILPIT_BASE}/api/v1/messages", timeout=10)
        messages_resp.raise_for_status()
        messages = (messages_resp.json() or {}).get("messages", [])
        for message in messages:
            recipients = message.get("To") or []
            if not any(str(item.get("Address", "")).lower() == email.lower() for item in recipients):
                continue
            message_id = message.get("ID")
            if not message_id:
                continue
            detail_resp = requests.get(f"{MAILPIT_BASE}/api/v1/message/{message_id}", timeout=10)
            detail_resp.raise_for_status()
            html = (detail_resp.json() or {}).get("HTML", "")
            token_match = re.search(r"[?&]token=([A-Za-z0-9_\-]+)", html)
            if token_match:
                return token_match.group(1)
        time.sleep(1.0)
    raise RuntimeError("Verification email token not found in Mailpit")


def main() -> int:
    health = requests.get(f"{BASE}/health", timeout=15)
    _assert(health.status_code == 200, f"Health failed: {health.status_code}")

    suffix = _rand()
    email = f"smoke-{suffix}@example.com"
    register_payload = {
        "email": email,
        "password": "StrongPass123!",
        "full_name": "Smoke Tester",
    }
    reg = requests.post(f"{BASE}/auth/register", json=register_payload, timeout=20)
    _assert(reg.status_code in {200, 201}, f"Register failed: {reg.status_code} {reg.text}")
    token = _get_verification_token(email)
    verify = requests.post(f"{BASE}/auth/verify-email", json={"token": token}, timeout=20)
    _assert(verify.status_code == 200, f"Verify email failed: {verify.status_code} {verify.text}")
    access_token = verify.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    profile_payload = {
        "first_name": "Smoke",
        "last_name": "Tester",
        "work_authorization": "other",
        "target_roles": ["Software Engineer"],
        "target_locations": ["Remote"],
    }
    prof = requests.post(f"{BASE}/profile", json=profile_payload, headers=headers, timeout=20)
    _assert(prof.status_code in {200, 201}, f"Profile create failed: {prof.status_code} {prof.text}")

    search = requests.get(f"{BASE}/jobs/search?q=python&page=1&page_size=5", headers=headers, timeout=20)
    _assert(search.status_code == 200, f"Job search failed: {search.status_code} {search.text}")

    print(json.dumps({
        "health": "ok",
        "register": "ok",
        "verify_email": "ok",
        "profile": "ok",
        "job_search": "ok",
        "items": len(search.json().get("items", [])),
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        raise SystemExit(1)
