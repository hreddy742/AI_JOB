# APEX APPLY

Production-grade multi-tenant AI job application automation platform.

## Stack

- Backend: FastAPI (Python 3.12, async)
- Frontend: Next.js 14 App Router (TypeScript)
- Database: PostgreSQL 16 with tenant RLS policies
- Search: Typesense
- Vector: ChromaDB
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
```

## Production

Use `docker-compose.prod.yml` with `infra/nginx/nginx.conf`.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Testing

Run all tests:

```bash
docker compose -f infra/docker-compose.yml exec -T api sh -lc "PYTHONPATH=/app pytest /app/tests -v"
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

## Jobs Discovery

- `All Jobs` mode: full-text + faceted search (`/jobs/search`, Typesense).
- `Semantic Matches` mode: resume-based similarity (`/jobs/matches`, ChromaDB).
- New tenant registrations are auto-seeded with default listings and indexed.

## CI

GitHub Actions workflow is defined in `.github/workflows/ci.yml` and runs:

- Typesense schema initialization check
- Copilot tests
- Referral tests
- Full pytest suite
