"""Resume creation service from wizard input."""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID

import httpx
from docx import Document
from weasyprint import HTML
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls, apply_user_rls
from db.models.resume import Resume
from db.models.resume_parsed_data import ResumeParsedData


def _to_markdown(payload: dict[str, Any], summary: str, enhanced_experience: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    contact = payload.get("contact", {})
    lines.append(f"# {contact.get('name','')}".strip())
    lines.append(f"{contact.get('email','')} | {contact.get('phone','')} | {contact.get('city','')}".strip(" |"))
    lines.append("")
    lines.append("## Summary")
    lines.append(summary)
    lines.append("")
    lines.append("## Experience")
    for job in enhanced_experience:
        lines.append(f"### {job.get('title','')} - {job.get('company','')}")
        lines.extend([f"- {b}" for b in job.get("bullets", [])])
    lines.append("")
    lines.append("## Education")
    for edu in payload.get("education", []):
        lines.append(f"- {edu.get('degree','')} - {edu.get('institution','')}")
    lines.append("")
    lines.append("## Skills")
    lines.append(", ".join(payload.get("skills", {}).get("technical", [])))
    return "\n".join(lines).strip()


async def _llm_bullet_enhance(raw_bullets: list[str], target_role: str, title: str, company: str) -> list[str]:
    if not raw_bullets:
        return []
    prompt = f"""
You are a professional resume writer.
Rewrite bullets as stronger professional bullet points without inventing facts.
Target Role: {target_role}
Current/Past Role: {title} at {company}
Raw bullets:
{chr(10).join(raw_bullets)}
Return ONLY JSON {{ "bullets": ["..."] }}.
""".strip()
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.WRITER_MODEL,
                "messages": [{"role": "system", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.2},
            },
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "{}")
    data = content if isinstance(content, dict) else __import__("json").loads(content)
    return [str(item).strip() for item in data.get("bullets", []) if str(item).strip()]


async def _llm_summary(payload: dict[str, Any]) -> str:
    prompt = f"""
Write a powerful 3-sentence professional summary.
No first-person pronouns.
Candidate Data:
Most Recent Title: {payload.get("target_role","")}
Top Skills: {", ".join(payload.get("skills", {}).get("technical", [])[:12])}
Strongest Achievements: {payload.get("highlights", [])}
""".strip()
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.WRITER_MODEL,
                "messages": [{"role": "system", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.25},
            },
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()


async def build_resume_from_wizard(db: AsyncSession, user_id: UUID, tenant_id: UUID, payload: dict[str, Any]) -> Resume:
    """Build and persist a resume from multi-step wizard payload."""

    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    experience = payload.get("experience", []) or []
    education = payload.get("education", []) or []
    if not experience and not education:
        raise ValueError("At least one work experience or education entry is required")

    enhanced_experience = []
    for item in experience:
        bullets = await _llm_bullet_enhance(item.get("responsibilities", []), payload.get("target_role", ""), item.get("title", ""), item.get("company", ""))
        enhanced_experience.append({**item, "bullets": bullets})

    summary = await _llm_summary(payload)
    markdown = _to_markdown(payload, summary, enhanced_experience)

    resume = Resume(
        user_id=user_id,
        tenant_id=tenant_id,
        label=payload.get("label", "My Resume"),
        file_name=f"built-{user_id}.md",
        file_size_bytes=len(markdown.encode("utf-8")),
        file_type="txt",
        file_path=f"tenants/{tenant_id}/resumes/{user_id}/built-{user_id}.md",
        original_text=markdown,
        raw_text=markdown,
        parse_status="parsed",
        parse_version=1,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    parsed = ResumeParsedData(
        resume_id=resume.id,
        user_id=user_id,
        tenant_id=tenant_id,
        contact_name=payload.get("contact", {}).get("name"),
        contact_email=payload.get("contact", {}).get("email"),
        contact_phone=payload.get("contact", {}).get("phone"),
        contact_location=payload.get("contact", {}).get("city"),
        contact_linkedin=payload.get("contact", {}).get("linkedin"),
        contact_github=payload.get("contact", {}).get("github"),
        contact_website=payload.get("contact", {}).get("website"),
        summary_text=summary,
        work_experience=enhanced_experience,
        education=education,
        skills_technical=payload.get("skills", {}).get("technical", []),
        skills_soft=payload.get("skills", {}).get("soft", []),
        skills_languages=payload.get("skills", {}).get("languages", []),
        skills_certifications=payload.get("skills", {}).get("certifications", []),
        projects=payload.get("projects", []),
        parser_model=settings.WRITER_MODEL,
    )
    db.add(parsed)
    await db.commit()
    return resume


def export_resume_pdf(markdown_text: str) -> bytes:
    html = f"<html><body><pre style='white-space: pre-wrap; font-family: Arial;'>{markdown_text}</pre></body></html>"
    return HTML(string=html).write_pdf()


def export_resume_docx(markdown_text: str) -> bytes:
    doc = Document()
    for line in markdown_text.splitlines():
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
