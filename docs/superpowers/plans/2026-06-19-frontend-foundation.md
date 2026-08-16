# Frontend Foundation (Plan 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the prot-cellar Next.js app shell — tooling, design system (bio accent), auth, runtime config, layout shell, API-client plumbing, and the bio shared components — so feature plans (1–5) can drop in context slices with zero plumbing work.

**Architecture:** Fresh Next 16 / React 19 app under `frontend/`, feature-sliced (`app/`, `features/`, `shared/`), mirroring chem-cellar's frontend (`~/workspace/chem-vault2/frontend`). Port chem-cellar's shared plumbing verbatim where it is domain-neutral; write novel code (design tokens, bio components, navigation) fresh. Server state via TanStack Query + orval-generated hooks; auth via Sentinel with a runtime-config BFF.

**Tech Stack:** Next 16 (App Router, `output: "standalone"`), React 19, TypeScript strict, Tailwind 4 (OKLch tokens), shadcn (new-york/zinc), radix-ui, TanStack Query v5, orval, `@duar-auth/*` 0.11, ag-grid, react-hook-form + zod, zustand, sonner, biome, vitest. Package manager: **pnpm**.

## Global Constraints

- **Reference frontend (normative):** `~/workspace/chem-vault2/frontend`. When a task says "port", copy that exact file and apply only the listed changes. Do not invent structure that diverges from the reference.
- **Spec:** `docs/superpowers/specs/2026-06-19-prot-cellar-frontend-design.md`. Every task implicitly inherits it.
- **Frontend location:** `/Users/sidx/workspace/prot-cellar/frontend/` (monorepo, sibling of `backend/`). Branch: `feat/frontend`.
- **Backend dev server:** prot-cellar runs on **port 8001** (`make up` then `make dev`), serves `/openapi.json`, API prefix `/api/v1`. chem-cellar uses 8000 — never point at 8000.
- **Dropped chem-only deps (must NOT appear in package.json):** `@rdkit/rdkit`, `ketcher-*`, `plotly.js`, `react-plotly.js`, `exceljs`, `papaparse`, `@types/papaparse`, `@types/react-plotly.js`, `react-dropzone`, `react-resizable-panels`, `gsap`.
- **Sentinel:** same identity-service as chem-cellar. `DUAR_URL=http://localhost:9003`, `DUAR_SERVICE_NAME=protcellar`.
- **Lint/format:** biome (2-space, 100 cols). `biome.json` ignores `src/shared/lib/api/` (generated) and `src/shared/components/ui/` (shadcn).
- **Path alias:** `@/*` → `./src/*`.
- **TDD policy:** Tasks producing pure logic (string/number/data transforms, validators) follow strict red→green TDD with the test code inlined. Tasks that scaffold/configure/port files (no testable pure logic) use a **verification gate** instead — an exact command plus expected output — clearly labeled "Verify".
- **Commit cadence:** one commit per task minimum, on `feat/frontend`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

```
frontend/
  package.json                          # T1  pinned deps (chem versions minus chem-only)
  pnpm-workspace.yaml tsconfig.json     # T1
  next.config.ts next-env.d.ts          # T1  (no fs-stub alias — that was RDKit-only)
  biome.json components.json            # T1
  postcss.config.mjs                    # T2
  .env.example .env.local .gitignore .dockerignore  # T1
  orval.config.ts                       # T6
  vitest.config.ts vitest.setup.ts      # T15
  Dockerfile                            # T15
  public/                               # T1 (favicon etc.)
  src/
    app/
      globals.css                       # T2  OKLch tokens, bio accent
      layout.tsx                        # T11 root: providers + fonts + Toaster + CommandPalette
      (dashboard)/layout.tsx page.tsx   # T11 auth guard + shell; dashboard placeholder
      login/page.tsx                    # T11
      auth/callback/page.tsx            # T11
      api/config/route.ts               # T9  runtime config
      api/auth/mint/route.ts            # T9  Sentinel BFF
    features/                           # (empty in Plan 0; populated by feature plans)
    shared/
      lib/
        utils.ts                        # T4  cn()
        api/custom-instance.ts          # T5  mutator + setApiBaseUrl + ApiError + API_V1
        api/endpoints.ts api/model/     # T6  GENERATED (orval)
        api/crud-hooks.ts               # T7  createCrudHooks + unwrapList
        auth/config.ts                  # T9  getDuarClient()
        toast.ts                        # T8  showSuccess/showError/showInfo
        navigation.ts                   # T10 sidebar/breadcrumb config (bio)
      providers/
        query-provider.tsx              # T7
        theme-provider.tsx              # T7
        auth-provider.tsx               # T9
      components/
        ui/                             # T3  ported shadcn primitives
        layout/                         # T10 AppSidebar, Header, NavMain, UserMenu, WorkspaceSwitcher
        data-grid/data-grid.tsx        # T12 ag-grid wrapper
        sequence/sequence-viewer.tsx   # T13 + sequence.ts (pure)
        xrefs/cross-reference-links.tsx# T13
        common/command-palette.tsx     # T14
      hooks/  types/                    # shared misc (as needed)
```

---

### Task 1: Scaffold Next app + base tooling

**Files:**
- Create: `frontend/package.json`, `frontend/pnpm-workspace.yaml`, `frontend/tsconfig.json`, `frontend/next.config.ts`, `frontend/next-env.d.ts`, `frontend/biome.json`, `frontend/components.json`, `frontend/.gitignore`, `frontend/.dockerignore`, `frontend/.env.example`, `frontend/.env.local`, `frontend/public/.gitkeep`
- Reference: `~/workspace/chem-vault2/frontend/{package.json,tsconfig.json,biome.json,components.json,next.config.ts}`

