# Import Hub — Frontend Design

**Date:** 2026-06-22
**Status:** Design — decisions locked via brainstorming
**Depends on:** backend on `feat/import-hub` (`POST/GET /api/v1/imports`, `GET /api/v1/imports/{id}`, `POST /api/v1/imports/uploads`)
**Input context:** `docs/superpowers/specs/2026-06-22-import-hub-frontend-handoff.md` (authoritative API contract, verified against code)
**Next step:** `writing-plans` → implementation plan, then TDD per task

---

## 1. Goal & scope

Build an admin **Import Hub** at `/admin/imports` so imports can be run from the UI instead of Swagger/curl. Four capabilities:

1. **List** import runs (cursor-paginated) — status, type, target, timestamps.
2. **Start an import** — one dialog whose param sub-form swaps by import type (`go_ontology` / `proteome` / `gene_enrichment`).
3. **Upload** an essentiality file (`.xlsx`/`.tsv`) → `upload_ref`, consumed inline by a `gene_enrichment` import.
4. **Detail view** with **live status polling** (`queued → running → succeeded/failed`), `phase`, `processed/total`, final `summary`, and `error`.

**Out of scope:** no cancel action (no backend endpoint); no retry; no client-side role fetch (see §6).

The structural approach is not a fork — it mirrors `src/features/workspace-config/` (simplest admin list+detail+dialog), which is the established convention. This design layers the import-specific decisions onto that template.

---

## 2. Locked decisions

| # | Question | Decision |
|---|---|---|
| 1 | Organism selection for `gene_enrichment` | **Searchable picker + manual `tax_id` fallback.** Combobox backed by `useOrganisms({ name })` (debounced) renders `scientific_name — tax_id` and sets `params.organism_id` (UUID). A "can't find it? enter a tax_id" disclosure sets `params.tax_id`. Exactly one is submitted (zod refine), mirroring backend validation. |
| 2 | `gff_url` / `essentiality_url` | **Collapsible "Advanced" disclosure.** Essentiality file upload is the primary path; the two URL fields live under a collapsed section. |
| 3 | Role gating | **Show page + actions to any authenticated user; let admin-only Start/Upload surface a 403 via the global error toast.** No client-side role fetch — `useAuthz().user` has no role; obtaining it needs an async `client.resolve()` call (net-new, YAGNI). Matches the existing app convention (no FE role gating exists anywhere today). |
| 4 | Progress fidelity | **Determinate bar when `total > 0`; otherwise an indeterminate spinner + `phase` text.** (`total` is often 0 early.) |
| 5 | Summary rendering | **Generic key/value render** of the free-form `summary` dict — no per-type schemas. Nested values JSON-stringified. |
| 6 | List polling | **Detail view polls; list does not auto-poll.** List has a manual refresh button + refetch-on-mount. |
| — | Upload flow (sub-decision) | **Inline** the essentiality upload inside the `gene_enrichment` sub-form (a file field that POSTs `FormData`, stashes the returned `upload_ref`, shows a "uploaded ✓" chip) rather than a separate top-level modal. |

---

## 3. Architecture & file layout

Mirror `workspace-config/`. New feature folder:

```
src/features/import-hub/
├── components/
│   ├── import-list.tsx                  # cursor-paginated DataGrid; row → detail
│   ├── import-columns.tsx               # ColDef[] + status-badge cell + type/target/time renderers
│   ├── start-import-dialog.tsx          # type <Select> → swaps param sub-form; submits StartImportBody
│   ├── param-fields/                    # one sub-form per import type (keeps start dialog small)
│   │   ├── go-ontology-fields.tsx       # { force }
│   │   ├── proteome-fields.tsx          # { proteome_id (req), force, dry_run, limit }
│   │   └── gene-enrichment-fields.tsx   # organism picker + manual tax_id + inline upload + Advanced(url)
│   ├── organism-combobox.tsx            # searchable single-select over useOrganisms({name})
│   └── import-detail.tsx                # polling status header, phase, progress, summary, error
├── hooks/
│   └── use-imports.ts                   # wrappers over generated hooks (list/get/start/upload) + polling
├── types/
│   └── index.ts                         # re-export generated models + IMPORT_TYPE_LABELS / STATUS_VARIANTS
└── index.ts                             # barrel

src/app/(dashboard)/admin/imports/
├── page.tsx                             # renders <ImportList/>
└── [id]/page.tsx                        # renders <ImportDetail id={...}/>
```

