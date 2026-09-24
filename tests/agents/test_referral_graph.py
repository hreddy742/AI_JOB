from __future__ import annotations

import asyncio

import httpx

from agents import referral_graph


def test_company_analysis_failure_does_not_invent_company_metadata(monkeypatch) -> None:
    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("ollama unavailable")

    monkeypatch.setattr(referral_graph.httpx, "AsyncClient", FailingClient)

    result = asyncio.run(referral_graph._call_company_analyzer("Example Corp"))

    assert result == {"company_domain": "", "github_org": "", "email_pattern": ""}
