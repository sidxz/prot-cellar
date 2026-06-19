# prot-cellar — developer Makefile
#
# First run:
#   make install      # backend (uv) + frontend (pnpm) deps
#   make up           # start Postgres + Valkey, run DB migrations
#   make dev          # start backend (:8001) + frontend (:3000) in the background
#   open http://localhost:3000
#
# Day to day:  make logs (tail)  ·  make stop (stop servers)  ·  make down (stop containers)
#
# Auth uses the shared Sentinel identity-service (configured in backend/.env + frontend/.env.local).
# No local Sentinel is needed when SENTINEL_URL points at the remote service.

COMPOSE  := docker compose
BACKEND  := cd backend
FRONTEND := cd frontend
LOGDIR   := .logs
# Load backend/.env (DATABASE_URL, SENTINEL_*) into the recipe shell.
BE_ENV   := set -a && . ./.env && set +a

.DEFAULT_GOAL := help
.PHONY: help up down install dev dev-be dev-fe stop logs migrate generate-api \
        test test-api test-all test-fe lint lint-fe nuke

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'

up: ## Start Postgres + Valkey, wait for readiness, run migrations
	$(COMPOSE) up -d postgres valkey
	@echo "Waiting for Postgres on :5433..."
	@until $(COMPOSE) exec -T postgres pg_isready -U protcellar -q 2>/dev/null; do sleep 1; done
	@$(MAKE) --no-print-directory migrate
	@echo "Infra ready: Postgres :5433, Valkey :6380."

down: ## Stop containers (keep data)
	$(COMPOSE) stop

install: ## Install backend (uv) + frontend (pnpm) dependencies
	$(BACKEND) && uv sync
	$(FRONTEND) && pnpm install

migrate: ## Apply DB migrations (alembic)
	$(BACKEND) && $(BE_ENV) && uv run alembic upgrade head

dev: stop ## Start backend (:8001) + frontend (:3000) in the background
	@mkdir -p $(LOGDIR)
	@echo "Starting backend on :8001..."
	@nohup sh -c '$(BACKEND) && $(BE_ENV) && exec uv run uvicorn protcellar.interface.app:app --reload --port 8001' \
		> $(LOGDIR)/backend.log 2>&1 & echo "$$!" > $(LOGDIR)/backend.pid
	@echo "Starting frontend on :3000..."
	@nohup sh -c '$(FRONTEND) && exec pnpm dev' \
		> $(LOGDIR)/frontend.log 2>&1 & echo "$$!" > $(LOGDIR)/frontend.pid
	@sleep 1
	@echo ""
	@echo "  Backend   http://localhost:8001/docs   (pid $$(cat $(LOGDIR)/backend.pid), log $(LOGDIR)/backend.log)"
	@echo "  Frontend  http://localhost:3000        (pid $$(cat $(LOGDIR)/frontend.pid), log $(LOGDIR)/frontend.log)"
	@echo "  make logs — tail both    ·    make stop — stop both"

dev-be: ## (Re)start the backend only, in the background
	@mkdir -p $(LOGDIR)
	@lsof -ti:8001 | xargs kill 2>/dev/null || true
	@nohup sh -c '$(BACKEND) && $(BE_ENV) && exec uv run uvicorn protcellar.interface.app:app --reload --port 8001' \
		> $(LOGDIR)/backend.log 2>&1 & echo "$$!" > $(LOGDIR)/backend.pid
	@echo "Backend (re)started on :8001 (log $(LOGDIR)/backend.log)"

dev-fe: ## (Re)start the frontend only, in the background
	@mkdir -p $(LOGDIR)
	@lsof -ti:3000 | xargs kill 2>/dev/null || true
	@nohup sh -c '$(FRONTEND) && exec pnpm dev' \
		> $(LOGDIR)/frontend.log 2>&1 & echo "$$!" > $(LOGDIR)/frontend.pid
	@echo "Frontend (re)started on :3000 (log $(LOGDIR)/frontend.log)"

stop: ## Stop the backend + frontend dev servers
	@[ -f $(LOGDIR)/backend.pid ]  && kill $$(cat $(LOGDIR)/backend.pid)  2>/dev/null || true
	@[ -f $(LOGDIR)/frontend.pid ] && kill $$(cat $(LOGDIR)/frontend.pid) 2>/dev/null || true
	@lsof -ti:8001 | xargs kill 2>/dev/null || true
	@lsof -ti:3000 | xargs kill 2>/dev/null || true
	@rm -f $(LOGDIR)/backend.pid $(LOGDIR)/frontend.pid
	@echo "Dev servers stopped."

logs: ## Tail backend + frontend dev logs
	@mkdir -p $(LOGDIR) && touch $(LOGDIR)/backend.log $(LOGDIR)/frontend.log
	tail -f $(LOGDIR)/backend.log $(LOGDIR)/frontend.log

generate-api: ## Refresh the OpenAPI snapshot from the backend + regenerate the TS client
	$(BACKEND) && $(BE_ENV) && uv run python -c \
		"import json,sys; from protcellar.interface.app import app; sys.stdout.write(json.dumps(app.openapi()))" \
		> ../frontend/openapi.json
	$(FRONTEND) && pnpm generate:api

test: ## Backend unit tests + import-linter
	$(BACKEND) && uv run pytest tests/unit -v && uv run lint-imports

test-api: ## Backend API tests
	$(BACKEND) && uv run pytest tests/api -v

test-all: ## All backend tests + import-linter
	$(BACKEND) && uv run pytest -v && uv run lint-imports

test-fe: ## Frontend tests (vitest)
	$(FRONTEND) && pnpm test

lint: ## Backend lint (ruff + mypy)
	$(BACKEND) && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src

lint-fe: ## Frontend lint (biome)
	$(FRONTEND) && pnpm lint

nuke: ## Stop containers and DELETE all data volumes
	$(COMPOSE) down -v
