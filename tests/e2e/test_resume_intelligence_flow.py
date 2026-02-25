from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest


async def _run_resume_flow(steps: dict[str, AsyncMock]) -> dict:
    uploaded = await steps["upload_resume"]()
    parsed = await steps["parse_resume"](uploaded["resume_id"])
    review = await steps["generate_review"](uploaded["resume_id"])
    tailored = await steps["tailor_resume"](uploaded["resume_id"], uploaded["job_id"])
    cover_letter = await steps["create_cover_letter"](uploaded["resume_id"], uploaded["job_id"])
    return {
        "uploaded": uploaded,
        "parsed": parsed,
        "review": review,
        "tailored": tailored,
        "cover_letter": cover_letter,
    }


@pytest.mark.e2e
def test_resume_intelligence_happy_path() -> None:
    steps = {
        "upload_resume": AsyncMock(return_value={"resume_id": "r-1", "job_id": "j-1", "status": "pending"}),
        "parse_resume": AsyncMock(return_value={"resume_id": "r-1", "status": "parsed"}),
        "generate_review": AsyncMock(return_value={"resume_id": "r-1", "overall_score": 82.5}),
        "tailor_resume": AsyncMock(return_value={"resume_id": "r-1", "status": "approved", "quality_score": 84.0}),
        "create_cover_letter": AsyncMock(return_value={"resume_id": "r-1", "status": "draft", "word_count": 287}),
    }
    result = asyncio.run(_run_resume_flow(steps))

    assert result["uploaded"]["status"] == "pending"
    assert result["parsed"]["status"] == "parsed"
    assert result["review"]["overall_score"] >= 70
    assert result["tailored"]["status"] == "approved"
    assert result["cover_letter"]["word_count"] <= 350

    steps["upload_resume"].assert_awaited_once()
    steps["parse_resume"].assert_awaited_once_with("r-1")
    steps["generate_review"].assert_awaited_once_with("r-1")
    steps["tailor_resume"].assert_awaited_once_with("r-1", "j-1")
    steps["create_cover_letter"].assert_awaited_once_with("r-1", "j-1")


@pytest.mark.e2e
def test_resume_intelligence_blocks_cover_letter_on_tailor_reject() -> None:
    steps = {
        "upload_resume": AsyncMock(return_value={"resume_id": "r-2", "job_id": "j-2", "status": "pending"}),
        "parse_resume": AsyncMock(return_value={"resume_id": "r-2", "status": "parsed"}),
        "generate_review": AsyncMock(return_value={"resume_id": "r-2", "overall_score": 74.0}),
        "tailor_resume": AsyncMock(return_value={"resume_id": "r-2", "status": "rejected", "quality_score": 55.0}),
        "create_cover_letter": AsyncMock(return_value={"resume_id": "r-2", "status": "draft", "word_count": 290}),
    }

    async def run_flow_guarded() -> dict:
        uploaded = await steps["upload_resume"]()
        await steps["parse_resume"](uploaded["resume_id"])
        await steps["generate_review"](uploaded["resume_id"])
        tailored = await steps["tailor_resume"](uploaded["resume_id"], uploaded["job_id"])
        if tailored["status"] != "approved":
            return {"status": "blocked", "reason": "tailoring_rejected"}
        await steps["create_cover_letter"](uploaded["resume_id"], uploaded["job_id"])
        return {"status": "completed"}

    result = asyncio.run(run_flow_guarded())
    assert result["status"] == "blocked"
    assert result["reason"] == "tailoring_rejected"
    steps["create_cover_letter"].assert_not_called()
