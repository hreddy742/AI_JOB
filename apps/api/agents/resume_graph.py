"""Strict resume tailoring graph with anti-hallucination controls."""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from core.config import settings


class TailoringState(TypedDict):
    original_resume_text: str
    parsed_resume: dict[str, Any]
    job_description: str
    user_id: str
    tenant_id: str
    resume_id: str
    job_id: str
    target_company: str
    target_title: str
    jd_analysis: dict[str, Any]
    tailored_text: str
    diff_log: list[dict[str, Any]]
    review_report: dict[str, Any]
    violations: list[dict[str, Any]]
    ats_score: float
    quality_score: float
    supervisor_decision: str
    retry_count: int
    retry_notes: str
    final_tailored_text: str
    error: str | None


KNOWLEDGE_PROMPT = """
You are a senior technical recruiter who has screened 10,000+ resumes.
Analyze the job description and extract structured requirements.
Only extract what is explicitly stated. Do not infer.
Output ONLY valid JSON:
{
  "required_skills": [],
  "preferred_skills": [],
  "ats_keywords": [],
  "seniority_level": "entry|mid|senior|lead|executive",
  "years_experience_required": 0,
  "domain": "software_engineering|data_science|devops|product|design|security|other",
  "industry": "fintech|healthcare|e-commerce|enterprise|startup|government|other",
  "key_responsibilities": [],
  "culture_keywords": [],
  "hard_requirements": []
}
""".strip()

WRITER_PROMPT = """
You are a professional resume writer with 20 years of experience helping
candidates at Google, Amazon, McKinsey, and top-tier startups get interviews.

ABSOLUTE CONSTRAINTS:
NEVER add any skill not listed/demonstrated in original.
NEVER add any company/project/employer not in original.
NEVER modify any job title.
NEVER change any date.
NEVER add any number/metric not in original.
NEVER invent any responsibility or achievement.
NEVER add education credentials not in original.

Output ONLY valid JSON:
{
  "tailored_text": "FULL tailored resume markdown",
  "diff_log": [
    {
      "section":"work_experience|skills|summary|education|projects",
      "change_type":"rephrase|reorder|remove|summary_rewrite|skills_reorder",
      "original":"...",
      "tailored":"...",
      "jd_keywords_matched":[],
      "reasoning":"...",
      "confidence":0.0
    }
  ],
  "ats_keywords_inserted": [],
  "bullets_removed": [],
  "summary_rewritten": true
}
""".strip()

REVIEWER_PROMPT = """
You are a resume integrity auditor and senior hiring manager.
Catch any fabrications or hallucinations in the tailored resume.
A false positive is better than a false negative.
Output ONLY JSON:
{
  "violations": [
    {
      "severity":"critical|high|medium|low",
      "type":"fabricated_skill|new_employer|modified_title|modified_date|fabricated_metric|invented_responsibility|unsupported_claim",
      "original_text":"...",
      "tailored_text":"...",
      "explanation":"..."
    }
  ],
  "ats_score": 0.0,
  "bullet_impact_score": 0.0,
  "clarity_score": 0.0,
  "overall_quality_score": 0.0,
  "summary_integrity": "PASS|FAIL",
  "strengths": [],
  "suggestions_for_writer": []
}
""".strip()


