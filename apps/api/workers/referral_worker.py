"""Referral worker graph runner."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from agents.referral_graph import ReferralState, compiled_referral_graph
from core.config import settings
from db.models.referral import ReferralSuggestion
from services.referral_service import get_job, get_user_profile


async def discover_referrals_for_job(ctx: dict[str, Any], job_id: str, user_id: str) -> dict[str, Any]:
    """Run referral discovery graph and persist top contacts."""

    # COMPLIANCE: All contacts stored with is_verified=False.
    # inferred_email is labeled as unverified in all API responses.
    # Users are warned in UI before any outreach action.
    db = ctx["db"]
    tenant_id: UUID = ctx["tenant_id"]

    job = await get_job(job_id, db, tenant_id)
    user_profile = await get_user_profile(user_id, db, tenant_id)

    initial_state: ReferralState = {
        "user_id": user_id,
        "job_id": job_id,
        "company": job.company,
        "company_domain": "",
        "company_github_org": "",
        "target_roles": user_profile.target_roles or [],
        "discovered_contacts": [],
        "email_pattern": "firstname.lastname",
        "scored_contacts": [],
        "error": None,
    }

    result = await compiled_referral_graph.ainvoke(initial_state)

    top_contacts = sorted(
        result["scored_contacts"],
        key=lambda x: float(x.get("confidence_score") or 0.0),
        reverse=True,
    )[: settings.REFERRAL_MAX_PER_JOB]

    for contact in top_contacts:
        suggestion = ReferralSuggestion(
            user_id=UUID(user_id),
            tenant_id=tenant_id,
            job_id=UUID(job_id),
            company=job.company,
            contact_name=contact.get("contact_name"),
            contact_title=contact.get("contact_title") or "Bio hint - not verified",
            contact_source=contact.get("contact_source"),
            contact_url=contact.get("contact_url"),
            inferred_email=contact.get("inferred_email"),
            email_pattern=contact.get("email_pattern"),
            confidence_score=float(contact.get("confidence_score") or 0.0),
            discovery_method=contact.get("discovery_method"),
            is_verified=False,
            status="pending",
        )
        db.add(suggestion)

    await db.commit()
    return {"job_id": job_id, "contacts_found": len(top_contacts)}


class WorkerSettings:
    """ARQ worker settings for referral discovery."""

    functions = [discover_referrals_for_job]
