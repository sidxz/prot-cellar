# Handoff — Import Hub frontend

**Date:** 2026-06-22
**Author:** previous session (backend complete, FE not started)
**For:** a fresh session that will build the Import Hub admin UI
**Branch context:** the import-hub **backend** is implemented and committed on `feat/import-hub`. There is **no frontend for it yet**. This doc is the starting context — it is NOT a finished plan. Begin with the `brainstorming` skill (open product questions are listed at the end), then `writing-plans`, then TDD per task.

---

## 1. What exists today

- **Backend import API is done and on `feat/import-hub`** (`POST/GET /api/v1/imports`, `GET /api/v1/imports/{id}`, `POST /api/v1/imports/uploads`). Backend design spec: `docs/superpowers/specs/2026-06-22-import-hub-design.md`; backend plan: `docs/superpowers/plans/2026-06-22-import-hub-backend.md`.
- **Imports are API-only.** The only way to run one right now is Swagger (`http://localhost:8001/docs`) or curl. Building the UI is this task.
- **Runtime prereqs** (already true on the dev box): Postgres `:5433` and Valkey `:6380` are up; the **arq worker** must be running or jobs sit in `queued` forever (`uv run --directory backend arq protcellar.infrastructure.ingestion.worker.WorkerSettings`). The worker is a backend concern — the FE just polls run status.

## 2. What to build

An **admin "Import Hub"** under `/admin/imports`:

1. **List** of import runs (paginated) with status, type, target, timestamps.
2. **Start an import** — a dialog whose fields depend on the chosen import type (3 types, below).
3. **Upload** an essentiality file (`.xlsx`/`.tsv`) → get an `upload_ref` to pass into a `gene_enrichment` import.
4. **Detail view** of one run with **live status polling** (`queued → running → succeeded/failed`), current `phase`, `processed/total` progress, the final `summary`, and any `error`.

There is **no cancel** endpoint (deferred per the backend spec) — do not build a cancel action.

---

## 3. Backend API contract (authoritative — verified against code)

Base router: `prefix="/api/v1/imports"`, tag `imports`. Source: `backend/src/protcellar/interface/routes/imports.py`.

### Endpoints & auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/imports` | **admin** | Start a run. Returns `202` + `ImportRunResponse`. |
| `GET` | `/api/v1/imports` | authenticated | List. Query: `cursor?`, `limit?`. Returns `PaginatedResponse<ImportRunResponse>`. |
| `GET` | `/api/v1/imports/{import_run_id}` | authenticated | One run (poll this for status). |
| `POST` | `/api/v1/imports/uploads` | **admin** | `multipart/form-data`, single field **`file`**. Returns `UploadResponse`. |

Auth is enforced **server-side** (`require_admin` / `require_authenticated`). Non-admins get a 403 from start/upload. (See §6 on client-side gating.)

### `StartImportBody` (POST body)
```jsonc
{ "import_type": "proteome" | "gene_enrichment" | "go_ontology",
  "params": { /* type-specific, see below */ } }
```

### Import types & their `params` (from `backend/src/protcellar/application/imports/params.py`)
- **`go_ontology`** — `{ "force": false }` (only `force`). Smallest; good for a smoke test.
- **`proteome`** — `{ "proteome_id": "UP000001584", "force": false, "dry_run": false, "limit": null }`. `proteome_id` **required** (a UniProt proteome id, e.g. M. tuberculosis = `UP000001584`).
- **`gene_enrichment`** — requires **`organism_id` (UUID) OR `tax_id` (int)**; optional `gff_url` (str), `essentiality_url` (str), `essentiality_upload_ref` (UUID, from `/uploads`), `force`. Validation rejects the params if neither organism identifier is present. (Concrete dev data: M. tuberculosis strain H37Rv `tax_id=83332`.)

### `ImportRunResponse` (list items, get, and start return this)
```jsonc
{
  "id": "uuid",
  "import_type": "proteome | gene_enrichment | go_ontology",
  "target_key": "string",                 // e.g. the proteome_id or organism/tax id
  "status": "queued | running | succeeded | failed | cancelled",
  "phase": "string | null",               // human label of current step, e.g. "fetch GFF"
  "progress": { "processed": 0, "total": 0 },
  "summary": { },                          // free-form dict, populated on success
  "source_version": "string | null",
  "error": "string | null",                // populated on failure
  "requested_by": "uuid",
  "upload_ref": "uuid | null",
  "created_at": "iso8601",
  "started_at": "iso8601 | null",
  "finished_at": "iso8601 | null"
}
```

