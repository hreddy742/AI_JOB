"""AI Career Copilot persistent conversational chain."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import Any, AsyncGenerator

import httpx
from pydantic import BaseModel, ValidationError

from core.config import settings
from db.models.chat_session import ChatSession
from db.models.job import Job
from db.models.resume import Resume
from db.models.user_profile import UserProfile

COPILOT_SYSTEM_PROMPTS = {
    "general": """
You are an expert AI career coach with 15+ years of experience helping
software engineers and tech professionals land their dream jobs.
You have access to:

The user's resume (provided below)
Their target job profile (provided below)
Their career preferences and goals

You provide:

Honest, actionable career advice
Resume feedback grounded in what's actually in their resume
Job search strategy tailored to their experience level
Encouragement balanced with realistic expectations

RULES:

Never make up facts about the user's experience
Base all advice on the actual resume content provided
If asked about skills they don't have, acknowledge the gap honestly
Do not promise outcomes you cannot guarantee

User Resume:
{resume_text}
User Profile:
{user_profile}
Target Job (if applicable):
{job_description}
""".strip(),
    "interview_prep": """
You are an expert technical interviewer and interview coach.
You are preparing the user for a specific job interview.
Your job:

Generate realistic interview questions for the target role
After user answers, provide structured feedback:

What was strong about the answer
What was missing or could be improved
Suggested improved answer using their actual experience


Cover: behavioral questions (STAR format), technical questions,
system design (if senior), culture fit questions
Adjust difficulty to match seniority level of target role

RULES:

Only reference skills and experience from their actual resume
Do not suggest they claim experience they don't have
Be encouraging but honest in feedback

User Resume:
{resume_text}
Target Job:
{job_description}
Target Seniority: {seniority_level}
""".strip(),
    "resume_review": """
You are a professional resume reviewer and career consultant.
Provide detailed, actionable feedback on the user's resume.
Review structure:

Overall impression (1-2 sentences)
Section-by-section feedback: Summary, Experience, Skills, Education
ATS optimization tips
Top 3 specific improvements (prioritized by impact)
What's working well (be specific)

RULES:

Only comment on what is actually in the resume
Do not suggest adding experience they don't have
Be specific - reference actual bullet points and phrases
Give concrete rewrites for weak bullet points

User Resume:
{resume_text}
""".strip(),
    "job_strategy": """
You are a strategic career advisor specializing in tech job searches.
You help with:

Job search strategy and prioritization
Salary negotiation tactics and ranges
When to apply (timing strategy)
How to evaluate offers
Building pipeline (how many applications, what cadence)
How to leverage network effectively

Ground all advice in:

The user's current experience level
Their target role and salary range
Current market conditions you are aware of

