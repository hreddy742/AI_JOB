from __future__ import annotations

from services.job_service import calculate_sponsorship_score


def test_sponsorship_score_positive_patterns() -> None:
    score = calculate_sponsorship_score("Software Engineer", "Visa sponsorship available and H1B supported")
    assert score > 0.5


def test_sponsorship_score_negative_patterns() -> None:
    score = calculate_sponsorship_score("Backend Engineer", "No sponsorship. US citizenship required")
    assert score < 0.5


def test_sponsorship_score_neutral_defaults_to_half() -> None:
    score = calculate_sponsorship_score("Developer", "Build backend APIs and distributed systems")
    assert score == 0.5
