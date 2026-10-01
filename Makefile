# prot-cellar — developer Makefile
#
# First run:
#   make install      # backend (uv) + frontend (pnpm) deps
#   make up           # start Postgres + Valkey, run DB migrations
#   make dev          # start backend (:8001) + frontend (:3001) + import worker in the background
#   open http://localhost:3001
#
# Day to day:  make logs (tail)  ·  make stop (stop servers)  ·  make down (stop containers)
#
# Deploy (GHCR images, see RELEASING.md):  cp .env.example .env  ·  make prod-up
#
# Auth uses the shared Duar identity-service (configured in backend/.env + frontend/.env.local).
# No local Duar is needed when DUAR_URL points at the remote service.

COMPOSE_INFRA := docker compose -f docker-compose.infra.yml
COMPOSE_PROD  := $(COMPOSE_INFRA) -f docker-compose.prod.yml
COMPOSE_BUILD := $(COMPOSE_PROD) -f docker-compose.yml
BACKEND  := cd backend
FRONTEND := cd frontend
LOGDIR   := .logs
# Load backend/.env (DATABASE_URL, DUAR_*) into the recipe shell.
BE_ENV   := set -a && . ./.env && set +a
# Build identity (version/sha/date) as APP_* — the same values CI bakes into images.
BUILD_INFO = eval "$$(scripts/build-info.sh $(1) | sed s/^/export\ APP_/)"
# arq import worker entrypoint (processes FE-enqueued import jobs).
WORKER   := uv run arq protcellar.infrastructure.ingestion.worker.WorkerSettings

.DEFAULT_GOAL := help
.PHONY: help up down install dev dev-be dev-fe dev-worker stop logs migrate generate-api \
        test test-api test-all test-fe lint lint-fe nuke security-scan \
        prod-pull prod-up prod-down prod-logs

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'

up: ## Start Postgres + Valkey, wait for readiness, run migrations
	$(COMPOSE_INFRA) up -d postgres valkey
	@echo "Waiting for Postgres on :5433..."
	@until $(COMPOSE_INFRA) exec -T postgres pg_isready -U protcellar -q 2>/dev/null; do sleep 1; done
	@$(MAKE) --no-print-directory migrate
	@echo "Infra ready: Postgres :5433, Valkey :6380."

down: ## Stop containers (keep data)
	$(COMPOSE_INFRA) stop

install: ## Install backend (uv) + frontend (pnpm) dependencies
	$(BACKEND) && uv sync
	$(FRONTEND) && pnpm install

migrate: ## Apply DB migrations (alembic)
	$(BACKEND) && $(BE_ENV) && uv run alembic upgrade head

dev: stop ## Start backend (:8001) + frontend (:3001) + import worker in the background
	@mkdir -p $(LOGDIR)
	@echo "Starting backend on :8001..."
	@nohup sh -c '$(call BUILD_INFO,backend) && $(BACKEND) && $(BE_ENV) && exec uv run uvicorn protcellar.interface.app:app --reload --port 8001' \
		> $(LOGDIR)/backend.log 2>&1 & echo "$$!" > $(LOGDIR)/backend.pid
	@echo "Starting frontend on :3001..."
	@nohup sh -c '$(call BUILD_INFO,frontend) && $(FRONTEND) && exec pnpm dev' \
		> $(LOGDIR)/frontend.log 2>&1 & echo "$$!" > $(LOGDIR)/frontend.pid
	@echo "Starting import worker..."
	@nohup sh -c '$(BACKEND) && $(BE_ENV) && exec $(WORKER)' \
		> $(LOGDIR)/worker.log 2>&1 & echo "$$!" > $(LOGDIR)/worker.pid
	@sleep 1
	@echo ""
	@echo "  Backend   http://localhost:8001/docs   (pid $$(cat $(LOGDIR)/backend.pid), log $(LOGDIR)/backend.log)"
	@echo "  Frontend  http://localhost:3001        (pid $$(cat $(LOGDIR)/frontend.pid), log $(LOGDIR)/frontend.log)"
	@echo "  Worker    import jobs                   (pid $$(cat $(LOGDIR)/worker.pid), log $(LOGDIR)/worker.log)"
	@echo "  make logs — tail all    ·    make stop — stop all"

