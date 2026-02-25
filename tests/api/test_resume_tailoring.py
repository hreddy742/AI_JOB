from __future__ import annotations

from typing import Any

from agents.resume_graph import supervisor_node


def _base_state() -> dict[str, Any]:
    return {
        "violations": [],
        "quality_score": 85.0,
        "retry_count": 0,
        "review_report": {"suggestions_for_writer": []},
        "tailored_text": "Tailored resume text",
        "supervisor_decision": "",
        "retry_notes": "",
        "error": None,
        "final_tailored_text": "",
    }


def test_supervisor_approves_clean_output() -> None:
    out = supervisor_node(_base_state())  # type: ignore[arg-type]
    assert out["supervisor_decision"] == "APPROVED"
    assert out["final_tailored_text"] == "Tailored resume text"


def test_supervisor_retries_on_critical_violations() -> None:
    state = _base_state()
    state["violations"] = [
        {"severity": "critical", "type": "fabricated_skill", "explanation": "Added AWS with no source evidence"}
    ]
    out = supervisor_node(state)  # type: ignore[arg-type]
    assert out["supervisor_decision"] == "RETRY"
    assert out["retry_count"] == 1
    assert "fabricated_skill" in out["retry_notes"]


def test_supervisor_rejects_after_max_retries_with_critical() -> None:
    state = _base_state()
    state["violations"] = [{"severity": "critical", "type": "new_employer", "explanation": "Inserted unknown company"}]
    state["retry_count"] = 3
    out = supervisor_node(state)  # type: ignore[arg-type]
    assert out["supervisor_decision"] == "REJECTED"
    assert "Rejected after 3 retries" in (out["error"] or "")


def test_supervisor_retries_on_low_quality() -> None:
    state = _base_state()
    state["quality_score"] = 62.5
    state["review_report"] = {"suggestions_for_writer": ["Improve keyword alignment", "Clarify impact language"]}
    out = supervisor_node(state)  # type: ignore[arg-type]
    assert out["supervisor_decision"] == "RETRY"
    assert out["retry_count"] == 1
    assert "Quality score" in out["retry_notes"]
