"""Deterministic screening intelligence helpers for Browser Agent V1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from services.screening_answer_service import normalize_screening_question


LOW_RISK_KEYWORDS = {
    "relocation",
    "background check",
    "drug test",
    "notice period",
    "salary expectation",
    "compensation",
    "start date",
}

SENSITIVE_KEYWORDS = {
    "authorized to work",
    "work authorization",
    "visa",
    "sponsorship",
    "citizen",
    "citizenship",
    "clearance",
}


@dataclass(slots=True)
class ScreeningMatch:
    question: str
    answer: str
    confidence: float
    source: str
    sensitive: bool = False


def _tokenize(text: str) -> set[str]:
    normalized = normalize_screening_question(text)
    synonyms = {
        "relocation": "relocate",
        "position": "role",
        "salary": "compensation",
        "pay": "compensation",
    }
    tokens = {token for token in re.split(r"[^a-z0-9]+", normalized) if token and len(token) > 2}
    return {synonyms.get(token, token) for token in tokens}


def screening_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens & right_tokens
    total = left_tokens | right_tokens
    return len(shared) / max(1, len(total))


def is_sensitive_screening_question(question: str) -> bool:
    haystack = normalize_screening_question(question)
    return any(keyword in haystack for keyword in SENSITIVE_KEYWORDS)


def is_low_risk_screening_question(question: str) -> bool:
    haystack = normalize_screening_question(question)
    return any(keyword in haystack for keyword in LOW_RISK_KEYWORDS)


def build_profile_screening_answer(question: str, profile: dict[str, Any]) -> ScreeningMatch | None:
    normalized = normalize_screening_question(question)
    if "relocation" in normalized:
        open_to_relocation = profile.get("open_to_relocation")
        if open_to_relocation is not None:
            return ScreeningMatch(question, "Yes" if bool(open_to_relocation) else "No", 0.93, "profile")
    if "background check" in normalized:
        value = profile.get("willing_to_undergo_background_checks")
        if value is not None:
            return ScreeningMatch(question, "Yes" if bool(value) else "No", 0.93, "profile")
    if "drug test" in normalized:
        value = profile.get("willing_to_undergo_drug_tests")
        if value is not None:
            return ScreeningMatch(question, "Yes" if bool(value) else "No", 0.93, "profile")
    if "notice period" in normalized or "how much notice" in normalized:
        notice = str(profile.get("notice_period") or "").strip()
        if notice:
            return ScreeningMatch(question, notice, 0.9, "profile")
    if "salary" in normalized or "compensation" in normalized or "pay" in normalized:
        min_salary = profile.get("salary_expectation_min") or profile.get("target_salary_min")
        max_salary = profile.get("salary_expectation_max") or profile.get("target_salary_max")
        if min_salary and max_salary:
            return ScreeningMatch(question, f"${int(float(min_salary))}-${int(float(max_salary))}", 0.88, "profile")
    if "authorized to work" in normalized or "sponsorship" in normalized or "visa" in normalized:
        auth = str(profile.get("us_work_authorization") or profile.get("work_authorization") or "").strip()
        if auth:
            return ScreeningMatch(question, auth, 0.8, "profile", sensitive=True)
    return None


def choose_best_screening_match(question: str, known_answers: dict[str, str], profile: dict[str, Any]) -> ScreeningMatch | None:
    direct = build_profile_screening_answer(question, profile)
    if direct is not None:
        return direct
    best: ScreeningMatch | None = None
    for candidate, answer in known_answers.items():
        similarity = screening_similarity(question, candidate)
        if similarity < 0.58:
            continue
        match = ScreeningMatch(
            question=candidate,
            answer=answer,
            confidence=min(0.96, 0.62 + similarity * 0.35),
            source="memory",
            sensitive=is_sensitive_screening_question(question) or is_sensitive_screening_question(candidate),
        )
        if best is None or match.confidence > best.confidence:
            best = match
    return best
