# APEX APPLY

Production-grade multi-tenant AI job application automation platform.

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

## Core Safeguards

- No scraping of LinkedIn, Indeed, Glassdoor
- No hallucinated resume edits (reviewer + supervisor enforcement)
- No auto-submit of job applications (human submit required)
- No auto-send outreach without explicit human approval
- All referral contacts stored as unverified until user confirmation

## Repository Layout

- `apps/api`: FastAPI application (routers, services, agents, workers)
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
Production examples now set `ENABLE_RERANKING=true`; use tenant-scoped admin override endpoints (`/admin/ranking/rerank-config`) to disable or re-enable instantly per tenant.

## Operations Quick Checks

After `docker compose -f infra/docker-compose.yml up -d --build`, verify these runtime paths:

- Notification pipeline:
  - worker: `notification-worker`
  - stream status: `GET /admin/alerts/status`
- Requirements extraction queue:
  - `GET /admin/requirements/status`
- Coverage and freshness:
  - `GET /admin/coverage/dashboard`
- Adaptive ranking feedback capture:
  - `POST /jobs/{job_id}/feedback` with `open` / `apply_click`
  - `GET /analytics/ranking-feedback`
- Automation task state (with persisted FSM snapshot):
  - `GET /applications/automate/tasks/{task_id}`
- Analytics marts refresh:
  - `POST /analytics/marts/refresh` (admin only)

## Jobs Discovery

- `All Jobs` mode: full-text + faceted search (`/jobs/search`, Typesense).
- `Semantic Matches` mode: resume-based similarity (`/jobs/matches`, pgvector).
- New tenant registrations are auto-seeded with default listings and indexed.

## CI

GitHub Actions workflow is defined in `.github/workflows/ci.yml` and runs:

- Typesense schema initialization check
- Copilot tests
- Referral tests
- Full pytest suite