### `UploadResponse`
```jsonc
{ "upload_ref": "uuid-string" }
```
> ⚠️ The multipart field is exactly **`file`**, and the response key is **`upload_ref`** (not `upload_id`). The `.xlsx` is parsed to TSV **server-side**; a bad file returns `422` with `{ "detail": "..." }`. Flow: upload file → get `upload_ref` → start a `gene_enrichment` import with `params.essentiality_upload_ref = <upload_ref>` and an organism identifier.

### Pagination
Cursor-based. `GET /api/v1/imports?cursor=&limit=` → `{ "items": [...], "next_cursor": "string | null" }`. Mirror the cursor-stack pattern in `organization-list.tsx`.

### Statuses (exact enum — `backend/src/protcellar/domain/imports/enums.py`)
`queued`, `running`, `succeeded`, `failed`, `cancelled`. **There is no `failed_validation` status** — map only these five to badge variants.

---

## 4. First step (REQUIRED): regenerate the API client

`frontend/openapi.json` is **stale — it does not contain `/api/v1/imports`**, and there is no `src/shared/lib/api/imports/` folder yet. Before writing any FE code:

```bash
# from repo root, with the backend importable (uv synced)
make generate-api
```
This regenerates `frontend/openapi.json` from `app.openapi()` and runs orval (`pnpm generate:api`) to emit `src/shared/lib/api/imports/imports.ts` (react-query hooks) + `src/shared/lib/api/model/*` types. Config: `frontend/orval.config.ts` (react-query, tags-split, mutator = `custom-instance.ts`).

Generated hook names follow FastAPI operationIds (same scheme as `useListOrganizationsApiV1OrganizationsGet`). After regenerating, **confirm the actual names** — they will be approximately:
- `useStartImportApiV1ImportsPost`
- `useListImportRunsApiV1ImportsGet`
- `useGetImportRunApiV1ImportsImportRunIdGet`
- `useUploadEssentialityFileApiV1ImportsUploadsPost`

---

## 5. Frontend conventions to follow (with concrete references)

**Best template to copy: `src/features/workspace-config/`** (admin organizations — simplest admin CRUD+detail). Mirror its structure:

```
src/features/import-hub/
├── components/  import-list.tsx · import-columns.tsx · start-import-dialog.tsx ·
│                essentiality-upload-dialog.tsx · import-detail.tsx  (+ *.test.tsx)
├── hooks/       use-imports.ts
├── types/       index.ts        (re-export generated models + status/type label maps)
└── index.ts     (barrel)
```