**Interfaces:**
- Produces: an installable Next app with biome + path alias `@/*`. Later tasks rely on `pnpm`, `@/` imports, and the dep set below.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "protcellar-frontend",
  "version": "0.1.0",
  "packageManager": "pnpm@11.0.8",
  "private": true,
  "scripts": {
    "dev": "next dev --turbopack --port 3000",
    "build": "next build",
    "start": "next start",
    "lint": "biome check src/",
    "lint:fix": "biome check --write src/",
    "test": "vitest run",
    "test:watch": "vitest",
    "generate:api": "orval"
  },
  "dependencies": {
    "@hookform/resolvers": "^5.0.0",
    "@duar-auth/js": "^0.11.0",
    "@duar-auth/nextjs": "^0.11.0",
    "@duar-auth/react": "^0.11.0",
    "@tabler/icons-react": "^3.41.1",
    "@tanstack/react-query": "^5.80.0",
    "@tanstack/react-virtual": "^3.13.24",
    "ag-grid-community": "^35.2.0",
    "ag-grid-react": "^35.2.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.0",
    "cmdk": "^1.1.1",
    "lucide-react": "^0.525.0",
    "next": "^16.2.2",
    "next-themes": "^0.4.6",
    "radix-ui": "^1.4.3",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "react-hook-form": "^7.56.0",
    "sonner": "^2.0.0",
    "tailwind-merge": "^3.3.0",
    "zod": "^3.25.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@biomejs/biome": "^1.9.0",
    "@tailwindcss/postcss": "^4.1.0",
    "@testing-library/dom": "^10.4.0",
    "@testing-library/jest-dom": "^6.9.1",
    "@testing-library/react": "^16.3.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "@vitejs/plugin-react": "^4.5.0",
    "jsdom": "^26.1.0",
    "orval": "^7.10.0",
    "tailwindcss": "^4.1.0",
    "typescript": "^5.8.0",
    "vitest": "^3.2.0"
  }
}
```

- [ ] **Step 2: Create config files**

`frontend/pnpm-workspace.yaml`:
```yaml
packages: []
```

`frontend/tsconfig.json` — copy `~/workspace/chem-vault2/frontend/tsconfig.json` verbatim (it already has strict, `@/*` alias, next plugin, bundler resolution).

`frontend/next.config.ts` (note: NO `turbopack.resolveAlias.fs` — that was an RDKit workaround):
```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

`frontend/next-env.d.ts`:
```ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

`frontend/biome.json` — copy `~/workspace/chem-vault2/frontend/biome.json` verbatim (its ignore globs already cover `src/shared/lib/api/` and `src/shared/components/ui/`).

`frontend/components.json` — copy `~/workspace/chem-vault2/frontend/components.json` verbatim (new-york, zinc, `@/shared/...` aliases, css `src/app/globals.css`).

`frontend/.gitignore`:
```
node_modules
.next
.env.local
*.tsbuildinfo
next-env.d.ts
coverage
```

`frontend/.dockerignore`:
```
node_modules
.next
.env.local
tests
```

`frontend/.env.example`:
```
APP_URL=http://localhost:3000
APP_API_BASE_URL=http://localhost:8001
APP_DUAR_URL=http://localhost:9003
APP_DUAR_SERVICE_NAME=protcellar
APP_DUAR_SERVICE_KEY=
APP_DUAR_GOOGLE_CLIENT_ID=
APP_DUAR_ENTRA_CLIENT_ID=
APP_DUAR_ENTRA_TENANT_ID=
```

`frontend/.env.local` — copy `.env.example` (dev values; service key left blank for now). `frontend/public/.gitkeep` — empty.

- [ ] **Step 3 (Verify): install + biome on an empty src**

Run:
```bash
cd /Users/sidx/workspace/prot-cellar/frontend && mkdir -p src && pnpm install
```
Expected: install completes, `node_modules/` present, **no** `@rdkit`/`ketcher`/`plotly` in the tree (`ls node_modules | grep -E 'rdkit|ketcher|plotly'` → empty).

- [ ] **Step 4: Commit**

```bash
cd /Users/sidx/workspace/prot-cellar && git add frontend/ && git commit -m "chore(frontend): scaffold Next 16 app + tooling (pnpm, biome, tsconfig)"
```

---

### Task 2: Design system — Tailwind 4 + bio-accent OKLch tokens

**Files:**
- Create: `frontend/postcss.config.mjs`, `frontend/src/app/globals.css`
- Reference: `~/workspace/chem-vault2/frontend/{postcss.config.mjs,src/app/globals.css}`

**Interfaces:**
- Produces: CSS variables (`--primary`, `--background`, `--sidebar-*`, radius, fonts) consumed by every shadcn component and feature. Primary hue = biology teal/emerald.

- [ ] **Step 1: Create `frontend/postcss.config.mjs`** — copy chem-cellar's verbatim:
```js
const config = {
  plugins: ["@tailwindcss/postcss"],
};
export default config;
```

- [ ] **Step 2: Create `frontend/src/app/globals.css`** — start from chem-cellar's `globals.css` (keep the full `@theme`/token structure, light/dark blocks, radius scale, `--font-sans`/`--font-mono`, sidebar token set, base layer). Apply ONLY these hue changes so prot-cellar reads as the bio sibling:

```css
/* :root (light) — primary shifts blue→teal; success nudged green to stay distinct */
--primary: oklch(0.55 0.11 185);
--primary-foreground: oklch(0.985 0.005 185);
--ring: oklch(0.55 0.11 185);
--sidebar-primary: oklch(0.55 0.11 185);
--sidebar-ring: oklch(0.55 0.11 185);
--success: oklch(0.5 0.13 150);
--info: oklch(0.55 0.12 230);

