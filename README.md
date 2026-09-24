# APEX APPLY

Production-grade multi-tenant AI job application automation platform.

## What this is

A job search platform where the AI does the tedious, error-prone parts —
tailoring a resume per job description, drafting outreach, discovering
referral contacts, aggregating listings from dozens of sources, and even
driving the actual application form on real ATS platforms — while every
action that matters (submitting an application, sending outreach) stays
a deliberate human decision.

## Stack

- Backend: FastAPI (Python 3.12, async)
- Frontend: Next.js 14 App Router (TypeScript)
- Database: PostgreSQL 16 with tenant RLS policies
- Search: Typesense
- Vector: pgvector (in-database embeddings via PostgreSQL extension)
- Cache/Queue: Redis + ARQ
- LLM runtime: Ollama
- Browser automation: Playwright
- Object storage: MinIO
- Observability: Prometheus + Sentry/GlitchTip

## Agent architecture

Five agent modules in `apps/api/agents/`, all LangGraph state machines
calling a local Ollama model — not single-prompt wrappers:

- **`resume_graph.py`** — resume tailoring. 4-node graph: knowledge
  (extracts JD requirements) → writer (tailors the resume) → reviewer
  (audits for fabrication) → supervisor (approve / retry up to 3x /
  reject). Anti-hallucination is enforced two ways: a strict "never
  invent" prompt, and a programmatic diff (`_programmatic_flags`) that
  compares numbers, company names, and skills between the original and
  tailored text independently of what the LLM claims.
- **`referral_graph.py`** — referral discovery. 5-node graph: infers a
  company's domain/GitHub org/email pattern via LLM → discovers real
  contacts through the public GitHub API → infers likely emails from
  name patterns → scores contact usefulness → stores sorted by
  confidence. Every contact is persisted with `is_verified: False`
  until a human confirms it.
- **`outreach_graph.py`** — outreach drafting. Draft generation is
  template-based (not LLM-authored) specifically to avoid hallucinated
  claims; a second LLM call acts as a compliance reviewer, scoring the
  draft for spam signals, GDPR risk, and CAN-SPAM compliance before
  it's allowed to be sent.
- **`copilot_chain.py`** — conversational career coach (interview prep,
  resume review, job strategy), streamed, with mode-specific system
  prompts grounded in the user's actual resume/profile.
- **`supervisor.py`** — platform health monitor. Not itself LLM-driven;
  it runs periodic rule-based checks (ingestion lag, Typesense sync lag,
  referral failure rate, and whether the copilot's Ollama model is
  actually reachable) and raises severity-tiered alerts.

## Browser Agent V1 — deterministic application automation

`apps/api/browser_agent_v1/` is a purpose-built browser automation engine
for filling out and submitting job applications on real ATS platforms
(Workday, Greenhouse, Lever, iCIMS, Ashby, BambooHR, generic forms). It
is not an LLM agent driving a browser through free-form reasoning — it
is a deterministic state machine, because unpredictable behavior on
someone's actual job application is not an acceptable failure mode.

- **State machine** (`domain/state_machine.py`, `domain/enums.py`) — 24
  explicit states (landing page, login, application form, file upload,
  screening questions, review, submit, etc.) with an explicit transition
  table (`_TRANSITIONS`). Every state change is validated against that
  table before it's allowed to happen.
- **Perception** (`perception.py`) — classifies the current page into a
  state using DOM signals and keyword heuristics, not vision or an LLM
  call. Fast, cheap, and deterministic.
- **Planner** (`planner.py`) — chooses the next action via explicit
  if/elif rules over the current state and perceived signals, not a
  prompted model. Given the same page and state, it always produces the
  same plan.
- **Provider playbooks** (`providers/`) — per-ATS selector definitions
  and quirks (Workday's iframe-heavy multi-page flow, Greenhouse's
  single-page form, Lever, iCIMS, generic fallback), each isolated so a
  layout change on one ATS can't break the others.
- **Action execution with selector fallback** (`runtime/action_executor.py`,
  `selectors.py`, and the `services/autofill/ats/*` adapters) — every
  click/type/select tries an ordered list of candidate selectors and
  records success/failure per selector so the system learns which
  selectors are actually reliable for a given provider over time
  (`db/models/browser_agent_selector_memory.py`).
- **Human-in-the-loop pauses** — the policy layer (`domain/policies.py`)
  flags sensitive questions (compensation, protected-class demographic
  questions, anything requiring a judgment call) and pauses the run,
  persisting a `BrowserAgentPauseRequest` and emailing the user, rather
  than guessing an answer on their behalf.
- **Full auditability** — every run persists its step timeline
  (`BrowserAgentStep`), event log (`BrowserAgentEventLog`), and state
  snapshots (`BrowserAgentStateSnapshot`) so a run can be replayed or
  debugged after the fact (`runtime/replay.py`).
- **Screenshots/DOM artifacts** are captured to MinIO (`storage.py`,
  `runtime/observers.py`) at each step for review.
- **Never auto-submits.** Every run ends in a review state requiring
  explicit human confirmation before final submission — consistent with
  the platform-wide "no auto-submit" safeguard below.

