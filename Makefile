.PHONY: up down logs migrate web index-typesense test-copilot test-referral smoke intelligent-test

up:
	docker compose -f infra/docker-compose.yml up -d --build

down:
	docker compose -f infra/docker-compose.yml down -v

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head

web:
	docker compose -f infra/docker-compose.yml up -d web

index-typesense:
	python scripts/seed_typesense.py

test-copilot:
	docker compose -f infra/docker-compose.yml exec -T api sh -lc "pip install pytest pytest-asyncio && PYTHONPATH=/app pytest /app/tests/api/test_copilot.py -v"

test-referral:
	docker compose -f infra/docker-compose.yml exec -T api sh -lc "pip install pytest pytest-asyncio && PYTHONPATH=/app pytest /app/tests/api/test_referral.py -v"

smoke:
	python scripts/smoke_test.py

intelligent-test:
	python scripts/intelligent_test_analyzer.py --include-web-build
