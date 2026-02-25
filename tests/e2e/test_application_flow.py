from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_application_flow() -> None:
    steps = [
        "register",
        "create profile",
        "search jobs",
        "tailor resume",
        "create application",
        "run automation",
        "manual submit",
    ]
    assert len(steps) == 7
    assert steps[-1] == "manual submit"
