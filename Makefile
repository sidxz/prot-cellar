.PHONY: up stop migrate dev test test-api test-all lint nuke

up:
	docker compose up -d postgres valkey
	cd backend && uv run alembic upgrade head

stop:
	docker compose stop

migrate:
	cd backend && uv run alembic upgrade head

dev:
	cd backend && uv run uvicorn protcellar.interface.app:app --reload --port 8001

test:
	cd backend && uv run pytest tests/unit -v && uv run lint-imports

test-api:
	cd backend && uv run pytest tests/api -v

test-all:
	cd backend && uv run pytest -v && uv run lint-imports

lint:
	cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src

nuke:
	docker compose down -v