Feature-flagged per tenant via `services/feature_flags.py`
(`get_tenant_browser_agent_v1_state` — supports shadow mode, percentage
rollout, and an internal-only allowlist) so it can be rolled out
gradually and disabled instantly per tenant without a deploy.

## Core Safeguards

- **No scraping of LinkedIn, Indeed, or Glassdoor by default.** Job
  ingestion (`apps/api/services/ingestion_service.py`) only auto-runs
  official APIs/feeds — Greenhouse, Lever, RemoteOK, Adzuna, Arbeitnow,
  The Muse, USAJobs. A `jobspy` adapter exists (wraps `python-jobspy`,
  which *does* scrape LinkedIn/Indeed/Glassdoor/ZipRecruiter) but is
  excluded from the default and personalized source sets and defaults
  to zero target sites (`JOBSPY_SITE_NAMES` is empty). It only runs at
  all if a deployer explicitly sets that variable and explicitly adds
  `"jobspy"` to a source list — an informed opt-in, never a default,
  because scraping those platforms carries real Terms-of-Service risk.
- No hallucinated resume edits (reviewer + supervisor enforcement, see
  Agent architecture above).
- No auto-submit of job applications (human submit required, including
  Browser Agent V1 runs — see above).
- No auto-send outreach without explicit human approval.
- All referral contacts stored as unverified until user confirmation.

## Repository Layout

- `apps/api`: FastAPI application (routers, services, agents, browser_agent_v1, workers)
- `apps/web`: Next.js frontend
- `infra`: local and production infrastructure assets
- `tests`: API/agent/e2e tests
- `scripts`: seed and utility scripts

## Local Development

1. Copy env vars:

```bash
cp .env.example .env
```

If a local `.env` with real credentials was ever committed, treat those values as compromised and rotate them before any shared or production use.

2. Start services:

```bash
make up
```

UI will be available at `http://localhost:3000` (dev compose `web` service).
API will be available at `http://localhost:8001`.
Email verification messages in local development are captured by Mailpit at `http://localhost:8025`.

For real email delivery (for example Gmail), set SMTP variables in `.env`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USE_TLS=false
SMTP_USERNAME=youraddress@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM_EMAIL=youraddress@gmail.com
```

3. Apply migrations:

```bash
make migrate
```

4. Seed development data:

```bash
python scripts/seed.py
python scripts/seed_typesense.py
```

5. Run smoke test:

```bash
python scripts/smoke_test.py
python scripts/smoke_jobs_filters.py
```

## Production

Use `docker-compose.prod.yml` with `infra/nginx/nginx.conf`.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

For full VPS deployment steps and automation scripts, see `DEPLOYMENT.md`.

## Testing

Run all tests:

```bash
make test-all
```

Targeted tests:

```bash
make test-copilot
make test-referral
docker compose -f infra/docker-compose.yml exec -T api sh -lc "PYTHONPATH=/app pytest /app/tests/api/test_search.py -v"
```

Intelligent test analysis (heuristics + LLM root-cause analysis):

```bash
make intelligent-test
```

Outputs:
- `intelligent-test-report.md`
- `intelligent-test-report.json`

Optional (skip LLM call, keep heuristic analysis):

```bash
python scripts/intelligent_test_analyzer.py --no-llm
```

Offline ranking evaluation (BM25/vector/RRF/rerank):

```bash
make ranking-eval
make ranking-gate
make ranking-build-fixture
make ranking-gate-real
```

`ranking-gate` uses `tests/fixtures/ranking_eval_rerank_baseline.json` and exits non-zero if the rerank candidate regresses below the configured `min_delta`.
`ranking-build-fixture` builds `tests/fixtures/ranking_eval_real_sample.json` from a CSV source schema (`query_id,relevant_ids,bm25_ids,vector_ids,rrf_ids,rrf_rerank_ids`).

Reranking rollout readiness can be monitored via admin APIs:

- `GET /admin/ranking/rerank-status?days=7`
- `GET /admin/ranking/rerank-readiness?days=7&min_attempts=100&max_timeout_rate=0.05&max_failure_rate=0.02&max_average_latency_ms=800`

Enable `ENABLE_RERANKING=true` only when offline gate passes and readiness endpoint returns `ready_to_enable_reranking=true` for your chosen thresholds.

## Operations Quick Checks

After `docker compose -f infra/docker-compose.yml up -d --build`, verify these runtime paths:

- Notification pipeline:
  - stream status: `GET /admin/alerts/status`
- Requirements extraction queue:
  - `GET /admin/requirements/status`
- Coverage and freshness:
  - `GET /admin/coverage/dashboard`
- Browser Agent V1 rollout/runs (admin only):
  - `GET /admin/browser-agent-v1/rollout`
  - `GET /admin/browser-agent-v1/runs`
- Adaptive ranking feedback capture:
  - `GET /admin/ranking/rerank-status`
- Overall health/dependency probe:
  - `GET /health`

## Jobs Discovery

- `All Jobs` mode: full-text + faceted search (`/jobs/search`, Typesense).
- `Semantic Matches` mode: resume-based similarity (`/jobs/matches`, pgvector).
- Tier-1 (official API/feed) and Tier-2 (ATS careers-page crawl) ingestion
  both feed a common Redis Streams pipeline (`services/ingestion/streams.py`)
  with idempotency, retry with backoff, and a dead-letter queue.
