# Handoff: final review of the target-biology write-surface hardening

**Date:** 2026-08-07
**Branch:** `feat/target-biology-hardening` — 8 commits, branched from `main` @ `b5d4e0a`, **not pushed**
**For:** a fresh session running the **final whole-branch review**, then deciding how to land it.

## Your job

Everything is built, task-reviewed, and live-QA'd. One thing is owed: the **final whole-branch
review** — the only pass that looks at all 8 commits together rather than task by task. After it,
`superpowers:finishing-a-development-branch` decides how this lands.

Do **not** re-run the per-task reviews. They happened, they found real defects, and the outcomes are
in the ledger.

## Read first, in this order

1. **The ledger** — `.superpowers/sdd/2026-08-07-target-biology-api-hardening-IMPL/progress.md`.
   Every task, every finding, both fix rounds, the adjudication, the live QA, and 12 deferred minors.
   This is the record; trust it and `git log` over anything else.
2. **The plan** — `docs/superpowers/plans/2026-08-07-target-biology-api-hardening-IMPL.md`
   (5 tasks, bite-sized). Its parent spec is
   `docs/superpowers/plans/2026-08-07-target-biology-api-hardening.md` (the why).
3. **Task reports** — `.superpowers/sdd/…/task-{1..5}-report.md`, if you need a specific decision's
   reasoning. Task 4's and Task 5's have fix-round sections appended.

To build the review package:

```bash
.../subagent-driven-development/scripts/review-package \
  docs/superpowers/plans/2026-08-07-target-biology-api-hardening-IMPL.md b5d4e0a HEAD
```

Note that the range includes ~78 orval-**generated** files under `frontend/src/shared/lib/api/`
plus `frontend/openapi.json`. Exclude them — they are `make generate-api` output, and they swept in
catch-up for Tasks 1-3 because the client had never been regenerated. The hand-written surface is
~14 files.

## What the branch does

| Commit | Change |
|---|---|
| `50d9edf` | PATCH becomes partial — an edit to one field stops clobbering provenance and re-stamping `generation_method` |
| `5863ad2` | Optimistic locking reaches the wire: `version` on responses, accepted on PATCH, 409 on mismatch. **Opt-in**, so importers are unaffected |
| `2623a38` | `compound`, `ligands`, `knockdown_strain_id` become writable — they were stored and returned but importer-only |
| `d719e9c` | `GET /api/v1/target-biology/schema` — a self-describing write contract derived from the `*WriteBody` models |
| `02cefaa` | Fix round: `SuggestedValuesReader` moved to ports-and-adapters; drift test; TTL cache; `concurrency` in the descriptor |
| `81c54b4` | The record form stops destroying provenance — full editor rendered from the descriptor |
| `eecada0` | Fix round: create stopped 422ing on all 8 kinds; `observed_on` can be cleared |
| `117f290` | All 33 `json` columns → `jsonb` (schema-wide, not just target-biology) |

Two of these fixed **live data bugs** that existed before any of this work:

- The record form round-tripped provenance through a 3-field draft, so every edit dropped
  DOI/URL-only citations, citations beyond the first, the contributor and the observed date.
- Full-replacement PATCH re-attributed AI-extracted records to a human on any edit.

## Already verified — don't redo

**Live QA passed**, run in a browser against the dev stack on gene `Rv1297`/`rho`, every result
checked in Postgres rather than in the UI:

1. Editing an unrelated field on an `imported` record left `generation_method` as `imported`.
2. The dialog round-tripped a **DOI-only** citation, a contributor and an observed date — all three
   used to be destroyed.
3. With two citations on a record, editing a field left both intact.
4. Creating a record works (this was the Critical bug in `81c54b4`, fixed in `eecada0`).
5. Both themes render, dialog included.

Test data was cleaned up afterwards and the modified record restored byte-for-byte.

## Baseline — these failures are NOT this branch's

Verified against a worktree at the merge base. Do not chase them, and do not let a reviewer report
them as findings:

- `make lint` chains with `&&` and **stops** at 3 pre-existing `E501` errors (`interface/app.py`,
  `tests/api/test_genes.py`, `tests/unit/.../test_bulk_upsert_genes.py`), so it never reaches its
  later steps.