dev-be: ## (Re)start the backend only, in the background
	@mkdir -p $(LOGDIR)
	@lsof -ti:8001 | xargs kill 2>/dev/null || true
	@nohup sh -c '$(call BUILD_INFO,backend) && $(BACKEND) && $(BE_ENV) && exec uv run uvicorn protcellar.interface.app:app --reload --port 8001' \
		> $(LOGDIR)/backend.log 2>&1 & echo "$$!" > $(LOGDIR)/backend.pid
	@echo "Backend (re)started on :8001 (log $(LOGDIR)/backend.log)"

dev-fe: ## (Re)start the frontend only, in the background
	@mkdir -p $(LOGDIR)
	@lsof -ti:3001 | xargs kill 2>/dev/null || true
	@nohup sh -c '$(call BUILD_INFO,frontend) && $(FRONTEND) && exec pnpm dev' \
		> $(LOGDIR)/frontend.log 2>&1 & echo "$$!" > $(LOGDIR)/frontend.pid
	@echo "Frontend (re)started on :3001 (log $(LOGDIR)/frontend.log)"

dev-worker: ## (Re)start the import worker only, in the background
	@mkdir -p $(LOGDIR)
	@[ -f $(LOGDIR)/worker.pid ] && kill $$(cat $(LOGDIR)/worker.pid) 2>/dev/null || true
	@pkill -f 'arq protcellar.infrastructure.ingestion.worker.WorkerSettings' 2>/dev/null || true
	@nohup sh -c '$(BACKEND) && $(BE_ENV) && exec $(WORKER)' \
		> $(LOGDIR)/worker.log 2>&1 & echo "$$!" > $(LOGDIR)/worker.pid
	@echo "Import worker (re)started (log $(LOGDIR)/worker.log)"

stop: ## Stop the backend + frontend + worker dev processes
	@[ -f $(LOGDIR)/backend.pid ]  && kill $$(cat $(LOGDIR)/backend.pid)  2>/dev/null || true
	@[ -f $(LOGDIR)/frontend.pid ] && kill $$(cat $(LOGDIR)/frontend.pid) 2>/dev/null || true
	@[ -f $(LOGDIR)/worker.pid ]   && kill $$(cat $(LOGDIR)/worker.pid)   2>/dev/null || true
	@lsof -ti:8001 | xargs kill 2>/dev/null || true
	@lsof -ti:3001 | xargs kill 2>/dev/null || true
	@pkill -f 'arq protcellar.infrastructure.ingestion.worker.WorkerSettings' 2>/dev/null || true
	@rm -f $(LOGDIR)/backend.pid $(LOGDIR)/frontend.pid $(LOGDIR)/worker.pid
	@echo "Dev servers stopped."

logs: ## Tail backend + frontend + worker dev logs
	@mkdir -p $(LOGDIR) && touch $(LOGDIR)/backend.log $(LOGDIR)/frontend.log $(LOGDIR)/worker.log
	tail -f $(LOGDIR)/backend.log $(LOGDIR)/frontend.log $(LOGDIR)/worker.log

generate-api: ## Refresh the OpenAPI snapshot from the backend + regenerate the TS client
	$(BACKEND) && $(BE_ENV) && uv run python -c \
		"import json,sys; from protcellar.interface.app import app; sys.stdout.write(json.dumps(app.openapi(), indent=2))" \
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

security-scan: ## Trivy gate before a release: lockfiles + secrets, then both images; fails on fixable HIGH/CRITICAL
	@command -v trivy >/dev/null || { echo "trivy is not installed: brew install trivy"; exit 1; }
	trivy fs --scanners vuln,secret --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
	  --skip-dirs node_modules,.venv,.next,.logs,backup-data .
	$(COMPOSE_BUILD) build backend frontend
	trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 prot-cellar-backend:local
	trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 prot-cellar-frontend:local

nuke: ## Stop containers and DELETE all data volumes
	$(COMPOSE_INFRA) down -v

# ── Production (GHCR images; settings in ./.env, see .env.example) ──

prod-pull: ## Pull the prod images (PROT_CELLAR_TAG=<tag>, default latest)
	$(COMPOSE_PROD) pull

prod-up: ## Start the prod stack from GHCR images (migrations run first)
	$(COMPOSE_PROD) up -d
	@echo "Prod stack up. Backend :8001  Frontend :3001  (make prod-logs to follow)"

prod-down: ## Stop the prod stack (keep data)
	$(COMPOSE_PROD) down

prod-logs: ## Tail prod app logs
	$(COMPOSE_PROD) logs -f migrate backend worker frontend
