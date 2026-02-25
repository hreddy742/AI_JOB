from __future__ import annotations

from services.resume_parser import compute_metadata, detect_sections, extract_contact_regex


def test_detect_sections_maps_standard_headers() -> None:
    text = """
JOHN DOE
Professional Summary
Backend engineer with 5 years of experience.
Work Experience
Acme Corp - Senior Engineer
Education
University of Somewhere
Skills
Python, FastAPI, PostgreSQL
""".strip()
    sections = detect_sections(text)
    assert "summary" in sections
    assert "experience" in sections
    assert "education" in sections
    assert "skills" in sections


def test_extract_contact_regex_finds_common_fields() -> None:
    text = """
Jane Roe
jane.roe@example.com
(555) 123-4567
https://linkedin.com/in/janeroe
https://github.com/janeroe
https://janeroe.dev
""".strip()
    contact = extract_contact_regex(text)
    assert contact["email"] == "jane.roe@example.com"
    assert "555" in (contact["phone"] or "")
    assert "linkedin.com/in/janeroe" in (contact["linkedin"] or "")
    assert "github.com/janeroe" in (contact["github"] or "")
    assert "janeroe.dev" in (contact["website"] or "")


def test_compute_metadata_sets_seniority_domain_and_skills_union() -> None:
    parsed = {
        "work_experience": [
            {
                "title": "Senior Software Engineer",
                "start_date": "Jan 2018",
                "end_date": "Present",
                "bullets": ["Built microservices platform for payments infrastructure."],
            }
        ],
        "skills_technical": ["Python", "Kubernetes", "PostgreSQL"],
        "skills_soft": ["Mentoring"],
        "skills_languages": [],
        "skills_certifications": [],
    }
    enriched = compute_metadata(parsed)
    assert enriched["seniority_level"] in {"senior", "lead", "executive"}
    assert enriched["primary_domain"] == "software_engineering"
    assert "Python" in enriched["skills_all"]
    assert float(enriched["total_years_experience"]) >= 1.0