Each `*.tsx` gets a colocated `*.test.tsx`; `use-imports.ts` gets `use-imports.test.ts`.

**Why `param-fields/` is split out:** three type-specific sub-forms in one file would make `start-import-dialog.tsx` large and tangle three validation schemas. Each sub-form owns its fields + zod schema and exposes a uniform `{ register/control, schema }` contract to the parent, so the dialog only orchestrates type selection + submit.

**Prerequisite (REQUIRED, first plan task):** `make generate-api` — `openapi.json` currently lacks `/api/v1/imports` (verified: 0 matches) and `src/shared/lib/api/imports/` does not exist. This regenerates the client and emits the react-query hooks + models. Confirm the actual generated hook names before wiring (expected `useStartImportApiV1ImportsPost`, `useListImportRunsApiV1ImportsGet`, `useGetImportRunApiV1ImportsImportRunIdGet`, `useUploadEssentialityFileApiV1ImportsUploadsPost`).

---

## 4. Components

**`import-columns.tsx`** — ag-grid `ColDef[]`: type (via `IMPORT_TYPE_LABELS`), `target_key`, status (badge cell using `STATUS_VARIANTS`), `created_at`/`finished_at` (formatted). Row click → `/admin/imports/{id}`. Mirror `organization-columns.tsx`.

**`import-list.tsx`** — `DataGrid` + cursor-stack pagination (prev/next) exactly as `organization-list.tsx`. Manual "Refresh" button (no auto-poll). "New import" button opens `start-import-dialog`.

**`organism-combobox.tsx`** — single-select searchable combobox; debounced `name` filter → `useOrganisms({ name })`; option label `scientific_name — {ncbi_tax_id ?? "—"}`; value = organism `id`. Reusable, isolated from the dialog.

**`param-fields/*`** — each renders its type's inputs and owns a zod schema:
- `go-ontology-fields`: `force` (checkbox).
- `proteome-fields`: `proteome_id` (free-text, **required**), `force`, `dry_run`, `limit` (nullable int).
- `gene-enrichment-fields`: `<OrganismCombobox/>` **or** manual `tax_id` (numeric); inline essentiality file field (uploads → `upload_ref` chip); Advanced disclosure with `gff_url` + `essentiality_url`. Cross-field zod refine: exactly one of `organism_id`/`tax_id` present.

**`start-import-dialog.tsx`** — `<Select>` for `import_type`; renders the matching sub-form; on submit composes `{ import_type, params }` and calls the start mutation; closes + toasts on success. react-hook-form + `@hookform/resolvers/zod`, radix `Dialog` — mirror `organization-form-dialog.tsx`.

**`import-detail.tsx`** — header with status badge + `phase`; progress (bar if `total>0`, else spinner); `processed/total` text; `summary` key/value block (success); `error` block (failure); timestamps. Uses the polling hook.

---

## 5. Data flow

**`use-imports.ts`** wraps the generated hooks (pattern: `use-organizations.ts`):
- `useImportList(cursor, limit)` → `useListImportRunsApiV1ImportsGet`.
- `useImportRun(id)` → `useGetImportRunApiV1ImportsImportRunIdGet` with status-keyed polling:
  `refetchInterval: (q) => ["queued","running"].includes(q.state.data?.status) ? 2000 : false`.