| Concern | Reference file(s) |
|---|---|
| Feature layout template | `src/features/workspace-config/` (simple) · `src/features/target/` (nested form fields) |
| Typed API client + **auth Bearer injection + FormData handling** | `src/shared/lib/api/custom-instance.ts` (detects `data instanceof FormData`, drops `Content-Type`, still injects `getAuthHeaders()`) → `src/shared/lib/auth/config.ts` |
| Hook wrappers over generated hooks | `src/features/workspace-config/hooks/use-organizations.ts` |
| CRUD/query helpers + **global mutation error toast** | `src/shared/lib/api/crud-hooks.ts` · `src/shared/providers/query-provider.tsx` (MutationCache.onError → showError; **don't add per-mutation onError**) |
| Cursor pagination | `src/features/workspace-config/components/organization-list.tsx` (cursor-stack: prev/next) |
| List table | `src/shared/components/data-grid/data-grid.tsx` + `organization-columns.tsx` (ag-grid ColDef + cell renderers) |
| Forms | `organization-form-dialog.tsx` — react-hook-form + zod (`@hookform/resolvers/zod`) + radix UI in `src/shared/components/ui/` (Dialog/Input/Select/Label/Button/Textarea) |
| Toasts | `src/shared/lib/toast.ts` (`showSuccess` / `showError` — `showError` unwraps `ApiError.detail`) |
| Status badges | `src/shared/components/ui/badge.tsx` (variants: default/secondary/success/destructive/warning) |
| Routing | pages live under `src/app/(dashboard)/admin/imports/page.tsx` and `.../[id]/page.tsx`. The `(dashboard)/layout.tsx` already enforces login + renders the sidebar. |
| Nav entry | add `{ title: "Imports", href: "/admin/imports", icon: Upload }` to the **Administration** group in `src/shared/lib/navigation.ts` |

**Live polling** for the detail view: use react-query `refetchInterval` keyed on status, e.g. `refetchInterval: (q) => ["queued","running"].includes(q.state.data?.status) ? 2000 : false`.

**Tooling** (per project memory): run vitest / tsc / biome via `./node_modules/.bin/*` inside `frontend/` — `pnpm exec` is flaky here.

---

## 6. Corrections & gotchas (don't trust generic assumptions)

- **Upload**: multipart field is `file` (only); response is `{ upload_ref }`. No `file_type` field. `.xlsx` parsed server-side; `422 {detail}` on bad file.
- **Statuses**: exactly `queued|running|succeeded|failed|cancelled`. No `failed_validation`.
- **No cancel endpoint** — don't build a cancel button.
- **No client-side role gating exists anywhere in the FE today** (grep for `workspace_role`/`isAdmin`/`role`/`scopes` → nothing). The app relies entirely on server-side enforcement + the existing `/admin/*` routes being login-gated. So the convention-matching default is: show the page to any authenticated user and let admin-only actions (Start / Upload) surface a 403 via the global error toast. **If** product wants the "New import" button hidden for non-admins, that's a *new* capability — how to read the current user's role on the client is an **open question** (the Sentinel `useAuthz()` user shape needs to be confirmed; it is not consumed anywhere yet). Raise this in brainstorming rather than assuming a `user.workspace_role` field.
- `make logs` only tails backend+frontend; the worker logs to `.logs/worker.log` separately.

---

## 7. Suggested build sequence

1. `make generate-api` → confirm `imports/` hooks + models exist.
2. `types/index.ts` — re-export `ImportRunResponse`, `ImportType`, status; add `IMPORT_TYPE_LABELS` / `STATUS_VARIANTS` maps.
3. `hooks/use-imports.ts` — wrap generated list/get/start hooks (+ invalidation/toasts like `use-organizations.ts`) and a `useGetImportRun(id)` with status-based `refetchInterval`; a `useUploadEssentiality()` that posts `FormData`.
4. `import-list.tsx` + `import-columns.tsx` — paginated DataGrid; status badge cell; row → detail.
5. `start-import-dialog.tsx` — type selector that swaps the param sub-form (go_ontology: just `force`; proteome: `proteome_id`; gene_enrichment: organism id/tax_id + optional essentiality upload + gff_url). Reuse the upload dialog or inline it.
6. `essentiality-upload-dialog.tsx` — `<input type="file" accept=".xlsx,.tsv,.txt">` → FormData → `upload_ref`.
7. `import-detail.tsx` — polling status header, phase + processed/total, summary, error.
8. `app/(dashboard)/admin/imports/page.tsx` + `[id]/page.tsx`; add nav entry.
9. Tests alongside each component (vitest); `./node_modules/.bin/tsc --noEmit` + `biome` + `vitest` green.

---

## 8. Open questions for brainstorming (resolve before planning)

1. **Organism selection for `gene_enrichment`** — should the form offer an organism/strain **picker** (there are existing organisms/strains list endpoints) that yields `organism_id`, or a raw `tax_id` field, or both? What's the nicest UX given dev data is M. tb (`tax_id=83332`, proteome `UP000001584`)?
2. **`gff_url` / `essentiality_url`** — expose these advanced fields in the UI at all, or only the file-upload path (`essentiality_upload_ref`)? (URLs go through the backend SSRF guard.)
3. **Role gating** — hide Start/Upload for non-admins (needs a confirmed client role source) vs. show-and-let-403? (See §6.)
4. **Live progress fidelity** — just a status badge + phase text, or a progress bar from `processed/total` (note `total` can be 0 early)?
5. **Summary rendering** — `summary` is a free-form dict; pretty-print JSON, or render known keys per import type?
6. **List polling** — poll the whole list while any run is active, or only poll the detail view?
