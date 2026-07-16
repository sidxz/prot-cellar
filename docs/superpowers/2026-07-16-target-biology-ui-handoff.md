# Handoff: Target-Biology UI

**Date:** 2026-07-16
**Branch:** `feat/target-biology-data-model` (based on `design-system-harmonization`, unmerged)
**For:** a fresh session building the frontend for the 8 target-biology records.

## Read these first (project memory)
- `target-biology-context-slice1` — the data model (8 records, schema shape, the essentiality dual-representation gotcha below).
- `target-biology-bulk-upload` — how data gets in (CLI, per record).
- `frontend-tooling-direct-binaries` — run `vitest`/`tsc`/`biome` via `./node_modules/.bin` in `frontend/` (pnpm exec is flaky).
- `daikon-gen3-target-biology-schema` (in the daikon-gen3 project) — what each record means biologically.

## Goal
Surface the 8 target-biology facts in the UI — primarily as **sections on the gene and protein detail pages** — and (optionally) a **bulk-upload form**. Scope is the frontend, but see the critical prerequisite below.

## ⚠️ Current state — this is a FULL vertical, not just frontend
The backend has the **data model + persistence** and **CLI bulk-upload** for all 8 records, but **nothing above the domain/persistence layer**:

| Layer | Gene/Protein (reference) | Target-biology records |
|---|---|---|
| Domain aggregate + repo | ✅ | ✅ (8 records) |
| Persistence + migration | ✅ | ✅ |
| **Read query use-case** (get/list) | ✅ `GetGene`/`ListGenes` | ❌ **none** (only `BulkUpsert*` write commands) |
| **API route** | ✅ `routes/genes.py` | ❌ **none** |
| **OpenAPI → orval client** | ✅ generated | ❌ **none** |
| **Frontend feature/components** | ✅ `features/protein-catalog` | ❌ **none** |

So building the UI requires building the read side of the backend first. The write side (bulk upload) is CLI-only — a bulk-upload UI would additionally need an upload route.

## The vertical to build (mirror how genes/proteins do it)

**1. Backend read query use-cases** — `application/target_biology/`
Add e.g. `list_essentiality_by_gene.py`, `list_vulnerability_by_gene.py`, … (or one `get_gene_target_biology.py` that returns all gene-side records for a gene; and `get_protein_target_biology.py` for protein-side). Mirror `application/protein_catalog/get_gene_neighborhood.py` (a `Query` + a use-case class using the repo's `find_by_gene`/`find_by_protein`). The repos already expose `find_by_gene(workspace_id, gene_id)` (gene-side) and `find_by_protein(workspace_id, protein_id)` (protein-side); read from `GLOBAL_WORKSPACE_ID`.

**2. DI wiring** — `infrastructure/di/` (add a `register_target_biology`, mirror `di/imports.py`) + `interface/dependencies.py` (add the `*Dep` aliases).

**3. API routes** — `interface/routes/target_biology.py` (new), mounted in `interface/app.py` (mirror how `imports_router`/`target_router` are included). GET endpoints like `/api/v1/genes/{gene_id}/target-biology` and `/api/v1/proteins/{protein_id}/target-biology`, with Pydantic `*Response.from_domain(...)` models (mirror `routes/genes.py` `GeneResponse`).

**4. Regenerate the client contract:**
- Backend: `uv run python -m protcellar.scripts.export_openapi` → writes `frontend/openapi.json`.
- Frontend: `npm run generate:api` (orval) → regenerates `src/shared/lib/api/*`. New hooks appear per the route tags.

**5. Frontend** — `features/protein-catalog` (or a new `features/target-biology`)
- Add sections to `components/gene-detail.tsx` (gene-side records) and `components/protein-detail.tsx` (protein-side records).
- Wrap the generated hooks in `hooks/` (mirror `hooks/use-genes.ts`), format in `lib/` (mirror `lib/protein-annotations.ts`).
- Stack: Next.js app-dir, TanStack Query (via orval hooks), `@structflo/daikon-design-tokens` for styling — mirror existing detail-page section look.

## Where each record attaches in the UI
- **Gene detail page** (`gene-detail.tsx`): Essentiality, Vulnerability, Hypomorph, CRISPRi Strain, Resistance Mutation.
- **Protein detail page** (`protein-detail.tsx`): Protein Production, Protein Activity Assay, Unpublished Structure.

## Recommended first slice (prove the vertical, then replicate)
Do **Essentiality + Vulnerability on the gene detail page** end-to-end: 2 read queries → 1 route → OpenAPI+orval regen → 2 sections on `gene-detail.tsx`. Once that vertical works, the other 6 records are mechanical repeats (same layers, different fields). Then the protein-side on `protein-detail.tsx`.

## Gotchas
- **Essentiality dual-representation:** essentiality is CURRENTLY read from the gene's `GeneAnnotation(axis=vulnerability, key="essentiality")` (see `get_gene_neighborhood.py`), NOT the typed `essentiality_records` table. The typed table is only seeded by the one-off `backfill_essentiality` script and is not populated by live ingestion yet. So a UI reading `essentiality_records` may be empty/stale until enrichment ingestion is repointed (a deferred backend slice). Decide per-record whether to read the typed record or the annotation; for Essentiality specifically, the annotation is the live source today.
- **No data may be present:** the typed tables are populated only by the bulk-upload CLIs / backfill, which have not been run against real data. Seed some via `uv run python -m protcellar.scripts.import_essentiality --dry-run` (drop `--dry-run` to write) before expecting UI content.
- **Writes are admin-only** (`require_admin`); reads should be normal-auth. All records live under `GLOBAL_WORKSPACE_ID`.
- **Pre-existing test noise:** the full backend suite has 2 pre-existing failures (`test_proteome_import_runner`, `test_proteome_membership`) — organism `99950` test-isolation collision, unrelated to this work; confirmed identical at the base commit. Don't chase them.
- **Import Hub FE** exists on the unmerged `feat/import-hub` branch — reference it if building an upload UI, but it isn't wired for these records.

## How to run
- Backend tests: `cd backend && uv run pytest -q` (testcontainers Postgres; needs Docker).
- Backend lint: `uv run ruff check .` (note: `alembic/versions` is not lint-clean by convention) + `uv run lint-imports`.
- Frontend: in `frontend/`, use `./node_modules/.bin/{vitest,tsc,biome}` and `npm run generate:api` for orval.

## Key backend facts for response shaping
Each record has: the attach id (`gene_id`/`protein_id`), a typed core (per record — see `domain/target_biology/<record>.py`), a `Provenance` VO (`source_type`, `citations[]{pmid,doi,url,label}`, contributor, `observed_on`, note), and a free `extensions` dict. `CompoundRef` (`compound_id`, `name`) appears on Resistance Mutation (`compound`) and Unpublished Structure (`ligands`).
