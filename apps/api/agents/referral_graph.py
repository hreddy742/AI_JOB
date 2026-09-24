"""Referral Discovery Engine graph."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from core.config import settings
GITHUB_API_BASE = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class ReferralState(TypedDict):
    """State used by referral discovery graph."""

    user_id: str
    job_id: str
    company: str
    company_domain: str
    company_github_org: str
    target_roles: list[str]
    discovered_contacts: list[dict[str, Any]]
    email_pattern: str
    scored_contacts: list[dict[str, Any]]
    error: Optional[str]


COMPANY_ANALYZER_PROMPT = """
Given a company name, determine:

company_domain: the company's primary email domain (e.g. stripe.com)
github_org: the company's GitHub organization name if publicly known
(e.g. for "Stripe" - "stripe", for "Unknown startup" - "")
email_pattern: most likely email format, choose from:
firstname.lastname | firstnamelastname | firstname | f.lastname

Respond with JSON only:
{"company_domain": "stripe.com", "github_org": "stripe", "email_pattern": "firstname.lastname"}
If you don't know the company, use empty strings for github_org.
""".strip()


async def _call_company_analyzer(company: str) -> dict[str, str]:
    """Infer company metadata via lightweight referral model."""

    fallback = {
        "company_domain": "",
        "github_org": "",
        "email_pattern": "",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.REFERRAL_MODEL,
                    "messages": [
                        {"role": "system", "content": COMPANY_ANALYZER_PROMPT},
                        {"role": "user", "content": company},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=45.0,
            )
            if resp.status_code != 200:
                return fallback
            payload = resp.json()
            content = payload.get("message", {}).get("content", "{}")
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, dict):
                return fallback
            return {
                "company_domain": str(parsed.get("company_domain") or ""),
                "github_org": str(parsed.get("github_org") or ""),
                "email_pattern": str(parsed.get("email_pattern") or ""),
            }
    except (httpx.HTTPError, json.JSONDecodeError):
        return fallback


async def discover_github_contacts(
    org: str,
    target_roles: list[str],
    max_results: int = 30,
) -> list[dict[str, Any]]:
    """Discover candidate contacts from GitHub org members."""

    if not org:
        return []

    async with httpx.AsyncClient(headers=GITHUB_HEADERS) as client:
        members_resp = await client.get(
            f"{GITHUB_API_BASE}/orgs/{org}/members",
            params={"per_page": max_results, "type": "member"},
        )
        if members_resp.status_code != 200:
            return []

        members = members_resp.json()
        if not isinstance(members, list):
            return []

        contacts: list[dict[str, Any]] = []
        role_keywords = [role.lower() for role in target_roles] + ["engineer", "developer", "manager", "recruiter"]

        for member in members[:max_results]:
            if not isinstance(member, dict) or not member.get("login"):
                continue
            await asyncio.sleep(0.5)
            user_resp = await client.get(f"{GITHUB_API_BASE}/users/{member['login']}")
            if user_resp.status_code != 200:
                continue

            user = user_resp.json()
            if not isinstance(user, dict):
                continue
            name = str(user.get("name") or user.get("login") or "")
            bio = str(user.get("bio") or "")

            is_relevant = any(keyword in bio.lower() for keyword in role_keywords)
            if is_relevant or not target_roles:
                contacts.append(
                    {
                        "contact_name": name,
                        "contact_title": None,
                        "title_guess": bio[:100],
                        "contact_source": "github",
                        "contact_url": user.get("html_url"),
                        "github_username": user.get("login"),
                        "public_email": user.get("email"),
                        "is_verified": False,
                        "confidence_score": 0.6 if is_relevant else 0.3,
                        "discovery_method": "github_api",
                    }
                )

        return contacts


def infer_email(name: str, domain: str, pattern: str) -> str | None:
    """Infer likely email from name/domain and selected pattern."""

    if not name or not domain:
        return None

    parts = [piece for piece in name.lower().strip().split() if piece]
    if len(parts) < 1:
        return None

    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    patterns: dict[str, str | None] = {
        "firstname.lastname": f"{first}.{last}@{domain}" if last else None,
        "firstnamelastname": f"{first}{last}@{domain}" if last else None,
        "firstname": f"{first}@{domain}",
        "f.lastname": f"{first[0]}.{last}@{domain}" if last else None,
    }
    return patterns.get(pattern)


def score_referral_contact(contact: dict[str, Any], job: object | None) -> float:
    """Score discovered referral usefulness between 0.0 and 1.0."""

    score = 0.0
    if contact.get("public_email"):
        score += 0.3
    title_guess = str(contact.get("title_guess") or "").lower()
    if any(keyword in title_guess for keyword in ["engineer", "developer", "manager", "lead", "staff", "recruiter"]):
        score += 0.2
    if contact.get("contact_source") == "github":
        score += 0.2
    name = str(contact.get("contact_name") or "")
    if len(name.split()) >= 2:
        score += 0.1
    location_city = getattr(job, "location_city", None) if job is not None else None
    if location_city and str(location_city).lower() in str(contact.get("location") or "").lower():
        score += 0.2
    return round(min(score, 1.0), 2)


async def company_analyzer_node(state: ReferralState) -> ReferralState:
    """Analyze company metadata needed for discovery and inference."""

    result = await _call_company_analyzer(state["company"])
    state["company_domain"] = result["company_domain"]
    state["company_github_org"] = result["github_org"]
    state["email_pattern"] = result["email_pattern"]
    return state


async def github_discovery_node(state: ReferralState) -> ReferralState:
    """Discover candidate contacts from GitHub org memberships."""

    contacts = await discover_github_contacts(
        org=state["company_github_org"],
        target_roles=state["target_roles"],
        max_results=30,
    )
    state["discovered_contacts"] = contacts
    return state


async def email_inference_node(state: ReferralState) -> ReferralState:
    """Infer unverified emails from discovered contact names."""

    enriched: list[dict[str, Any]] = []
    for contact in state["discovered_contacts"]:
        inferred = infer_email(
            name=str(contact.get("contact_name") or ""),
            domain=state["company_domain"],
            pattern=state["email_pattern"],
        )
        new_contact = dict(contact)
        new_contact["inferred_email"] = inferred
        new_contact["email_pattern"] = state["email_pattern"]
        new_contact["is_verified"] = False
        enriched.append(new_contact)
    state["discovered_contacts"] = enriched
    return state


async def scorer_node(state: ReferralState) -> ReferralState:
    """Score discovered contacts and keep normalized output list."""

    scored: list[dict[str, Any]] = []
    for contact in state["discovered_contacts"]:
        score = score_referral_contact(contact, None)
        scored.append(
            {
                "contact_name": contact.get("contact_name"),
                "contact_title": contact.get("contact_title"),
                "contact_source": contact.get("contact_source"),
                "contact_url": contact.get("contact_url"),
                "inferred_email": contact.get("inferred_email"),
                "email_pattern": contact.get("email_pattern"),
                "confidence_score": score,
                "discovery_method": contact.get("discovery_method") or "github_api",
                "is_verified": False,
            }
        )
    state["scored_contacts"] = scored
    return state


async def store_node(state: ReferralState) -> ReferralState:
    """Finalize state payload for persistence by worker."""

    state["scored_contacts"] = sorted(state["scored_contacts"], key=lambda item: float(item.get("confidence_score") or 0.0), reverse=True)
    return state


referral_graph = StateGraph(ReferralState)
referral_graph.add_node("company_analyzer", company_analyzer_node)
referral_graph.add_node("github_discovery", github_discovery_node)
referral_graph.add_node("email_inference", email_inference_node)
referral_graph.add_node("scorer", scorer_node)
referral_graph.add_node("store", store_node)
referral_graph.set_entry_point("company_analyzer")
referral_graph.add_edge("company_analyzer", "github_discovery")
referral_graph.add_edge("github_discovery", "email_inference")
referral_graph.add_edge("email_inference", "scorer")
referral_graph.add_edge("scorer", "store")
referral_graph.add_edge("store", END)
compiled_referral_graph = referral_graph.compile()
