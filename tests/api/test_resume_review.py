from __future__ import annotations

from services.resume_reviewer_service import _extract_bullets


def test_extract_bullets_returns_only_bullet_lines() -> None:
    text = """
Summary line
- Built API platform serving 1M requests/day
- Reduced deployment time by 40%
Not a bullet
""".strip()
    bullets = _extract_bullets(text)
    assert len(bullets) == 2
    assert bullets[0].startswith("Built API")
    assert "Reduced deployment time" in bullets[1]
