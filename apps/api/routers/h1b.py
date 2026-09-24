"""H1B explorer routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.h1b_sponsor import H1BSponsor

router = APIRouter(prefix="/h1b", tags=["h1b"])


def _serialize_sponsor(row: H1BSponsor) -> dict:
    return {
        "id": str(row.id),
        "company_name": row.company_name,
        "active_sponsor": bool(row.is_active_sponsor if row.is_active_sponsor is not None else row.active_sponsor),
        "lca_count_1yr": int(row.lca_last_1yr or row.lca_count_1yr or 0),
        "approval_rate": float(row.approval_rate or 0),
        "approved_count": int(row.approved_count or 0),
        "median_wage": float(row.median_wage_usd or row.median_wage or 0) if (row.median_wage_usd is not None or row.median_wage is not None) else None,
        "confidence_score": int(row.confidence_score or 0),
        "primary_state": row.primary_state,
        "lca_last_3yr": int(row.lca_last_3yr or 0),
        "source": "U.S. Department of Labor LCA Disclosure Data",
    }


@router.get("/company/{name}")
async def get_h1b_company(
    name: str,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return one company record by exact or normalized name."""

    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    term = name.strip().lower()
    row = (
        await db.execute(
            select(H1BSponsor)
            .where(
                or_(
                    H1BSponsor.company_normalized == term,
                    H1BSponsor.normalized_name == term,
                    H1BSponsor.company_name.ilike(name.strip()),
                )
            )
            .order_by(H1BSponsor.confidence_score.desc(), H1BSponsor.lca_last_1yr.desc(), H1BSponsor.lca_count_1yr.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    item = _serialize_sponsor(row) if row is not None else None
    return {"item": item, "results": [item] if item is not None else []}


@router.get("/search")
async def search_h1b_sponsors(
    q: str = Query(default="", min_length=1),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Search H1B sponsor aggregates."""

    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    term = q.strip().lower()
    rows = (
        await db.execute(
            select(H1BSponsor)
            .where(
                or_(
                    H1BSponsor.company_normalized.ilike(f"%{term}%"),
                    H1BSponsor.normalized_name.ilike(f"%{term}%"),
                    H1BSponsor.company_name.ilike(f"%{term}%"),
                )
            )
            .order_by(H1BSponsor.confidence_score.desc(), H1BSponsor.lca_last_1yr.desc(), H1BSponsor.lca_count_1yr.desc())
            .limit(30)
        )
    ).scalars().all()
    items = [_serialize_sponsor(row) for row in rows]
    return {"items": items, "results": items}
