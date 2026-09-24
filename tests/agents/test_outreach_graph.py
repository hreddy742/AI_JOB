from __future__ import annotations

import asyncio

import httpx

from agents import outreach_graph


def test_compliance_failure_blocks_sending(monkeypatch) -> None:
    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("ollama unavailable")

    monkeypatch.setattr(outreach_graph.httpx, "AsyncClient", FailingClient)
    state = {
        "contact": {"contact_name": "Taylor"},
        "job": {"company": "Example", "title": "Engineer"},
        "resume_summary": "Python engineer",
        "user_profile": {"first_name": "Casey", "last_name": "Smith"},
        "draft_text": "A professional outreach draft.",
        "compliance_report": {},
    }

    result = asyncio.run(outreach_graph.compliance_node(state))

    assert result["compliance_report"]["approved_to_send"] is False
    assert result["compliance_report"]["flags"] == ["compliance_review_unavailable"]

