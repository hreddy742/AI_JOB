#!/usr/bin/env bash
set -euo pipefail

# Idempotent production deploy script for this repository.
# Run from repo root on your VPS.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f docker-compose.prod.yml ]]; then
  echo "docker-compose.prod.yml not found. Run from the repository root."
  exit 1
fi

if [[ ! -f .env ]]; then
  echo ".env not found. Create it first (cp .env.production.example .env)."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed."
  exit 1
fi

echo "Pulling latest images/building services..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Applying database migrations..."
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head

echo "Waiting for health checks..."
for i in {1..30}; do
  if curl -fsS http://localhost/api/health >/dev/null 2>&1; then
    echo "API health check passed."
    break
  fi
  sleep 3
  if [[ "$i" -eq 30 ]]; then
    echo "API health check did not pass in time."
    docker compose -f docker-compose.prod.yml ps
    exit 1
  fi
done

if curl -fsS http://localhost/login >/dev/null 2>&1; then
  echo "Web health check passed."
else
  echo "Web health check failed."
  docker compose -f docker-compose.prod.yml ps
  exit 1
fi

echo "Deployment complete."
docker compose -f docker-compose.prod.yml ps
