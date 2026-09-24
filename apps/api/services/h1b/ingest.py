"""Quarterly H1B/LCA sponsor ingestion."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from io import BytesIO
import re

import httpx
import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionFactory

logger = structlog.get_logger()

_SUFFIX_PATTERN = re.compile(r"\b(?:llc|inc|corp|ltd|co|corporation|incorporated)\b", re.IGNORECASE)
_PUNCTUATION_PATTERN = re.compile(r"[,\.\-']")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _current_fiscal_period() -> tuple[int, int]:
    now = datetime.now(UTC)
    quarter = ((now.month - 1) // 3) + 1
    return now.year, quarter


def normalize_company_name(name: str | None) -> str:
    value = str(name or "").strip().lower()
    value = _PUNCTUATION_PATTERN.sub(" ", value)
    value = _SUFFIX_PATTERN.sub("", value)
    value = _WHITESPACE_PATTERN.sub(" ", value).strip()
    return value


def _annualize_wage(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    if numeric < 1000:
        return round(numeric * 2080, 2)
    return round(numeric, 2)


def _pick_column(columns: list[str], *candidates: str) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    for candidate in candidates:
        normalized = candidate.lower().replace("_", "").replace(" ", "")
        for column in columns:
            compact = column.lower().replace("_", "").replace(" ", "")
            if compact == normalized:
                return column
    return None


def _aggregate_dataframe(df: pd.DataFrame) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in df.to_dict(orient="records"):
        normalized = normalize_company_name(row.get("company_name"))
        if not normalized:
            continue

        wage = _annualize_wage(row.get("wage_from"))
        status_value = str(row.get("case_status") or "")
        state_value = str(row.get("worksite_state") or "").strip().upper()
        approved = "certified" in status_value.lower()

        bucket = grouped.setdefault(
            normalized,
            {
                "company_name": str(row.get("company_name") or "").strip(),
                "company_normalized": normalized,
                "normalized_name": normalized,
                "wages": [],
                "states": [],
                "lca_count": 0,
                "approved_count": 0,
            },
        )
        bucket["lca_count"] = int(bucket["lca_count"]) + 1
        if approved:
            bucket["approved_count"] = int(bucket["approved_count"]) + 1
        if wage is not None:
            wages = bucket["wages"]
            assert isinstance(wages, list)
            wages.append(wage)
        if state_value:
            states = bucket["states"]
            assert isinstance(states, list)
            states.append(state_value)

    aggregated: list[dict[str, object]] = []
    for item in grouped.values():
        wages = item.pop("wages")
        states = item.pop("states")
        median_wage = float(pd.Series(wages, dtype="float64").median()) if wages else None
        state = Counter(states).most_common(1)[0][0] if states else None
        lca_count = int(item["lca_count"])
        approved_count = int(item["approved_count"])
        approval_rate = round((approved_count / lca_count) if lca_count else 0.0, 4)
        aggregated.append(
            {
                **item,
                "lca_last_1yr": lca_count,
                "lca_last_3yr": lca_count,
                "median_wage_usd": median_wage,
                "median_wage": median_wage,
                "primary_state": state,
                "approved_count": approved_count,
                "approval_rate": approval_rate,
                "lca_count_1yr": lca_count,
                "active_sponsor": lca_count > 0,
                "is_active_sponsor": lca_count > 0,
                "e_verify": False,
                "company_size": "unknown",
            }
        )
    return aggregated


async def ingest_h1b_sponsors(db: AsyncSession) -> dict[str, object]:
    year, quarter = _current_fiscal_period()
    url = f"https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY{year}_Q{quarter}.xlsx"
    logger.info("h1b_ingest_download_started", url=url, year=year, quarter=quarter)

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        logger.info("h1b_ingest_download_completed", url=url, bytes=len(response.content))

        dataframe = pd.read_excel(BytesIO(response.content))
        columns = dataframe.columns.tolist()
        logger.info("h1b_ingest_columns_detected", columns=columns)

        company_col = _pick_column(columns, "EMPLOYER_NAME")
        case_col = _pick_column(columns, "CASE_NUMBER")
        wage_col = _pick_column(columns, "WAGE_RATE_OF_PAY_FROM")
        state_col = _pick_column(columns, "WORKSITE_STATE")
        status_col = _pick_column(columns, "CASE_STATUS")
        if not all([company_col, case_col, wage_col, state_col, status_col]):
            missing = {
                "company_col": company_col,
                "case_col": case_col,
                "wage_col": wage_col,
                "state_col": state_col,
                "status_col": status_col,
            }
            logger.error("h1b_ingest_required_columns_missing", **missing)
            return {"status": "error", "upserted": 0, "enriched_jobs": 0, "error_if_any": f"Missing columns: {missing}"}

        trimmed = dataframe.rename(
            columns={
                company_col: "company_name",
                case_col: "case_number",
                wage_col: "wage_from",
                state_col: "worksite_state",
                status_col: "case_status",
            }
        )[["company_name", "case_number", "wage_from", "worksite_state", "case_status"]]
        trimmed = trimmed.dropna(subset=["company_name", "case_number"])
        aggregated = _aggregate_dataframe(trimmed)
        logger.info("h1b_ingest_aggregated", companies=len(aggregated))

        if aggregated:
            await db.execute(
                text(
                    """
                    INSERT INTO h1b_sponsors (
                        tenant_id,
                        company_name,
                        normalized_name,
                        company_normalized,
                        active_sponsor,
                        is_active_sponsor,
                        lca_count_1yr,
                        lca_last_1yr,
                        lca_last_3yr,
                        approval_rate,
                        approved_count,
                        median_wage,
                        median_wage_usd,
                        primary_state,
                        confidence_score,
                        e_verify,
                        company_size
                    ) VALUES (
                        NULL,
                        :company_name,
                        :normalized_name,
                        :company_normalized,
                        :active_sponsor,
                        :is_active_sponsor,
                        :lca_count_1yr,
                        :lca_last_1yr,
                        :lca_last_3yr,
                        :approval_rate,
                        :approved_count,
                        :median_wage,
                        :median_wage_usd,
                        :primary_state,
                        0,
                        :e_verify,
                        :company_size
                    )
                    ON CONFLICT (company_normalized) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        normalized_name = EXCLUDED.normalized_name,
                        active_sponsor = EXCLUDED.active_sponsor,
                        is_active_sponsor = EXCLUDED.is_active_sponsor,
                        lca_count_1yr = EXCLUDED.lca_count_1yr,
                        lca_last_1yr = EXCLUDED.lca_last_1yr,
                        lca_last_3yr = h1b_sponsors.lca_last_3yr + EXCLUDED.lca_last_3yr,
                        approval_rate = EXCLUDED.approval_rate,
                        approved_count = EXCLUDED.approved_count,
                        median_wage = EXCLUDED.median_wage,
                        median_wage_usd = EXCLUDED.median_wage_usd,
                        primary_state = EXCLUDED.primary_state,
                        e_verify = COALESCE(h1b_sponsors.e_verify, false),
                        company_size = COALESCE(NULLIF(h1b_sponsors.company_size, ''), EXCLUDED.company_size),
                        updated_at = now()
                    """
                ),
                aggregated,
            )

        await db.execute(
            text(
                """
                UPDATE h1b_sponsors
                SET
                    confidence_score =
                        (CASE WHEN lca_last_1yr > 0 THEN 40 ELSE 0 END)
                        + (CASE WHEN approval_rate > 0.85 THEN 20 ELSE 0 END)
                        + (CASE WHEN lca_last_3yr > 10 THEN 20 ELSE 0 END)
                        + (CASE WHEN e_verify THEN 10 ELSE 0 END)
                        + (CASE WHEN company_size IN ('large', 'enterprise') THEN 10 ELSE 0 END),
                    is_active_sponsor = (lca_last_1yr > 0),
                    active_sponsor = (lca_last_1yr > 0),
                    updated_at = now()
                """
            )
        )

        normalize_sql = (
            "trim(regexp_replace("
            "regexp_replace(lower(coalesce(jobs.company, '')), '[-,\\.'']', ' ', 'g'), "
            "'\\m(llc|inc|corp|ltd|co|corporation|incorporated)\\M', '', 'gi'))"
        )
        enriched = await db.execute(
            text(
                f"""
                UPDATE jobs
                SET
                    h1b_confidence_score = s.confidence_score,
                    h1b_active_sponsor = s.is_active_sponsor,
                    h1b_sponsor_count_3yr = s.lca_last_3yr,
                    h1b_avg_salary_lca = s.median_wage_usd
                FROM h1b_sponsors s
                WHERE regexp_replace({normalize_sql}, '\\s+', ' ', 'g') = s.company_normalized
                """
            )
        )
        await db.commit()

        enriched_jobs = int(enriched.rowcount or 0)
        logger.info("h1b_ingest_completed", upserted=len(aggregated), enriched_jobs=enriched_jobs)
        return {"status": "ok", "upserted": len(aggregated), "enriched_jobs": enriched_jobs, "error_if_any": None}
    except Exception as exc:
        await db.rollback()
        logger.exception("h1b_ingest_failed", error=str(exc))
        return {"status": "error", "upserted": 0, "enriched_jobs": 0, "error_if_any": str(exc)}


async def ingest_h1b_quarterly(_: dict | None = None) -> dict[str, object]:
    """ARQ-compatible wrapper for quarterly H1B ingestion."""

    async with AsyncSessionFactory() as db:
        return await ingest_h1b_sponsors(db)
