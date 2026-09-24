"""Signal extraction from browser pages."""

from __future__ import annotations

from typing import Any

from browser_agent_v1.perception import PageSignals, VisibleField


SIGNAL_SCRIPT = """
() => {
  const pickText = (nodes) =>
    Array.from(nodes || [])
      .map((node) => (node.textContent || '').trim())
      .filter(Boolean)
      .slice(0, 50);
  const fields = Array.from(document.querySelectorAll('input, textarea, select')).slice(0, 100).map((el) => {
    const id = el.getAttribute('id') || '';
    const label = id ? (document.querySelector(`label[for="${id}"]`)?.textContent || '') : '';
    const name = (el.getAttribute('name') || '').trim();
    const tag = (el.tagName || '').toLowerCase();
    let selector = '';
    if (id) {
      selector = `#${id}`;
    } else if (name) {
      selector = `${tag}[name="${name.replace(/"/g, '\\"')}"]`;
    } else {
      selector = tag;
    }
    return {
      name,
      label: label.trim() || (el.getAttribute('aria-label') || '').trim() || (el.getAttribute('placeholder') || '').trim(),
      field_type: (el.getAttribute('type') || el.tagName || '').toLowerCase(),
      selector,
      required: el.required || el.getAttribute('aria-required') === 'true',
      checked: !!el.checked,
      options: el.tagName === 'SELECT'
        ? Array.from(el.options || []).map((opt) => (opt.label || opt.text || '').trim()).filter(Boolean).slice(0, 30)
        : []
    };
  });
  const errors = Array.from(document.querySelectorAll('[aria-invalid="true"], .error, .errors, [role="alert"]'))
    .map((el) => (el.textContent || '').trim())
    .filter(Boolean)
    .slice(0, 30);
  const uploads = Array.from(document.querySelectorAll('input[type="file"]'))
    .map((el) => (el.getAttribute('name') || el.getAttribute('id') || 'file').trim())
    .filter(Boolean);
  const providerHints = [];
  const html = document.documentElement.outerHTML.toLowerCase();
  if (html.includes('myworkdayjobs')) providerHints.push('workday');
  if (html.includes('greenhouse.io')) providerHints.push('greenhouse');
  if (html.includes('jobs.lever.co')) providerHints.push('lever');
  if (html.includes('icims.com') || html.includes('icims') || html.includes('icims_')) providerHints.push('icims');
  const visibleQuestions = pickText(
    Array.from(document.querySelectorAll('label, legend, p, span, div'))
      .filter((node) => (node.textContent || '').trim().includes('?'))
      .slice(0, 40)
  );
  const reviewSignals = pickText(
    Array.from(document.querySelectorAll('h1, h2, h3, button, a, div, span'))
      .filter((node) => /review|confirm|summary/i.test((node.textContent || '').trim()))
      .slice(0, 20)
  );
  const submitSignals = pickText(
    Array.from(document.querySelectorAll('button, a, input[type="submit"], input[type="button"]'))
      .filter((node) => /submit|send application|finish application/i.test((node.textContent || '').trim() || (node.getAttribute('value') || '').trim()))
      .slice(0, 20)
  );
  return {
    headings: pickText(document.querySelectorAll('h1, h2, h3')),
    buttons: pickText(document.querySelectorAll('button, a[role="button"], input[type="submit"], input[type="button"]')),
    labels: pickText(document.querySelectorAll('label')),
    forms: Array.from(document.querySelectorAll('form')).map((form) => (form.getAttribute('id') || form.getAttribute('name') || 'form')).slice(0, 20),
    uploads,
    validation_errors: errors,
    page_text: (document.body?.innerText || '').slice(0, 5000),
    provider_hints: providerHints,
    visible_fields: fields,
    visible_questions: visibleQuestions,
    review_signals: reviewSignals,
    submit_signals: submitSignals
  };
}
"""


async def extract_page_signals(page: Any, *, url: str = "", title: str = "") -> PageSignals:
    """Extract deterministic signals from the current page."""

    data = await page.evaluate(SIGNAL_SCRIPT)
    fields = [
        VisibleField(
            name=str(item.get("name") or ""),
            label=str(item.get("label") or ""),
            field_type=str(item.get("field_type") or ""),
            selector=str(item.get("selector") or ""),
            required=bool(item.get("required")),
            options=[str(option) for option in (item.get("options") or [])],
            checked=bool(item.get("checked")),
        )
        for item in (data.get("visible_fields") or [])
        if isinstance(item, dict)
    ]
    blockers: list[str] = []
    if data.get("validation_errors"):
        blockers.append("validation_errors_present")
    return PageSignals(
        url=url,
        title=title,
        headings=[str(item) for item in (data.get("headings") or [])],
        buttons=[str(item) for item in (data.get("buttons") or [])],
        labels=[str(item) for item in (data.get("labels") or [])],
        forms=[str(item) for item in (data.get("forms") or [])],
        uploads=[str(item) for item in (data.get("uploads") or [])],
        validation_errors=[str(item) for item in (data.get("validation_errors") or [])],
        page_text=str(data.get("page_text") or ""),
        provider_hints=[str(item) for item in (data.get("provider_hints") or [])],
        visible_fields=fields,
        blockers=blockers,
        visible_questions=[str(item) for item in (data.get("visible_questions") or [])],
        review_signals=[str(item) for item in (data.get("review_signals") or [])],
        submit_signals=[str(item) for item in (data.get("submit_signals") or [])],
    )