async def _call_ollama_json(model: str, system_prompt: str, user_content: str, temperature: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=240.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                "format": "json",
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        response.raise_for_status()
        payload = response.json()
    content = payload.get("message", {}).get("content", "{}")
    return content if isinstance(content, dict) else json.loads(content)


def _extract_tokens(text: str) -> dict[str, set[str]]:
    numbers = set(re.findall(r"\d+(?:\.\d+)?%?", text))
    companies = set(
        x.strip()
        for x in re.findall(r"\b[A-Z][A-Za-z0-9&]+(?:\s+[A-Z][A-Za-z0-9&]+){0,3}\b", text)
        if len(x.strip().split()) <= 4
    )
    words = set(re.findall(r"[A-Za-z][A-Za-z\+\#\-]{1,}", text.lower()))
    return {"numbers": numbers, "companies": companies, "words": words}


def _programmatic_flags(state: TailoringState) -> list[str]:
    original = _extract_tokens(state["original_resume_text"])
    tailored = _extract_tokens(state["tailored_text"])
    flags: list[str] = []
    new_numbers = sorted(tailored["numbers"] - original["numbers"])
    if new_numbers:
        flags.append(f"Potential new numeric claims: {', '.join(new_numbers[:20])}")
    new_companies = sorted(tailored["companies"] - original["companies"])
    if new_companies:
        flags.append(f"Potential new organizations: {', '.join(new_companies[:20])}")
    known_skills = {s.lower() for s in (state.get("parsed_resume", {}).get("skills_all", []) or [])}
    jd_skills = {s.lower() for s in (state.get("jd_analysis", {}).get("required_skills", []) or [])}
    new_skill_like = sorted((tailored["words"] & jd_skills) - known_skills)
    if new_skill_like:
        flags.append(f"Potential inserted skills not present in resume: {', '.join(new_skill_like[:30])}")
    return flags


def _required_overlap(jd_required: list[str], skill_pool: list[str]) -> float:
    if not jd_required:
        return 0.0
    normalized = {s.lower().strip() for s in skill_pool}
    hit = sum(1 for item in jd_required if item.lower().strip() in normalized)
    return hit / len(jd_required)


async def knowledge_agent_node(state: TailoringState) -> TailoringState:
    analysis = await _call_ollama_json(settings.KNOWLEDGE_MODEL, KNOWLEDGE_PROMPT, state["job_description"], 0.0)
    overlap = _required_overlap(analysis.get("required_skills", []), state.get("parsed_resume", {}).get("skills_all", []))
    analysis["overlap_score"] = round(overlap, 3)
    state["jd_analysis"] = analysis
    return state


async def writer_agent_node(state: TailoringState) -> TailoringState:
    payload = json.dumps(
        {
            "original_resume_text": state["original_resume_text"],
            "jd_analysis_json": state["jd_analysis"],
            "retry_notes": state.get("retry_notes") or "",
        }
    )
    output = await _call_ollama_json(settings.WRITER_MODEL, WRITER_PROMPT, payload, 0.15)
    state["tailored_text"] = output.get("tailored_text", state["original_resume_text"])
    state["diff_log"] = output.get("diff_log", [])
    return state


async def reviewer_agent_node(state: TailoringState) -> TailoringState:
    flags = _programmatic_flags(state)
    review_payload = json.dumps(
        {
            "original_resume_text": state["original_resume_text"],
            "tailored_text": state["tailored_text"],
            "jd_analysis_json": state["jd_analysis"],
            "diff_log_json": state["diff_log"],
            "programmatic_flags": flags,
        }
    )
    review = await _call_ollama_json(settings.REVIEWER_MODEL, REVIEWER_PROMPT, review_payload, 0.0)
    state["review_report"] = review
    state["violations"] = review.get("violations", [])
    state["ats_score"] = float(review.get("ats_score") or 0)
    state["quality_score"] = float(review.get("overall_quality_score") or 0)
    return state


def supervisor_node(state: TailoringState) -> TailoringState:
    max_retries = 3
    quality_threshold = 70.0
    critical = [v for v in state["violations"] if v.get("severity") == "critical"]
    high = [v for v in state["violations"] if v.get("severity") == "high"]
    score = float(state.get("quality_score") or 0)
    retries = int(state.get("retry_count") or 0)

    if critical and retries >= max_retries:
        state["supervisor_decision"] = "REJECTED"
        state["error"] = (
            f"Rejected after {retries} retries. {len(critical)} critical violations remain: "
            + "; ".join(v.get("explanation", "") for v in critical)
        )
    elif critical:
        state["retry_count"] = retries + 1
        suggestions = state.get("review_report", {}).get("suggestions_for_writer", [])
        notes = "\n".join(f"- {v.get('type','')}: {v.get('explanation','')}" for v in critical)
        state["retry_notes"] = (
            f"RETRY {state['retry_count']}/{max_retries}. "
            f"Fix ALL of these CRITICAL violations:\n{notes}\nReviewer suggestions:\n"
            + "\n".join(f"- {s}" for s in suggestions)
        )
        state["supervisor_decision"] = "RETRY"
    elif len(high) >= 2 and retries < max_retries:
        state["retry_count"] = retries + 1
        state["retry_notes"] = "Fix HIGH violations: " + "; ".join(v.get("explanation", "") for v in high)
        state["supervisor_decision"] = "RETRY"
    elif score < quality_threshold and retries < max_retries:
        state["retry_count"] = retries + 1
        suggestions = state.get("review_report", {}).get("suggestions_for_writer", [])
        state["retry_notes"] = f"Quality score {score:.1f} below {quality_threshold}. " + "; ".join(suggestions)
        state["supervisor_decision"] = "RETRY"
    else:
        state["supervisor_decision"] = "APPROVED"
        state["final_tailored_text"] = state["tailored_text"]
    return state


graph = StateGraph(TailoringState)
graph.add_node("knowledge", knowledge_agent_node)
graph.add_node("writer", writer_agent_node)
graph.add_node("reviewer", reviewer_agent_node)
graph.add_node("supervisor", supervisor_node)
graph.set_entry_point("knowledge")
graph.add_edge("knowledge", "writer")
graph.add_edge("writer", "reviewer")
graph.add_edge("reviewer", "supervisor")
graph.add_conditional_edges("supervisor", lambda s: s["supervisor_decision"], {"APPROVED": END, "RETRY": "writer", "REJECTED": END})
compiled_graph = graph.compile()
