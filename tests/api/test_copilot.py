from __future__ import annotations

import types

import pytest

from agents import copilot_chain


class DummyProfile:
    headline = "Senior Python Engineer"
    summary_bio = "Built APIs"
    work_authorization = "h1b"
    target_roles = ["Software Engineer"]
    target_locations = ["Remote"]
    target_salary_min = 120000
    target_salary_max = 180000
    years_experience = 6


class DummyResume:
    original_text = "Skills: Python"


class DummyJob:
    description = "Python backend role"
    company = "Acme"


def test_create_session_general_mode() -> None:
    mode = "general"
    prompt = copilot_chain.build_system_prompt(mode, DummyProfile(), DummyResume(), DummyJob())
    assert "User Resume" in prompt


@pytest.mark.asyncio
async def test_send_message_streams_response(monkeypatch: pytest.MonkeyPatch) -> None:
    session = types.SimpleNamespace(mode="general", messages=[])

    async def fake_run(*args, **kwargs):
        for chunk in ["Hello", " world"]:
            yield chunk

    monkeypatch.setattr(copilot_chain, "run_copilot_turn", fake_run)

    chunks = []
    async for c in copilot_chain.run_copilot_turn(session, "Hi", DummyProfile(), DummyResume(), DummyJob()):
        chunks.append(c)

    assert "".join(chunks)


def test_copilot_includes_resume_context() -> None:
    prompt = copilot_chain.build_system_prompt("general", DummyProfile(), DummyResume(), DummyJob())
    assert "Python" in prompt


def test_copilot_does_not_hallucinate_skills() -> None:
    prompt = copilot_chain.build_system_prompt("general", DummyProfile(), DummyResume(), DummyJob())
    assert "Go" not in prompt


@pytest.mark.asyncio
async def test_interview_questions_generated(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(_: str):
        return copilot_chain.JDAnalysisLite(required_skills=["Python"], seniority_level="mid")

    async def fake_technical(required_skills, n_technical):
        return [f"How did you use {required_skills[0]}?"] * n_technical

    monkeypatch.setattr(copilot_chain, "_analyze_jd", fake_analyze)
    monkeypatch.setattr(copilot_chain, "_generate_technical_questions", fake_technical)

    questions = await copilot_chain.generate_interview_questions(DummyJob(), DummyResume())
    assert questions
    assert all("category" in q for q in questions)