User Profile:
{user_profile}
Target Role: {target_role}
Target Salary Range: {salary_range}
""".strip(),
}

INTERVIEW_QUESTION_BANKS = {
    "behavioral": [
        "Tell me about a time you dealt with a difficult stakeholder.",
        "Describe a project where you had to learn something new quickly.",
        "Tell me about a time you disagreed with your team's decision.",
        "Describe your most challenging bug and how you resolved it.",
        "Tell me about a time you missed a deadline and what you did.",
    ],
    "system_design": [
        "Design a URL shortener like bit.ly.",
        "Design a job board that handles 1M daily active users.",
        "How would you design a real-time notification system?",
        "Design a rate limiter for an API gateway.",
    ],
    "culture": [
        "Why do you want to work at {company}?",
        "Where do you see yourself in 3 years?",
        "How do you handle ambiguity in your work?",
        "What's your preferred engineering culture?",
    ],
}


class JDAnalysisLite(BaseModel):
    """Minimal JD analysis used for interview question generation."""

    required_skills: list[str]
    seniority_level: str


def _profile_to_context(user_profile: UserProfile) -> str:
    """Render user profile into compact context string."""

    return json.dumps(
        {
            "headline": user_profile.headline,
            "summary_bio": user_profile.summary_bio,
            "work_authorization": user_profile.work_authorization,
            "target_roles": user_profile.target_roles,
            "target_locations": user_profile.target_locations,
            "salary_min": float(user_profile.target_salary_min) if user_profile.target_salary_min is not None else None,
            "salary_max": float(user_profile.target_salary_max) if user_profile.target_salary_max is not None else None,
            "years_experience": user_profile.years_experience,
        }
    )


def build_system_prompt(
    mode: str,
    user_profile: UserProfile,
    resume: Resume | None,
    job: Job | None,
    seniority_level: str = "unknown",
) -> str:
    """Build mode-specific copilot system prompt with injected context."""

    prompt_template = COPILOT_SYSTEM_PROMPTS.get(mode, COPILOT_SYSTEM_PROMPTS["general"])
    resume_text = resume.original_text if resume is not None else "No resume provided."
    job_description = job.description if job is not None and job.description else "No specific job selected."
    target_role = ", ".join(user_profile.target_roles) if user_profile.target_roles else "Not specified"
    salary_range = "Not specified"
    if user_profile.target_salary_min is not None or user_profile.target_salary_max is not None:
        salary_range = f"{user_profile.target_salary_min or 0} - {user_profile.target_salary_max or 0}"

    return prompt_template.format(
        resume_text=resume_text,
        user_profile=_profile_to_context(user_profile),
        job_description=job_description,
        seniority_level=seniority_level,
        target_role=target_role,
        salary_range=salary_range,
    )


async def run_copilot_turn(
    session: ChatSession,
    user_message: str,
    user_profile: UserProfile,
    resume: Resume | None,
    job: Job | None,
) -> AsyncGenerator[str, None]:
    """Process one conversational turn and stream text chunks."""

    system_prompt = build_system_prompt(session.mode.value if hasattr(session.mode, "value") else str(session.mode), user_profile, resume, job)
    history = session.messages[-settings.COPILOT_MAX_HISTORY_MESSAGES :]

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    full_response = ""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.COPILOT_MODEL,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
            },
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = chunk.get("message", {}).get("content", "")
                if text:
                    full_response += text
                    yield text

    session.messages.append({"role": "user", "content": user_message, "timestamp": datetime.now(UTC).isoformat()})
    session.messages.append({"role": "assistant", "content": full_response, "timestamp": datetime.now(UTC).isoformat()})
    session.updated_at = datetime.now(UTC)


async def _analyze_jd(job_description: str) -> JDAnalysisLite:
    """Analyze JD using lightweight model for interview preparation."""

    prompt = {
        "required_skills": ["Python", "SQL"],
        "seniority_level": "mid",
    }
    system = (
        "Extract required_skills and seniority_level from the job description. "
        "Return JSON with keys required_skills (list[str]) and seniority_level (str)."
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.KNOWLEDGE_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": job_description},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=45.0,
        )
        if response.status_code != 200:
            return JDAnalysisLite(**prompt)
        payload = response.json()
        content = payload.get("message", {}).get("content", "{}")
        try:
            data = json.loads(content) if isinstance(content, str) else content
            return JDAnalysisLite.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            return JDAnalysisLite(**prompt)


async def _generate_technical_questions(required_skills: list[str], n_technical: int) -> list[str]:
    """Generate technical questions from required skills via LLM."""

    if not required_skills:
        return []

    system = "Generate concise technical interview questions as JSON list under key questions."
    user = json.dumps({"skills": required_skills, "count": n_technical})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.COPILOT_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=45.0,
        )
        if response.status_code != 200:
            return [f"How have you used {skill} in production?" for skill in required_skills[:n_technical]]

        payload = response.json()
        content = payload.get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            questions = parsed.get("questions") if isinstance(parsed, dict) else None
            if isinstance(questions, list):
                return [str(item) for item in questions][:n_technical]
        except json.JSONDecodeError:
            pass

    return [f"How have you used {skill} in production?" for skill in required_skills[:n_technical]]


async def generate_interview_questions(
    job: Job,
    resume: Resume,
    n_behavioral: int = 3,
    n_technical: int = 3,
    include_system_design: bool = True,
) -> list[dict[str, str]]:
    """Generate tailored interview questions from JD + question banks."""

    analysis = await _analyze_jd(job.description or "")
    behavioral = random.sample(INTERVIEW_QUESTION_BANKS["behavioral"], k=min(n_behavioral, len(INTERVIEW_QUESTION_BANKS["behavioral"])))
    culture = random.sample(INTERVIEW_QUESTION_BANKS["culture"], k=1)
    technical = await _generate_technical_questions(analysis.required_skills, n_technical)

    questions: list[dict[str, str]] = []
    for question in behavioral:
        questions.append({"category": "behavioral", "question": question, "tips": "Use STAR and quantify impact using real experience."})

    for question in technical:
        questions.append({"category": "technical", "question": question, "tips": "Anchor your answer to projects that appear in your resume."})

    if include_system_design and analysis.seniority_level in {"senior", "lead", "executive"}:
        for question in random.sample(INTERVIEW_QUESTION_BANKS["system_design"], k=2):
            questions.append({"category": "system_design", "question": question, "tips": "Clarify requirements, discuss tradeoffs, and cover scaling."})

    company_name = job.company or "the company"
    for question in culture:
        questions.append(
            {
                "category": "culture",
                "question": question.format(company=company_name),
                "tips": "Connect motivation to your resume-backed strengths and company mission.",
            }
        )

    if not resume.original_text.strip():
        questions.append(
            {
                "category": "behavioral",
                "question": "Walk me through your most relevant recent project.",
                "tips": "Focus on role, actions, and measurable outcome.",
            }
        )

    return questions
