"""Outreach draft and compliance graph."""

from __future__ import annotations

import json
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from core.config import settings


class OutreachState(TypedDict):
    """State for outreach generation and compliance checks."""

    contact: dict[str, Any]
    job: dict[str, Any] | None
    resume_summary: str
    user_profile: dict[str, Any]
    draft_text: str
    compliance_report: dict[str, Any]


class ComplianceOutput(BaseModel):
    """Compliance analyzer output schema."""

    score: float = Field(ge=0.0, le=1.0)
    flags: list[str] = []
    gdpr_risk: bool = False
    approved_to_send: bool = False


COMPLIANCE_PROMPT = """
You are a compliance officer reviewing an outreach message.
Check for:

Spam signals (urgency, over-promising, mass-blast feel)
Deceptive subject line
Missing sender identification
GDPR risk (EU-based contact based on company HQ)
CAN-SPAM compliance
Professionalism (no casual/aggressive language)

Score 0.0 to 1.0. Flag issues.
{"score": 0.85, "flags": [...], "gdpr_risk": false, "approved_to_send": true}
""".strip()


def _first_name(name: str | None) -> str:
    """Extract first name fallback for templates."""

    if not name:
        return "there"
    return name.strip().split()[0]


async def draft_node(state: OutreachState) -> OutreachState:
    """Build template-based outreach draft without hallucinations."""

    contact = state["contact"]
    job = state["job"] or {}

    first = _first_name(contact.get("name") or contact.get("contact_name"))
    company = contact.get("company") or job.get("company") or "your company"
    role = job.get("title") or "the role"
    specific_detail = "the role requirements"
    if job.get("description"):
        specific_detail = str(job["description"]).split(".")[0][:120]

    draft = (
        f"Hi {first},\n\n"
        f"I am reaching out regarding {role} at {company}. "
        f"I was interested in {specific_detail}. "
        "I would value any guidance you can share about the team and hiring process.\n\n"
        "Best regards,\n"
        f"{state['user_profile'].get('first_name', 'Candidate')} {state['user_profile'].get('last_name', '')}"
    ).strip()
    state["draft_text"] = draft
    return state


async def compliance_node(state: OutreachState) -> OutreachState:
    """Score draft for compliance and outreach safety."""

    default_report = {
        "score": 0.0,
        "flags": ["compliance_review_unavailable"],
        "gdpr_risk": False,
        "approved_to_send": False,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.REVIEWER_MODEL,
                    "messages": [
                        {"role": "system", "content": COMPLIANCE_PROMPT},
                        {"role": "user", "content": state["draft_text"]},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=45.0,
            )
            if resp.status_code != 200:
                state["compliance_report"] = default_report
                return state

            payload = resp.json()
            content = payload.get("message", {}).get("content", "{}")
            parsed = json.loads(content) if isinstance(content, str) else content
            report = ComplianceOutput.model_validate(parsed)
            state["compliance_report"] = report.model_dump()
            return state
    except Exception:
        state["compliance_report"] = default_report
        return state


graph = StateGraph(OutreachState)
graph.add_node("draft", draft_node)
graph.add_node("compliance", compliance_node)
graph.set_entry_point("draft")
graph.add_edge("draft", "compliance")
graph.add_edge("compliance", END)
compiled_outreach_graph = graph.compile()