- `useStartImport()` → start mutation; on success invalidate the list query + `showSuccess`.
- `useUploadEssentiality()` → posts `FormData` (single field **`file`**) via the upload mutation; returns `upload_ref`.

**Upload mechanics:** `custom-instance.ts` already detects `data instanceof FormData`, drops `Content-Type`, and still injects `getAuthHeaders()` — so the generated upload hook works as-is; the sub-form just builds `FormData` with field name `file`.

**Errors:** rely on the global `MutationCache.onError → showError` in `query-provider.tsx` (unwraps `ApiError.detail`). **No per-mutation `onError`.** A non-admin Start/Upload → 403 → global toast. A bad upload → `422 {detail}` → global toast.

---

## 6. Error handling & gotchas (carried from handoff, verified)

- Upload multipart field is exactly **`file`**; response key is **`upload_ref`** (not `upload_id`). No `file_type` field.
- Status enum is exactly `queued|running|succeeded|failed|cancelled` — **no `failed_validation`**. `STATUS_VARIANTS` maps these five only (`cancelled` shown though no cancel UI exists, since old/seeded runs may carry it).
- No cancel / retry actions.
- No client role gating — server enforces; FE shows actions and lets 403 surface (decision #3).
- Worker must run for jobs to leave `queued`; that's a backend/ops concern, FE only polls. Worker logs to `.logs/worker.log` (not `make logs`).

---

## 7. Testing strategy (vitest, colocated)

Mirror existing `*.test.tsx` patterns. Per component:
- **`import-columns`**: status cell renders correct badge variant per status; type/time formatting.
- **`import-list`**: renders rows from a mocked list; pagination next/prev advances cursor; refresh refetches.
- **`organism-combobox`**: typing filters; selecting sets value.
- **`gene-enrichment-fields`**: organism-XOR-tax_id refine (error when both/neither); upload sets `upload_ref` chip; Advanced toggles URL fields.
- **`proteome-fields`**: `proteome_id` required validation.
- **`start-import-dialog`**: switching type swaps sub-form; submit composes correct `{import_type, params}`.
- **`import-detail`**: polling stops on terminal status; renders summary on success, error on failure; bar vs spinner by `total`.
- **`use-imports`**: start invalidates list; `refetchInterval` predicate returns 2000 for active, false for terminal.

Gate: `./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/biome check`, `./node_modules/.bin/vitest run` all green (run via direct binaries — `pnpm exec` is flaky here).

---

## 8. Build sequence (high-level — detailed steps in the plan)

1. `make generate-api`; confirm `imports/` hooks + models. **(blocking)**
2. `types/index.ts` — re-exports + `IMPORT_TYPE_LABELS` / `STATUS_VARIANTS`.
3. `use-imports.ts` (+ test) — list/get(poll)/start/upload wrappers.
4. `import-columns.tsx` + `import-list.tsx` (+ tests) — paginated grid.
5. `organism-combobox.tsx` (+ test).
6. `param-fields/*` (+ tests) — three sub-forms.
7. `start-import-dialog.tsx` (+ test) — type switch + submit.
8. `import-detail.tsx` (+ test) — polling header, progress, summary, error.
9. `app/(dashboard)/admin/imports/page.tsx` + `[id]/page.tsx`; nav entry `{ title: "Imports", href: "/admin/imports", icon: Upload }` in the **Administration** group of `navigation.ts`.
10. Full gate green (tsc + biome + vitest).

---

## 9. Open implementation note (not a blocker)

Dev target **H37Rv (tax_id 83332) is a strain**, loaded in `/api/v1/strains`, not necessarily in `/api/v1/organisms`. The organism picker sources `/api/v1/organisms`; if H37Rv isn't there, it's reached via the **manual `tax_id` field** (exactly why the fallback exists). If product later wants strain-level targets pickable, extend `organism-combobox` to also source `/api/v1/strains`. v1 assumption: organisms picker + manual tax_id is sufficient. Verify during implementation of `gene-enrichment-fields`.
