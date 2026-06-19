# prot-cellar frontend

Next.js 16 frontend for prot-cellar — a biological sequence and target registry. Mirrors chem-cellar's architecture with a biology accent.

## Architecture

Feature-sliced layout:

```
src/
  app/          # Next.js App Router pages and API routes
  features/     # Domain feature slices (proteins, targets, taxonomy, …)
  shared/       # Design system, hooks, API client, utilities
```

Shared components follow the bio accent design token palette (teal/blue primary on neutral slate). The API client is generated from `openapi.json` via [orval](https://orval.dev/).

---

## Prerequisites

- Node 22 + pnpm 11 (`corepack enable`)
- Docker (for the backend stack)

---

## Local development

### 1. Start the backend

From the repo root:

```bash
make up    # starts Postgres + backend API on :8001
make dev   # starts the FastAPI dev server (if not included in make up)
```

The backend API listens on `http://localhost:8001`.

### 2. Install frontend dependencies

```bash
cd frontend
pnpm install
```

### 3. Start the dev server

```bash
pnpm dev   # Next.js on http://localhost:3000 (Turbopack)
```

---

## API client

The typed API client lives in `src/shared/lib/api/generated/` and is generated from the committed OpenAPI snapshot at `frontend/openapi.json`.

### Regenerate after a backend API change

1. Export a fresh schema from the running backend:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar \
  uv run python -c \
  "import json,sys; from protcellar.interface.app import app; sys.stdout.write(json.dumps(app.openapi()))" \
  > ../frontend/openapi.json
```

2. Regenerate the client:

```bash
cd ../frontend
pnpm generate:api
```

Commit both `openapi.json` and the regenerated files together so the snapshot and client are always in sync.

---

## Common commands

| Command | Description |
|---|---|
| `pnpm dev` | Dev server on :3000 (Turbopack) |
| `pnpm build` | Production build (outputs `.next/standalone`) |
| `pnpm start` | Serve the production build locally |
| `pnpm lint` | Biome check (exits 0 on warnings, non-zero on errors) |
| `pnpm lint:fix` | Biome auto-fix |
| `pnpm test` | Vitest — run all tests once |
| `pnpm test:watch` | Vitest — watch mode |
| `pnpm generate:api` | Regenerate API client from `openapi.json` |

---

## Docker

Build a production image:

```bash
docker build \
  --build-arg APP_VERSION=1.0.0 \
  --build-arg APP_GIT_SHA=$(git rev-parse --short HEAD) \
  --build-arg APP_BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  -t prot-cellar-frontend:local \
  frontend/
```

The image uses a multi-stage build (base → deps → builder → runner), runs as a non-root user (`cellar`, uid 1001), and exposes port 3000. Runtime config (API URL, auth settings) is served from the `/api/config` endpoint — no secrets are baked into the image.
