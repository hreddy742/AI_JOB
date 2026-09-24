"""PostgreSQL pgvector query helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls
from db.session import AsyncSessionFactory
from services.embeddings import embed_passage


def _vector_literal(embedding: list[float]) -> str:
    """Serialize embedding to pgvector literal."""

    return "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"


async def search_similar_jobs(
    query_embedding: list[float],
    tenant_id: str | UUID,
    limit: int = 50,
    filters: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """Search jobs by cosine similarity using pgvector."""

    if not tenant_id:
        raise ValueError("tenant_id is required for vector search")
    tenant_id_str = str(tenant_id)
    where_clauses = ["tenant_id = CAST(:tenant_id AS uuid)", "embedding IS NOT NULL", "is_active = TRUE"]
    params: dict[str, Any] = {"tenant_id": tenant_id_str, "embedding": _vector_literal(query_embedding), "limit": int(limit)}

    if filters:
        if filters.get("remote") is True:
            where_clauses.append("remote = TRUE")
        if filters.get("sponsorship_min") is not None:
            where_clauses.append("(sponsorship_status != 'no_sponsor')")
        if filters.get("location_city"):
            where_clauses.append("location_city ILIKE :location_city")
            params["location_city"] = f"%{str(filters['location_city']).strip()}%"
        if filters.get("salary_min") is not None:
            where_clauses.append("(salary_max IS NULL OR salary_max >= :salary_min)")
            params["salary_min"] = float(filters["salary_min"])

    sql = text(
        f"""
        SELECT
            id, title, company, location_city, location_state, location_country, remote,
            sponsorship_status, sponsorship_confidence, sponsorship_score,
            salary_min, salary_max, source, url,
            1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM jobs
        WHERE {' AND '.join(where_clauses)}
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )
    if db is not None:
        rows = (await db.execute(sql, params)).mappings().all()
        return [dict(row) for row in rows]
    async with AsyncSessionFactory() as session:
        await apply_tenant_rls(session, UUID(tenant_id_str))
        rows = (await session.execute(sql, params)).mappings().all()
    return [dict(row) for row in rows]


async def find_matching_users(
    job_embedding: list[float],
    tenant_id: str | UUID,
    top_k: int = 200,
    min_similarity: float = 0.72,
    db: AsyncSession | None = None,
) -> list[str]:
    """Find users with similar resume embeddings for alerting."""

    if not tenant_id:
        raise ValueError("tenant_id is required for vector search")
    tenant_id_str = str(tenant_id)
    sql = text(
        """
        SELECT user_id, 1 - (resume_embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM user_profiles
        WHERE tenant_id = CAST(:tenant_id AS uuid)
          AND alerts_active = TRUE
          AND resume_embedding IS NOT NULL
          AND 1 - (resume_embedding <=> CAST(:embedding AS vector)) > :min_sim
        ORDER BY resume_embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    params = {
        "tenant_id": tenant_id_str,
        "embedding": _vector_literal(job_embedding),
        "min_sim": float(min_similarity),
        "top_k": int(top_k),
    }
    if db is not None:
        rows = (await db.execute(sql, params)).all()
        return [str(row[0]) for row in rows]
    async with AsyncSessionFactory() as session:
        await apply_tenant_rls(session, UUID(tenant_id_str))
        rows = (await session.execute(sql, params)).all()
    return [str(row[0]) for row in rows]


async def upsert_user_resume_embedding(
    user_id: str,
    tenant_id: str | UUID,
    resume_text: str,
    db: AsyncSession | None = None,
) -> None:
    """Update user profile resume embedding from latest resume text."""

    if not tenant_id:
        raise ValueError("tenant_id is required for vector update")
    tenant_id_str = str(tenant_id)
    embedding = embed_passage(resume_text)
    sql = text(
        """
        UPDATE user_profiles
        SET resume_embedding = CAST(:embedding AS vector),
            updated_at = NOW()
        WHERE user_id = CAST(:user_id AS uuid)
          AND tenant_id = CAST(:tenant_id AS uuid)
        """
    )
    params = {"embedding": _vector_literal(embedding), "user_id": user_id, "tenant_id": tenant_id_str}
    if db is not None:
        await db.execute(sql, params)
        return
    async with AsyncSessionFactory() as session:
        await apply_tenant_rls(session, UUID(tenant_id_str))
        await session.execute(sql, params)
        await session.commit()


async def save_job_embedding(
    job_id: str,
    tenant_id: str | UUID,
    embedding: list[float],
    db: AsyncSession | None = None,
) -> None:
    """Persist one job embedding in pgvector column."""

    if not tenant_id:
        raise ValueError("tenant_id is required for vector update")
    tenant_id_str = str(tenant_id)
    sql = text(
        "UPDATE jobs SET embedding = CAST(:embedding AS vector) "
        "WHERE id = CAST(:job_id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid)"
    )
    params = {"embedding": _vector_literal(embedding), "job_id": job_id, "tenant_id": tenant_id_str}
    if db is not None:
        await db.execute(sql, params)
        return
    async with AsyncSessionFactory() as session:
        await apply_tenant_rls(session, UUID(tenant_id_str))
        await session.execute(sql, params)
        await session.commit()