/* .dark — same hue family, lifted lightness for contrast */
--primary: oklch(0.7 0.12 185);
--primary-foreground: oklch(0.16 0.02 185);
--ring: oklch(0.7 0.12 185);
--sidebar-primary: oklch(0.7 0.12 185);
--sidebar-ring: oklch(0.7 0.12 185);
--success: oklch(0.62 0.14 150);
--info: oklch(0.68 0.12 230);
```
Leave `--destructive`, `--warning`, `--background`, `--foreground`, `--border`, `--muted`, radius, and font variables exactly as chem-cellar has them.

- [ ] **Step 3 (Verify): dev server compiles tokens**

Run:
```bash
cd /Users/sidx/workspace/prot-cellar/frontend && timeout 25 pnpm dev >/tmp/pc-dev.log 2>&1; grep -iE "ready|compiled|error" /tmp/pc-dev.log | head
```
Expected: "Ready"/"compiled" with no CSS errors. (A minimal `app/layout.tsx`/`page.tsx` is added in T11; for this check, add a temporary `src/app/page.tsx` returning `<main>ok</main>` and `src/app/layout.tsx` importing `./globals.css`, then remove the temporaries after verifying — or defer this Verify to T11. If deferring, just confirm the file parses with `pnpm exec biome check src/app/globals.css` is not applicable to CSS; instead `pnpm exec tsc --noEmit` after T11.)

- [ ] **Step 4: Commit**
```bash
git add frontend/postcss.config.mjs frontend/src/app/globals.css && git commit -m "feat(frontend): Tailwind 4 design tokens with biology teal accent"
```

---

### Task 3: Port shadcn UI primitives

**Files:**
- Create: `frontend/src/shared/components/ui/*` (port subset)
- Reference: `~/workspace/chem-vault2/frontend/src/shared/components/ui/`

**Interfaces:**
- Produces: shadcn primitives used across the app: `button`, `input`, `label`, `textarea`, `select`, `dialog`, `dropdown-menu`, `sidebar`, `skeleton`, `badge`, `separator`, `tooltip`, `sheet`, `command`, `sonner`, `scroll-area`, `tabs`, `avatar`, `collapsible`, `breadcrumb`, `card`. (Add others later as features need them.)

- [ ] **Step 1: Copy the primitive set** — copy each listed file from chem-cellar's `ui/` verbatim. They depend only on `@/shared/lib/utils` (`cn`, Task 4), radix-ui, CVA, and the CSS tokens (Task 2) — all domain-neutral.

```bash
cd /Users/sidx/workspace/prot-cellar/frontend
mkdir -p src/shared/components/ui
for f in button input label textarea select dialog dropdown-menu sidebar skeleton badge separator tooltip sheet command sonner scroll-area tabs avatar collapsible breadcrumb card; do
  cp ~/workspace/chem-vault2/frontend/src/shared/components/ui/$f.tsx src/shared/components/ui/$f.tsx
done
ls src/shared/components/ui
```
Expected: 21 `.tsx` files. (If a referenced file does not exist in chem-cellar, generate it instead with `pnpm dlx shadcn@latest add <name>`.)

- [ ] **Step 2 (Verify): typecheck deferred** — these import `@/shared/lib/utils` (Task 4); typecheck happens at the end of Task 4. No commit yet if `utils.ts` is absent — proceed to Task 4, then commit both together.

- [ ] **Step 3: Commit (after Task 4 lands `utils.ts`)**
```bash
git add frontend/src/shared/components/ui && git commit -m "feat(frontend): port shadcn ui primitives (new-york)"
```

---

### Task 4: `cn()` utility (TDD)

**Files:**
- Create: `frontend/src/shared/lib/utils.ts`, `frontend/src/shared/lib/utils.test.ts`

**Interfaces:**
- Produces: `cn(...inputs: ClassValue[]): string` — clsx + tailwind-merge. Consumed by all `ui/` components.

- [ ] **Step 1: Write the failing test** — `frontend/src/shared/lib/utils.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("joins class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });
  it("dedupes conflicting tailwind classes (last wins)", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
  it("drops falsy values", () => {
    expect(cn("a", false, undefined, "b")).toBe("a b");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/utils.test.ts`
Expected: FAIL — cannot resolve `./utils`. (vitest config lands in T15; if vitest isn't wired yet, temporarily run `pnpm exec vitest run src/shared/lib/utils.test.ts --globals --environment node` — or reorder T15 before this task.)

- [ ] **Step 3: Write minimal implementation** — `frontend/src/shared/lib/utils.ts`:
```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/utils.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit** (with the Task 3 `ui/` files)
```bash
git add frontend/src/shared/lib/utils.ts frontend/src/shared/lib/utils.test.ts frontend/src/shared/components/ui && git commit -m "feat(frontend): cn() utility + port shadcn ui primitives"
```

---

### Task 5: API client `customInstance` mutator (TDD)

**Files:**
- Create: `frontend/src/shared/lib/api/custom-instance.ts`, `frontend/src/shared/lib/api/custom-instance.test.ts`
- Reference: `~/workspace/chem-vault2/frontend/src/shared/lib/api/custom-instance.ts`

**Interfaces:**
- Produces:
  - `setApiBaseUrl(url: string): void`
  - `customInstance<T>(config: { url: string; method: string; params?: Record<string, unknown>; data?: unknown; headers?: Record<string, string>; signal?: AbortSignal }): Promise<T>`
  - `class ApiError extends Error { status: number; detail: unknown }`
  - `const API_V1 = "/api/v1"`
- Consumes: `getAuthHeaders()` from `@/shared/lib/auth/config` (Task 9). **For TDD isolation, the test mocks that module.**

- [ ] **Step 1: Write the failing test** — `frontend/src/shared/lib/api/custom-instance.test.ts`:
```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/auth/config", () => ({
  getAuthHeaders: () => ({ Authorization: "Bearer test-token" }),
}));

import { ApiError, API_V1, customInstance, setApiBaseUrl } from "./custom-instance";

const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  setApiBaseUrl("http://localhost:8001");
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("customInstance", () => {
  it("prefixes the base URL and attaches auth header", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "1" }));
    const out = await customInstance<{ id: string }>({ url: "/api/v1/proteins/P1", method: "GET" });
    expect(out).toEqual({ id: "1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8001/api/v1/proteins/P1");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("serializes array params as repeated keys (FastAPI list[T])", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await customInstance({ url: "/api/v1/proteins", method: "GET", params: { id: ["a", "b"], q: "x" } });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("id=a&id=b");
    expect(url).toContain("q=x");
  });

  it("returns undefined for 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const out = await customInstance<undefined>({ url: "/api/v1/x", method: "DELETE" });
    expect(out).toBeUndefined();
  });

  it("throws ApiError carrying status + detail on non-2xx", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "nope" }, 409));
    await expect(customInstance({ url: "/api/v1/x", method: "POST" })).rejects.toMatchObject({
      status: 409,
      detail: "nope",
    });
    await expect(customInstance({ url: "/api/v1/x", method: "POST" })).rejects.toBeInstanceOf(ApiError);
  });

  it("exposes API_V1 constant", () => {
    expect(API_V1).toBe("/api/v1");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/api/custom-instance.test.ts`
Expected: FAIL — cannot resolve `./custom-instance`.

- [ ] **Step 3: Write the implementation** — port chem-cellar's `custom-instance.ts` and verify it satisfies the contract above (it already implements base-url injection, repeated-key array params, 204→undefined, `ApiError` with `detail`, `API_V1`, JSON content-type unless `FormData`, merges `getAuthHeaders()`). If any behavior differs from the test, adjust the test ONLY if chem-cellar's behavior is the intended contract; otherwise adjust the port. Key shape:
```ts
import { getAuthHeaders } from "@/shared/lib/auth/config";

export const API_V1 = "/api/v1";
let _baseUrl = "";
export function setApiBaseUrl(url: string): void {
  _baseUrl = url.replace(/\/$/, "");
}
export class ApiError extends Error {
  constructor(public status: number, message: string, public detail: unknown) {
    super(message);
    this.name = "ApiError";
  }
}
export async function customInstance<T>(config: {
  url: string; method: string;
  params?: Record<string, unknown>; data?: unknown;
  headers?: Record<string, string>; signal?: AbortSignal;
}): Promise<T> {
  // build query string with repeated keys for array values
  // merge getAuthHeaders() + config.headers; set JSON content-type unless FormData
  // fetch(`${_baseUrl}${config.url}${qs}`, {...})
  // 204 → undefined; non-2xx → throw new ApiError(status, msg, parsedBody?.detail ?? parsedBody)
}
```

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/api/custom-instance.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**
```bash
git add frontend/src/shared/lib/api/custom-instance.ts frontend/src/shared/lib/api/custom-instance.test.ts && git commit -m "feat(frontend): API client customInstance mutator (base url, auth, array params, ApiError)"
```

---

### Task 6: orval config + first API generation

**Files:**
- Create: `frontend/orval.config.ts`
- Generates: `frontend/src/shared/lib/api/endpoints.ts`, `frontend/src/shared/lib/api/model/*`
- Create (fallback): `frontend/openapi.json` (snapshot, gitignored from biome but committed)

**Interfaces:**
- Produces: orval react-query hooks + DTO types for all 8 backend route groups, consumed by feature plans.

- [ ] **Step 1: Create `frontend/orval.config.ts`** — copy chem-cellar's, changing the package key and port:
```ts
import { defineConfig } from "orval";

export default defineConfig({
  protcellar: {
    input: { target: "http://localhost:8001/openapi.json" },
    output: {
      target: "src/shared/lib/api/endpoints.ts",
      schemas: "src/shared/lib/api/model",
      client: "react-query",
      mode: "tags-split",
      override: {
        mutator: { path: "src/shared/lib/api/custom-instance.ts", name: "customInstance" },
        query: { useQuery: true },
      },
    },
  },
});
```

- [ ] **Step 2: Bring the backend up and snapshot its OpenAPI**
Run:
```bash
cd /Users/sidx/workspace/prot-cellar && make up && (cd backend && DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar uv run uvicorn protcellar.interface.app:app --port 8001 >/tmp/pc-api.log 2>&1 &) && sleep 6 && curl -fsS http://localhost:8001/openapi.json -o frontend/openapi.json && head -c 200 frontend/openapi.json
```
Expected: `openapi.json` written, starts with `{"openapi":"3.1.0"...`. If Sentinel blocks `/openapi.json`, it is in the exclude list (`app.py:51`) so it should be public.

- [ ] **Step 3 (Verify): generate the client**
Run: `cd frontend && pnpm generate:api && ls src/shared/lib/api && ls src/shared/lib/api/model | head`
Expected: `endpoints.ts` + per-tag files + `model/` populated. (orval reads the live URL; the snapshot is the offline fallback — if the server is down, temporarily set `input.target: "./openapi.json"` and regenerate.)

- [ ] **Step 4 (Verify): typecheck the generated client**
Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors (the generated code references `customInstance` from Task 5).

- [ ] **Step 5: Commit**
```bash
git add frontend/orval.config.ts frontend/openapi.json frontend/src/shared/lib/api/endpoints.ts frontend/src/shared/lib/api/model && git commit -m "feat(frontend): orval config + generated API client (8001 OpenAPI)"
```

---

### Task 7: Query provider, theme provider, CRUD-hooks factory (TDD for `unwrapList`)

**Files:**
- Create: `frontend/src/shared/providers/query-provider.tsx`, `frontend/src/shared/providers/theme-provider.tsx`, `frontend/src/shared/lib/api/crud-hooks.ts`, `frontend/src/shared/lib/api/crud-hooks.test.ts`
- Reference: chem-cellar's `providers/query-provider.tsx`, `providers/theme-provider.tsx`, and its CRUD-hooks factory.

**Interfaces:**
- Produces:
  - `<QueryProvider>` (QueryClient: `staleTime` default 60s, `retry: 1`, MutationCache global error → `showError`).
  - `<ThemeProvider>` (next-themes, `attribute="class"`, `defaultTheme="dark"`, `enableSystem`).
  - `unwrapList<T>(data: T[] | { items: T[] } | undefined): T[]`
  - `createCrudHooks<T>(opts)` factory (used by feature plans).

- [ ] **Step 1: Write the failing test** — `frontend/src/shared/lib/api/crud-hooks.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { unwrapList } from "./crud-hooks";

describe("unwrapList", () => {
  it("passes through a bare array", () => {
    expect(unwrapList([1, 2, 3])).toEqual([1, 2, 3]);
  });
  it("unwraps a paginated {items} envelope", () => {
    expect(unwrapList({ items: [1, 2], next_cursor: "x" } as never)).toEqual([1, 2]);
  });
  it("returns [] for undefined", () => {
    expect(unwrapList(undefined)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/api/crud-hooks.test.ts`
Expected: FAIL — cannot resolve `./crud-hooks`.

- [ ] **Step 3: Implement** — `crud-hooks.ts` with `unwrapList` + the `createCrudHooks` factory (port chem-cellar's factory shape: `useGet/useCreate/useUpdate/useDelete/useAction` over `customInstance`, invalidating the feature query key and toasting on success). `query-provider.tsx` + `theme-provider.tsx` ported from chem-cellar verbatim (domain-neutral).
```ts
export function unwrapList<T>(data: T[] | { items: T[] } | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.items;
}
```

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/api/crud-hooks.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**
```bash
git add frontend/src/shared/providers/query-provider.tsx frontend/src/shared/providers/theme-provider.tsx frontend/src/shared/lib/api/crud-hooks.ts frontend/src/shared/lib/api/crud-hooks.test.ts && git commit -m "feat(frontend): query/theme providers + createCrudHooks factory + unwrapList"
```

---

### Task 8: Toast wrapper

**Files:**
- Create: `frontend/src/shared/lib/toast.ts`
- Reference: chem-cellar's `src/shared/lib/toast.ts`

**Interfaces:**
- Produces: `showSuccess(msg)`, `showError(msg | unknown)`, `showInfo(msg)` over sonner. `showError` unwraps `ApiError.detail`/`Error.message`/string.

- [ ] **Step 1: Port** chem-cellar's `toast.ts` verbatim; ensure `showError` handles `ApiError` (from Task 5) by surfacing `.detail` when it is a string, else `.message`.

- [ ] **Step 2 (Verify): typecheck**
Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**
```bash
git add frontend/src/shared/lib/toast.ts && git commit -m "feat(frontend): toast wrapper (showSuccess/showError/showInfo)"
```

---

### Task 9: Auth — Sentinel client, providers, BFF + config routes

**Files:**
- Create: `frontend/src/shared/lib/auth/config.ts`, `frontend/src/shared/providers/auth-provider.tsx`, `frontend/src/app/api/config/route.ts`, `frontend/src/app/api/auth/mint/route.ts`
- Reference: chem-cellar's `src/shared/lib/auth/config.ts`, `src/shared/providers/auth-provider.tsx`, `src/app/api/config/route.ts`, `src/app/api/auth/mint/route.ts`

**Interfaces:**
- Produces:
  - `getDuarClient()` singleton; `getAuthHeaders(): Record<string,string>` (consumed by Task 5).
  - `<AuthProvider>` — fetches `/api/config`, calls `setApiBaseUrl()`, mounts `AppConfigProvider` + Sentinel `AuthzProvider`.
  - `GET /api/config` — returns `{ apiBaseUrl, duarUrl, serviceName, idp:{...}, appUrl, build:{...} }` from `APP_*` env at request time.
  - `POST /api/auth/mint` — BFF that exchanges the IdP token with Sentinel using `APP_DUAR_SERVICE_KEY` (server-only).

- [ ] **Step 1: Port the four files** from chem-cellar, changing only:
  - service name → `protcellar` (read from `APP_DUAR_SERVICE_NAME`).
  - default API base URL fallback → `http://localhost:8001`.
  - `redirectUri` → `${appUrl}/auth/callback`, `mintEndpoint: "/api/auth/mint"` (unchanged).
  - Keep `getAuthHeaders` wired so Task 5's mock contract (`{ Authorization }`) holds at runtime.

- [ ] **Step 2 (Verify): config route serves env at runtime**
Run (after a minimal `app/layout.tsx` exists from T11, or standalone):
```bash
cd frontend && timeout 30 pnpm dev >/tmp/pc-fe.log 2>&1 & sleep 12 && curl -fsS http://localhost:3000/api/config | head -c 200; kill %1 2>/dev/null
```
Expected: JSON with `apiBaseUrl: "http://localhost:8001"` and `serviceName: "protcellar"`. (If T11 hasn't run, this Verify moves to the end of T11.)

- [ ] **Step 3 (Verify): typecheck**
Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/shared/lib/auth frontend/src/shared/providers/auth-provider.tsx frontend/src/app/api && git commit -m "feat(frontend): Sentinel auth (client, provider, config + mint BFF routes)"
```

---

### Task 10: Layout shell + navigation config (bio)

**Files:**
- Create: `frontend/src/shared/lib/navigation.ts`, `frontend/src/shared/components/layout/{app-sidebar,header,nav-main,user-menu,workspace-switcher,breadcrumbs,theme-toggle}.tsx`
- Reference: chem-cellar's `src/shared/lib/navigation.ts` + `src/shared/components/layout/*`

**Interfaces:**
- Consumes: `ui/sidebar`, `ui/dropdown-menu`, `ui/breadcrumb` (Task 3); `useAuthz` (Task 9).
- Produces: `<AppSidebar>`, `<Header>`, and the `navigation` config (source of truth for sidebar + breadcrumbs).

- [ ] **Step 1: Write `navigation.ts`** (bio groups + lucide icons):
```ts
import { Dna, FlaskConical, Microscope, Network, Layers, Building2, ScrollText, LayoutDashboard, Boxes } from "lucide-react";

export type NavItem = { title: string; href: string; icon: React.ComponentType<{ className?: string }> };
export type NavGroup = { label: string; items: NavItem[] };

export const navigation: { home: NavItem; groups: NavGroup[] } = {
  home: { title: "Dashboard", href: "/", icon: LayoutDashboard },
  groups: [
    { label: "Catalog", items: [
      { title: "Proteins", href: "/proteins", icon: Dna },
      { title: "Genes", href: "/genes", icon: Network },
      { title: "Targets", href: "/targets", icon: FlaskConical },
    ]},
    { label: "Taxonomy", items: [
      { title: "Organisms", href: "/organisms", icon: Microscope },
      { title: "Strains", href: "/strains", icon: Boxes },
      { title: "Proteomes", href: "/proteomes", icon: Layers },
    ]},
    { label: "Administration", items: [
      { title: "Organizations", href: "/admin/organizations", icon: Building2 },
      { title: "Audit", href: "/admin/audit", icon: ScrollText },
    ]},
  ],
};
```

- [ ] **Step 2: Port the layout components** from chem-cellar, adapting them to consume the `navigation` shape above (chem-cellar's `nav-main` iterates groups; reuse its collapsible + active-path logic). Replace the chem app title/logo text with "prot-cellar". `theme-toggle`, `user-menu`, `workspace-switcher`, `breadcrumbs` are domain-neutral — port verbatim.

- [ ] **Step 3 (Verify): typecheck**
Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/shared/lib/navigation.ts frontend/src/shared/components/layout && git commit -m "feat(frontend): layout shell (sidebar/header/nav) + bio navigation config"
```

---

### Task 11: App routes — root layout, dashboard shell, login, callback

**Files:**
- Create: `frontend/src/app/layout.tsx`, `frontend/src/app/(dashboard)/layout.tsx`, `frontend/src/app/(dashboard)/page.tsx`, `frontend/src/app/login/page.tsx`, `frontend/src/app/auth/callback/page.tsx`
- Reference: chem-cellar's equivalents

**Interfaces:**
- Consumes: providers (Tasks 7, 9), layout shell (Task 10), `CommandPalette` (Task 14 — import lazily / add after T14, or stub then wire).

- [ ] **Step 1: Root `layout.tsx`** — fonts (IBM Plex Sans/Mono via `next/font/google`), `import "./globals.css"`, provider stack `ThemeProvider → AuthProvider → QueryProvider`, `<Toaster position="bottom-right" />`. (Wire `<CommandPalette/>` in T14.)

- [ ] **Step 2: `(dashboard)/layout.tsx`** — `"use client"`; `useAuthz()` guard (skeleton while loading; redirect to `/login` when unauthenticated); render `SidebarProvider → AppSidebar + SidebarInset → Header + <main className="flex-1 overflow-auto p-4">{children}</main>`.

- [ ] **Step 3: `(dashboard)/page.tsx`** — minimal dashboard placeholder: a heading "prot-cellar" + a few `Card`s linking to Proteins/Targets/Organisms (full dashboard is Plan 5). `login/page.tsx` — Sentinel IdP buttons (Google/Entra) on a clean split layout with a CSS-gradient background (NO gsap/GridMotion). `auth/callback/page.tsx` — `AuthzCallback` from `@duar-auth/nextjs`.

- [ ] **Step 4 (Verify): app boots, unauth redirect, /api/config works**
Run:
```bash
cd frontend && timeout 40 pnpm dev >/tmp/pc-fe.log 2>&1 & sleep 14
curl -fsS http://localhost:3000/api/config | grep -o '"serviceName":"protcellar"'
curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:3000/login
kill %1 2>/dev/null
```
Expected: `"serviceName":"protcellar"` printed; `/login` → `200`. Also `pnpm exec tsc --noEmit` clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/app && git commit -m "feat(frontend): root + dashboard layouts, login, auth callback"
```

---

### Task 12: DataGrid wrapper

**Files:**
- Create: `frontend/src/shared/components/data-grid/data-grid.tsx`, `frontend/src/shared/components/data-grid/data-grid.test.tsx`
- Reference: chem-cellar's `src/shared/components/data-grid/`

**Interfaces:**
- Produces: `DataGrid<T>` — props `{ rowData, columnDefs, loading?, height?, onRowClick?, emptyState?, suppressFilters? }` over ag-grid with the app theme + loading/empty states.

- [ ] **Step 1: Write the failing test** — `data-grid.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataGrid } from "./data-grid";

describe("DataGrid", () => {
  it("renders the empty state when there are no rows and not loading", () => {
    render(<DataGrid rowData={[]} columnDefs={[{ field: "name" }]} emptyState={<div>No rows</div>} />);
    expect(screen.getByText("No rows")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && pnpm exec vitest run src/shared/components/data-grid/data-grid.test.tsx`
Expected: FAIL — cannot resolve `./data-grid`.

- [ ] **Step 3: Port** chem-cellar's `data-grid.tsx` (ag-grid wrapper + theme), ensuring the empty-state branch renders `emptyState` when `!loading && rowData.length === 0`. Register ag-grid community modules as chem-cellar does.

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && pnpm exec vitest run src/shared/components/data-grid/data-grid.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/shared/components/data-grid && git commit -m "feat(frontend): DataGrid (ag-grid wrapper) with loading/empty states"
```

---

### Task 13: Bio shared components — SequenceViewer + CrossReferenceLinks (TDD pure cores)

**Files:**
- Create: `frontend/src/shared/components/sequence/sequence.ts`, `sequence.test.ts`, `sequence-viewer.tsx`, `sequence-viewer.test.tsx`
- Create: `frontend/src/shared/components/xrefs/cross-reference-links.tsx`, `cross-reference-links.test.tsx`

**Interfaces:**
- Produces:
  - `chunkSequence(seq: string, perLine?: number): string[]` and `toFasta(header: string, seq: string, width?: number): string` (pure).
  - `<SequenceViewer sequence length mass? accession? />` — monospace, ruler, length/mass badges, copy + FASTA download.
  - `<CrossReferenceLinks items={CrossReference[]} />` — grouped resolvable links (uses each item's resolved `url`).

- [ ] **Step 1: Write the failing test (pure core)** — `sequence.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { chunkSequence, toFasta } from "./sequence";

describe("chunkSequence", () => {
  it("splits into fixed-width lines (default 60)", () => {
    expect(chunkSequence("A".repeat(130)).map((l) => l.length)).toEqual([60, 60, 10]);
  });
  it("honors a custom width", () => {
    expect(chunkSequence("ABCDE", 2)).toEqual(["AB", "CD", "E"]);
  });
  it("returns [] for an empty sequence", () => {
    expect(chunkSequence("")).toEqual([]);
  });
});

describe("toFasta", () => {
  it("emits a header line then wrapped sequence", () => {
    expect(toFasta("sp|P1|X", "ABCDE", 2)).toBe(">sp|P1|X\nAB\nCD\nE");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && pnpm exec vitest run src/shared/components/sequence/sequence.test.ts`
Expected: FAIL — cannot resolve `./sequence`.

- [ ] **Step 3: Implement `sequence.ts`**
```ts
export function chunkSequence(seq: string, perLine = 60): string[] {
  const out: string[] = [];
  for (let i = 0; i < seq.length; i += perLine) out.push(seq.slice(i, i + perLine));
  return out;
}
export function toFasta(header: string, seq: string, width = 60): string {
  return [`>${header}`, ...chunkSequence(seq, width)].join("\n");
}
```

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && pnpm exec vitest run src/shared/components/sequence/sequence.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Implement the components + component tests**
`sequence-viewer.tsx` uses `chunkSequence`/`toFasta` + `ui/badge`, `ui/button`; renders monospace lines with a position ruler, length/mass badges, a copy button (clipboard), and a "Download FASTA" button (Blob). `cross-reference-links.tsx` groups `items` by `database` and renders anchors to each item's resolved `url` (fallback: render accession text when no url).
`sequence-viewer.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SequenceViewer } from "./sequence-viewer";
describe("SequenceViewer", () => {
  it("shows the residue length", () => {
    render(<SequenceViewer sequence={"ACDEFGHIK"} length={9} accession="P1" />);
    expect(screen.getByText(/9/)).toBeInTheDocument();
  });
});
```
`cross-reference-links.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CrossReferenceLinks } from "./cross-reference-links";
describe("CrossReferenceLinks", () => {
  it("renders a resolvable link per xref", () => {
    render(<CrossReferenceLinks items={[{ database: "pdb", accession: "1ABC", url: "https://x/1ABC" }]} />);
    expect(screen.getByRole("link", { name: /1ABC/ })).toHaveAttribute("href", "https://x/1ABC");
  });
});
```

- [ ] **Step 6: Run the component tests**
Run: `cd frontend && pnpm exec vitest run src/shared/components/sequence src/shared/components/xrefs`
Expected: PASS.

- [ ] **Step 7: Commit**
```bash
git add frontend/src/shared/components/sequence frontend/src/shared/components/xrefs && git commit -m "feat(frontend): bio shared components (SequenceViewer, CrossReferenceLinks)"
```

---

### Task 14: CommandPalette (cmdk)

**Files:**
- Create: `frontend/src/shared/components/common/command-palette.tsx`, `command-palette.test.tsx`
- Modify: `frontend/src/app/layout.tsx` (mount it)
- Reference: chem-cellar's command palette

**Interfaces:**
- Produces: `<CommandPalette>` — ⌘K dialog seeded from `navigation` (jump to each page). Entity quick-search added per-context later.

- [ ] **Step 1: Write the failing test** — `command-palette.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CommandPalette } from "./command-palette";
describe("CommandPalette", () => {
  it("lists navigation destinations when open", () => {
    render(<CommandPalette defaultOpen />);
    expect(screen.getByText("Proteins")).toBeInTheDocument();
    expect(screen.getByText("Targets")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && pnpm exec vitest run src/shared/components/common/command-palette.test.tsx`
Expected: FAIL — cannot resolve `./command-palette`.

- [ ] **Step 3: Implement** using `ui/command` (cmdk) + `next/navigation` router; iterate `navigation.home` + `navigation.groups`; support a `defaultOpen` prop for tests and a `⌘K`/`Ctrl+K` listener at runtime. Mount `<CommandPalette/>` in root `layout.tsx`.

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && pnpm exec vitest run src/shared/components/common/command-palette.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/shared/components/common frontend/src/app/layout.tsx && git commit -m "feat(frontend): command palette (cmdk) seeded from navigation"
```

---

### Task 15: vitest config, Dockerfile, full green gate

**Files:**
- Create: `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`, `frontend/Dockerfile`, `frontend/README.md`
- Reference: chem-cellar's `vitest.config.ts`, `vitest.setup.ts`, `Dockerfile`

**Interfaces:**
- Produces: the test runner config (jsdom, globals, `@/` alias, setup polyfills) and a production Docker image (no RDKit copy step).

> **Note:** if any earlier task needed vitest before this task, this task may be reordered to run first. The plan assumes `vitest.config.ts` exists when the first `vitest run` is invoked; if executing strictly in order, create `vitest.config.ts` + `vitest.setup.ts` as the very first action of Task 4.

- [ ] **Step 1: Create `vitest.config.ts`** — port chem-cellar's: `@vitejs/plugin-react`, `environment: "jsdom"`, `globals: true`, `setupFiles: ["./vitest.setup.ts"]`, resolve alias `@` → `./src`.

- [ ] **Step 2: Create `vitest.setup.ts`** — port chem-cellar's: `@testing-library/jest-dom`, ResizeObserver polyfill, in-memory localStorage/sessionStorage, `matchMedia` stub.

- [ ] **Step 3: Create `Dockerfile`** — multi-stage (base → deps → builder → runner), Node 22-alpine, non-root user, `output: standalone`, build args `APP_VERSION/APP_GIT_SHA/APP_BUILD_DATE`, healthcheck `wget http://localhost:3000/`. Port chem-cellar's but **remove the RDKit wasm copy step** and the `postinstall` reference.

- [ ] **Step 4: Write `README.md`** — dev workflow: `make up` + `make dev` (backend on 8001) → `pnpm install` → `pnpm generate:api` → `pnpm dev`; how to regen the client; lint/test commands.

- [ ] **Step 5 (Verify): full green gate**
Run:
```bash
cd /Users/sidx/workspace/prot-cellar/frontend && pnpm lint && pnpm exec tsc --noEmit && pnpm test && pnpm build
```
Expected: biome clean; `tsc` no errors; all vitest suites pass; `next build` succeeds (`.next/` produced).

- [ ] **Step 6: Commit**
```bash
git add frontend/vitest.config.ts frontend/vitest.setup.ts frontend/Dockerfile frontend/README.md && git commit -m "chore(frontend): vitest config, Dockerfile, dev README; full green gate"
```

---

## Subsequent plans (authored at each checkpoint)

Per the spec's checkpoint-per-context cadence, each context gets its own plan written after the
prior checkpoint lands green, reusing the foundation above (orval hooks, `createCrudHooks`,
`DataGrid`, forms, bio components). Scope summary:

- **Plan 1 — Protein Catalog:** proteins (browse/search/detail with `SequenceViewer` +
  `CrossReferenceLinks` + FASTA download) and genes. *(Before Target.)*
- **Plan 2 — Target:** targets list/detail + create/edit with `TargetComponentsEditor`
  enforcing the single-vs-complex cardinality invariant; full workspace-scoped CRUD.
- **Plan 3 — Taxonomy:** organisms (browse/detail + lineage panel), strains (full CRUD),
  proteomes.
- **Plan 4 — Workspace Config / Admin:** organizations admin CRUD.
- **Plan 5 — Audit + Dashboard:** read-only audit timeline; dashboard summary cards.

---

## Self-Review

**Spec coverage (spec §):** §2 approach → T1 (fresh scaffold, dropped deps). §3 architecture →
file-structure + T1–T15. §4 stack/tooling → T1 (deps), T6 (orval), T15 (vitest/Docker). §5
design tokens (bio accent) → T2. §6 bio components → T13 (SequenceViewer, CrossReferenceLinks);
`TargetComponentsEditor` + organism lineage are deferred to Plans 2/3 (correctly — they are
feature-coupled, noted in §6/§12). §8 data flow → T5/T6/T7. §9 auth/config → T9, T11. §10
navigation → T10. §11 testing → TDD tasks + T15. §12 build cadence → this is Plan 0; 1–5 listed
above. §13 open items → T2 (palette pin), T6 (orval/backend + snapshot fallback). §14 out of
scope → nothing built here. No gaps for Plan 0.

**Placeholder scan:** No "TBD/TODO/implement later". Ported tasks cite exact source paths +
explicit changes (actionable, not placeholders). Pure-logic tasks inline full test + impl.

**Type consistency:** `customInstance`/`setApiBaseUrl`/`ApiError`/`API_V1` (T5) match T6 orval
mutator + T7 usage. `getAuthHeaders` (T9) matches T5's mock contract. `unwrapList`/
`createCrudHooks` (T7) consumed by feature plans. `navigation` shape (T10) consumed by T14.
`chunkSequence`/`toFasta` (T13) consumed by `SequenceViewer`. Consistent.

**Ordering caveat fixed:** vitest config (T15) is required by the first TDD task (T4) — the
note in T15 + T7/T4 instructs creating `vitest.config.ts`/`vitest.setup.ts` first if executing
strictly in order.
