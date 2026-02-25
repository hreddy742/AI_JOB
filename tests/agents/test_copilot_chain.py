from __future__ import annotations

from agents.copilot_chain import build_system_prompt


class P:
    headline = "Engineer"
    summary_bio = "Python"
    work_authorization = "h1b"
    target_roles = ["Software Engineer"]
    target_locations = ["Remote"]
    target_salary_min = 100000
    target_salary_max = 150000
    years_experience = 5


class R:
    original_text = "Skills: Python, SQL"


class J:
    description = "Looking for Python engineer"


def test_build_system_prompt_includes_context() -> None:
    prompt = build_system_prompt("general", P(), R(), J())
    assert "Skills: Python" in prompt
    assert "Target Job" in prompt
