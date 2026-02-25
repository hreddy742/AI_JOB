from __future__ import annotations

from typing import Any

from agents.resume_graph import graph, supervisor_node


def test_resume_graph_has_expected_nodes() -> None:
    assert graph is not None


def test_supervisor_retries_on_low_score() -> None:
    state: dict[str, Any] = {
        "violations": [],
        "reviewer_score": 10.0,
        "retry_count": 0,
    }
    out = supervisor_node(state)  # type: ignore[arg-type]
    assert out["supervisor_decision"] == "RETRY"
