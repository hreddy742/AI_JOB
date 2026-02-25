"""LLM-assisted test runner and failure analyzer.

Runs a set of repo checks, extracts likely root causes, then asks an LLM
for a prioritized remediation plan. Designed to work even when some tools
or services are unavailable.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("KNOWLEDGE_MODEL", "qwen2:1.5b")


@dataclass
class CheckSpec:
    name: str
    command: list[str]
    cwd: Path
    required: bool = True


@dataclass
class CheckResult:
    name: str
    command: str
    cwd: str
    required: bool
    returncode: int | None
    duration_seconds: float
    output_tail: str
    skipped_reason: str | None = None


def _python_executable() -> str:
    return sys.executable


def _has_pytest() -> bool:
    return importlib.util.find_spec("pytest") is not None


def _has_npm() -> bool:
    return shutil.which("npm.cmd") is not None or shutil.which("npm") is not None


def _npm_command() -> str:
    npm_cmd = shutil.which("npm.cmd")
    if npm_cmd:
        return npm_cmd
    npm_bin = shutil.which("npm")
    if npm_bin:
        return npm_bin
    return "npm.cmd"


def _build_checks(include_web_build: bool) -> list[CheckSpec]:
    checks = [
        CheckSpec(
            name="api_compile",
            command=[_python_executable(), "-m", "compileall", "apps/api"],
            cwd=ROOT,
        ),
        CheckSpec(
            name="api_smoke",
            command=[_python_executable(), "scripts/smoke_test.py"],
            cwd=ROOT,
        ),
    ]

    if _has_pytest():
        checks.append(
            CheckSpec(
                name="api_pytest",
                command=[_python_executable(), "-m", "pytest", "tests", "-v"],
                cwd=ROOT,
            )
        )
    else:
        checks.append(
            CheckSpec(
                name="api_pytest",
                command=[_python_executable(), "-m", "pytest", "tests", "-v"],
                cwd=ROOT,
                required=False,
            )
        )

    web_dir = ROOT / "apps" / "web"
    if _has_npm() and (web_dir / "package.json").exists():
        checks.append(
            CheckSpec(
                name="web_typecheck",
                command=[_npm_command(), "run", "-s", "typecheck"],
                cwd=web_dir,
            )
        )
        if include_web_build:
            checks.append(
                CheckSpec(
                    name="web_build",
                    command=[_npm_command(), "run", "-s", "build"],
                    cwd=web_dir,
                    required=False,
                )
            )
    else:
        checks.append(
            CheckSpec(
                name="web_typecheck",
                command=[_npm_command(), "run", "-s", "typecheck"],
                cwd=web_dir,
                required=False,
            )
        )
    return checks


def _trim_output(text: str, max_chars: int = 6000) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return f"...(truncated)...\n{cleaned[-max_chars:]}"


def run_check(spec: CheckSpec, timeout: int) -> CheckResult:
    start = time.perf_counter()
    cmd = " ".join(spec.command)
    if spec.name == "api_pytest" and not _has_pytest():
        return CheckResult(
            name=spec.name,
            command=cmd,
            cwd=str(spec.cwd),
            required=spec.required,
            returncode=None,
            duration_seconds=0.0,
            output_tail="",
            skipped_reason="pytest is not installed in this Python environment",
        )
    if spec.name.startswith("web_") and not _has_npm():
        return CheckResult(
            name=spec.name,
            command=cmd,
            cwd=str(spec.cwd),
            required=spec.required,
            returncode=None,
            duration_seconds=0.0,
            output_tail="",
            skipped_reason="npm is not available on PATH",
        )

    try:
        proc = subprocess.run(
            spec.command,
            cwd=spec.cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = f"{proc.stdout}\n{proc.stderr}".strip()
        return CheckResult(
            name=spec.name,
            command=cmd,
            cwd=str(spec.cwd),
            required=spec.required,
            returncode=proc.returncode,
            duration_seconds=round(time.perf_counter() - start, 2),
            output_tail=_trim_output(output),
        )
    except subprocess.TimeoutExpired as exc:
        output = f"{exc.stdout or ''}\n{exc.stderr or ''}\nERROR: command timed out"
        return CheckResult(
            name=spec.name,
            command=cmd,
            cwd=str(spec.cwd),
            required=spec.required,
            returncode=124,
            duration_seconds=round(time.perf_counter() - start, 2),
            output_tail=_trim_output(output),
        )


def _line_match(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def extract_issues(results: list[CheckResult]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for r in results:
        text = r.output_tail or ""
        if r.skipped_reason:
            issues.append(
                {
                    "severity": "medium",
                    "source": r.name,
                    "category": "check_skipped",
                    "summary": r.skipped_reason,
                    "evidence": r.skipped_reason,
                    "fix_hint": "Install missing toolchain and rerun analyzer.",
                }
            )
            continue
        if r.returncode in {0, None}:
            continue

        if _line_match(r"No module named ['\"]([^'\"]+)['\"]", text):
            mod = re.search(r"No module named ['\"]([^'\"]+)['\"]", text)
            module_name = mod.group(1) if mod else "unknown"
            issues.append(
                {
                    "severity": "high",
                    "source": r.name,
                    "category": "missing_python_dependency",
                    "summary": f"Missing Python module: {module_name}",
                    "evidence": module_name,
                    "fix_hint": "Install API requirements into the active venv.",
                }
            )
        if _line_match(r"validation errors for settings|field required", text):
            issues.append(
                {
                    "severity": "high",
                    "source": r.name,
                    "category": "missing_env_config",
                    "summary": "Required environment variables for API settings are missing.",
                    "evidence": "Settings validation failed during import.",
                    "fix_hint": "Populate .env from .env.example before running tests.",
                }
            )
        if _line_match(r"dockerdesktoplinuxengine|failed to connect to the docker api", text):
            issues.append(
                {
                    "severity": "high",
                    "source": r.name,
                    "category": "docker_unavailable",
                    "summary": "Docker daemon is unavailable.",
                    "evidence": "Could not connect to Docker engine pipe.",
                    "fix_hint": "Start Docker Desktop and verify docker compose ps works.",
                }
            )
        if _line_match(r"actively refused|connection refused|max retries exceeded with url", text):
            issues.append(
                {
                    "severity": "high",
                    "source": r.name,
                    "category": "service_not_running",
                    "summary": "A required local service is not reachable.",
                    "evidence": "Connection refused during smoke/runtime check.",
                    "fix_hint": "Start API/web stack before smoke and e2e checks.",
                }
            )
        if _line_match(r"spawn eperm|psexecutionpolicy|running scripts is disabled", text):
            issues.append(
                {
                    "severity": "medium",
                    "source": r.name,
                    "category": "execution_policy_or_spawn_restriction",
                    "summary": "Process spawn or shell execution policy blocked the check.",
                    "evidence": "EPERM or PowerShell script policy error detected.",
                    "fix_hint": "Use npm.cmd and run outside restricted shell/sandbox if needed.",
                }
            )
        if _line_match(r"password cannot be longer than 72 bytes|passlib|bcrypt", text):
            issues.append(
                {
                    "severity": "high",
                    "source": r.name,
                    "category": "password_hashing_backend_issue",
                    "summary": "Password hashing backend appears incompatible.",
                    "evidence": "bcrypt/passlib runtime hashing error.",
                    "fix_hint": "Align bcrypt version with pinned requirements and retest auth hashing.",
                }
            )
        if not any(i["source"] == r.name for i in issues):
            issues.append(
                {
                    "severity": "medium",
                    "source": r.name,
                    "category": "unknown_failure",
                    "summary": f"{r.name} failed with return code {r.returncode}",
                    "evidence": _trim_output(text, 240),
                    "fix_hint": "Inspect command output and add targeted remediation.",
                }
            )
    return issues


def query_ollama(
    ollama_url: str,
    model: str,
    results: list[CheckResult],
    heuristic_issues: list[dict[str, Any]],
    timeout: int,
) -> dict[str, Any]:
    condensed_results = [
        {
            "name": r.name,
            "returncode": r.returncode,
            "skipped_reason": r.skipped_reason,
            "output_tail": _trim_output(r.output_tail, 1800),
        }
        for r in results
    ]
    system_prompt = (
        "You are a senior test reliability engineer. "
        "Analyze check results, identify root causes, and produce a prioritized fix plan. "
        "Return strict JSON with keys: summary, critical_issues, likely_root_causes, "
        "fix_plan, confidence."
    )
    user_prompt = {
        "context": "Repository intelligent test run",
        "heuristic_issues": heuristic_issues,
        "check_results": condensed_results,
    }
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt)},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")

    req = Request(
        url=f"{ollama_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)
        content = data.get("message", {}).get("content", "{}")
        if isinstance(content, dict):
            return content
        return json.loads(content)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "summary": "LLM analysis unavailable",
            "critical_issues": [],
            "likely_root_causes": [str(exc)],
            "fix_plan": ["Verify Ollama is running and model is available, then rerun."],
            "confidence": 0.0,
        }


def _status(result: CheckResult) -> str:
    if result.skipped_reason:
        return "SKIPPED"
    if result.returncode == 0:
        return "PASS"
    return "FAIL"


def render_markdown_report(
    results: list[CheckResult],
    issues: list[dict[str, Any]],
    llm_analysis: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Intelligent Test Report")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now(UTC).isoformat()}")
    lines.append("")
    lines.append("## Check Status")
    lines.append("")
    lines.append("| Check | Status | Duration(s) |")
    lines.append("|---|---|---:|")
    for r in results:
        lines.append(f"| `{r.name}` | {_status(r)} | {r.duration_seconds} |")
    lines.append("")
    lines.append("## Heuristic Findings")
    lines.append("")
    if not issues:
        lines.append("- No issues detected.")
    else:
        for issue in issues:
            lines.append(
                f"- [{issue['severity']}] `{issue['source']}` {issue['category']}: "
                f"{issue['summary']} | hint: {issue['fix_hint']}"
            )
    lines.append("")
    lines.append("## LLM Analysis")
    lines.append("")
    lines.append(f"- Summary: {llm_analysis.get('summary', 'n/a')}")
    lines.append(f"- Confidence: {llm_analysis.get('confidence', 'n/a')}")
    critical = llm_analysis.get("critical_issues", []) or []
    roots = llm_analysis.get("likely_root_causes", []) or []
    plan = llm_analysis.get("fix_plan", []) or []
    if critical:
        lines.append("- Critical issues:")
        for item in critical:
            lines.append(f"  - {item}")
    if roots:
        lines.append("- Likely root causes:")
        for item in roots:
            lines.append(f"  - {item}")
    if plan:
        lines.append("- Prioritized fix plan:")
        for idx, item in enumerate(plan, start=1):
            lines.append(f"  {idx}. {item}")
    lines.append("")
    lines.append("## Command Output Tails")
    lines.append("")
    for r in results:
        lines.append(f"### {r.name}")
        lines.append("")
        lines.append(f"- Command: `{r.command}`")
        lines.append(f"- CWD: `{r.cwd}`")
        lines.append(f"- Status: `{_status(r)}`")
        if r.skipped_reason:
            lines.append(f"- Skipped: {r.skipped_reason}")
        if r.output_tail:
            lines.append("")
            lines.append("```text")
            lines.append(r.output_tail)
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run intelligent test analysis with LLM support.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL.")
    parser.add_argument("--timeout", type=int, default=600, help="Per-check timeout in seconds.")
    parser.add_argument("--llm-timeout", type=int, default=120, help="LLM request timeout in seconds.")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM analysis.")
    parser.add_argument(
        "--include-web-build",
        action="store_true",
        help="Include Next.js production build in checks.",
    )
    parser.add_argument(
        "--report-path",
        default=str(ROOT / "intelligent-test-report.md"),
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--json-path",
        default=str(ROOT / "intelligent-test-report.json"),
        help="JSON report output path.",
    )
    args = parser.parse_args()

    checks = _build_checks(include_web_build=args.include_web_build)
    results = [run_check(spec, timeout=args.timeout) for spec in checks]
    issues = extract_issues(results)
    llm_analysis: dict[str, Any] = {
        "summary": "LLM analysis skipped",
        "critical_issues": [],
        "likely_root_causes": [],
        "fix_plan": [],
        "confidence": 0.0,
    }
    if not args.no_llm:
        llm_analysis = query_ollama(
            ollama_url=args.ollama_url,
            model=args.model,
            results=results,
            heuristic_issues=issues,
            timeout=args.llm_timeout,
        )

    md = render_markdown_report(results, issues, llm_analysis)
    report_path = Path(args.report_path)
    report_path.write_text(md, encoding="utf-8")

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": [asdict(r) for r in results],
        "heuristic_issues": issues,
        "llm_analysis": llm_analysis,
    }
    json_path = Path(args.json_path)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    failed_required = any(r.required and _status(r) == "FAIL" for r in results)
    print(f"Report written: {report_path}")
    print(f"JSON written: {json_path}")
    print(f"Required checks failed: {failed_required}")
    return 1 if failed_required else 0


if __name__ == "__main__":
    raise SystemExit(main())
