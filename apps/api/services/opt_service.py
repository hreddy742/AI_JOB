"""OPT deadline alert automation."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from db.session import AsyncSessionFactory

logger = structlog.get_logger()

_THRESHOLDS = {180, 120, 90, 60, 30, 14, 7, 3, 1}


def _urgency(days_remaining: int) -> str:
    if days_remaining <= 14:
        return "critical"
    if days_remaining <= 60:
        return "elevated"
    return "normal"


def _build_message(days_remaining: int, opt_end_date: object, stem_opt_eligible: bool) -> str:
    message = f"Your OPT expires in {days_remaining} days on {opt_end_date}."
    if stem_opt_eligible and days_remaining <= 90:
        message += " Apply for STEM OPT extension now to add 24 months of work authorization."
    if days_remaining <= 30:
        message += " Focus your applications on companies with H1B confidence score above 70."
    return message


async def run_opt_deadline_alerts(_: dict | None = None) -> dict[str, int]:
    """Send in-app alerts for users approaching OPT deadlines."""

    sent = 0
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT
                        o.user_id,
                        o.tenant_id,
                        u.email,
                        o.opt_end_date,
                        o.stem_opt_eligible,
                        o.stem_opt_end,
                        o.h1b_filed,
                        o.urgency_level,
                        o.last_alert_sent,
                        (o.opt_end_date - CURRENT_DATE) AS days_remaining
                    FROM opt_tracker o
                    JOIN users u ON u.id = o.user_id
                    WHERE o.opt_end_date > CURRENT_DATE
                    """
                )
            )
        ).mappings().all()

        for row in rows:
            days_remaining = int(row["days_remaining"])
            last_alert_sent = row["last_alert_sent"]
            if days_remaining not in _THRESHOLDS:
                continue
            if last_alert_sent is not None and getattr(last_alert_sent, "date", lambda: None)() == datetime.now(UTC).date():
                continue

            urgency = _urgency(days_remaining)
            message = _build_message(days_remaining, row["opt_end_date"], bool(row["stem_opt_eligible"]))
            await db.execute(
                text(
                    """
                    INSERT INTO alert_log (user_id, tenant_id, title, message, alert_type, channel, payload)
                    VALUES (:user_id, :tenant_id, :title, :message, 'opt_deadline', 'in_app', :payload::jsonb)
                    """
                ),
                {
                    "user_id": row["user_id"],
                    "tenant_id": row["tenant_id"],
                    "title": "OPT deadline approaching",
                    "message": message,
                    "payload": '{"channel":"in_app"}',
                },
            )
            await db.execute(
                text(
                    """
                    UPDATE opt_tracker
                    SET urgency_level = :urgency, last_alert_sent = now()
                    WHERE user_id = :user_id
                    """
                ),
                {"urgency": urgency, "user_id": row["user_id"]},
            )
            sent += 1

        await db.commit()

    logger.info("opt_deadline_alerts_completed", sent=sent)
    return {"sent": sent}