- `ruff format --check` has ~13 pre-existing candidates.
- `mypy src` reports **53 errors across 12 files**, all the same lagom `Container.define()`
  argument-type pattern. This branch ends at exactly 53 — it adds none.
- `make test-api` has **2 pre-existing order-dependent pollution failures** (`test_organisms.py`,
  `test_plugin_run.py`) that pass in isolation and fail in a full-suite run on a shared
  `ncbi_tax_id`.
- `make test` (unit + import-linter) passes **clean**: 330 tests, 3 contracts kept.
- `alembic/` is **not** in the lint path. All 34 migrations use the `typing.Sequence`/`Union`
  template style; matching them is correct, not a finding.

## 12 deferred minors to triage

The final review should decide which of these must be fixed before merge. All are in the ledger
with full context; summarised here:

**Task 4 — descriptor (7):** 13 of 33 `_ANNOTATIONS` entries are dead weight (deleting them yields a
byte-identical descriptor) · `note → "text"` is a hardcoded field-name branch in `_scalar_type`
rather than an annotation · `attaches_to`/`read_only` restate the route split and the ORM with no
guard · the deferred import in the route handler is correct but records a misplaced boundary (the
`*WriteBody` classes are shared contracts living inside one of two consumers; the fix is
`interface/schemas/target_biology.py`) · `_MODELS` in `suggested_values_reader.py` restates each
repository's `model_class` · `for_all_kinds()` takes no workspace argument, masked today by the
single `GLOBAL_WORKSPACE_ID` sentinel · `compound`/`ligands` post `{compound_id, name}` while
`knockdown_strain_id` posts a bare UUID, yet both render `type: "reference"`.

**Task 5 — frontend (2):** blank citation rows are not filtered client-side (harmless — the backend's
`ProvenanceBody.to_domain()` drops all-null citations on both POST and PATCH, verified — but it
costs a round trip and shows a misleading "updated" toast) · `PmidCell` still shows only the first
citation's PMID, so a curator scanning the table can't tell a row holds three.

**Task 3 (1):** `ligands` and `knockdown_strain_id` have create-path tests but no dedicated PATCH
test; `compound` has both.

**Task 1 (2):** a `ruff format` reflow of one pre-existing call · a Task 1 report claim about
"fixing a bug in the brief" that the reviewer disproved at byte level. Both cosmetic; the second
matters only as a caution that task reports are not always accurate.

## Two things the review should specifically look at

1. **The deferred import** in `interface/routes/target_biology.py` — it resolves a genuine circular
   import (reproduced independently), but it is the symptom of the `*WriteBody` classes living in
   the wrong module. Worth a judgement on whether it merges as-is.
2. **`117f290` is schema-wide**, not target-biology-scoped: 33 columns across 6 contexts, including
   a rewrite of four tables totalling ~2.4M rows. It needs a maintenance window and ~2× disk on any
   deployment with real data — the migration docstring says so. Confirm that is acceptable, or split
   the big four into their own migration.

## Context you may not otherwise have

- **This service must stay usable standalone.** It has no knowledge of, and no dependency on, any
  consumer. Loose mentions of sibling apps in domain docstrings predate this work and the owner has
  confirmed they are fine — sibling apps, not a coupling. Do not add new ones in code you write.
- **A downstream consumer is waiting on `GET /target-biology/schema`.** Its design is written and
  approved but not built, and it is explicitly gated on this branch landing. That is why the
  descriptor exists and why `concurrency: {field: "version"}` was added to it — so a client never
  has to hardcode a field list. Keep that property.
- Dev stack: `make dev` → backend `:8001`, frontend `:3001`, Postgres `127.0.0.1:5433`
  (`protcellar`/`protcellar`/`protcellar`). Sign-in is Google OAuth via Sentinel.
- The Docker VM ran out of disk during `117f290`; build cache and dangling images were pruned (no
  volumes). If a migration fails on `DiskFullError`, alembic's transactional DDL rolls it back
  cleanly — verify with `SELECT version_num FROM alembic_version` before retrying.
