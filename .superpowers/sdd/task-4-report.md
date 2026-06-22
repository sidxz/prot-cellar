# Task 4 Report — Application layer: param schemas, `StartImport`, list/get queries, `JobEnqueuer`

## What Was Built

Five new files in `backend/src/protcellar/application/imports/`:

| File | Contents |
|------|----------|
| `params.py` | `ProteomeParams`, `GeneEnrichmentParams`, `GoOntologyParams` (Pydantic); `validate_params`, `target_key`, `needs_upload`, `upload_ref_of` helpers |
| `job_enqueuer.py` | `JobEnqueuer(Protocol)` with `async enqueue_import(import_run_id: UUID) -> None` |
| `start_import.py` | `StartImportCommand` dataclass + `StartImport` use case |
| `list_import_runs.py` | `ListImportRunsQuery` + `ListImportRuns` query (ts-cursor pagination) |
| `get_import_run.py` | `GetImportRunQuery` + `GetImportRun` query (NotFoundError on miss) |

Two new test files in `backend/tests/unit/application/imports/`:

| File | Tests |
|------|-------|
| `test_start_import.py` | 5 async tests covering: queued+enqueued, duplicate guard, requested_by, gene_enrichment, go_ontology |
| `test_params.py` | 18 tests covering valid/invalid ProteomeParams, GeneEnrichmentParams, GoOntologyParams; validate_params domain error wrapping; target_key for all 3 import types |

## TDD Red → Green

**RED:** `uv run --directory backend pytest tests/unit/application/imports -q` → 2 collection errors (missing modules).

**GREEN:** After implementing all 5 files → `23 passed in 0.20s`.

## Files Changed

Created:
- `backend/src/protcellar/application/imports/params.py`
- `backend/src/protcellar/application/imports/job_enqueuer.py`
- `backend/src/protcellar/application/imports/start_import.py`
- `backend/src/protcellar/application/imports/list_import_runs.py`
- `backend/src/protcellar/application/imports/get_import_run.py`
- `backend/tests/unit/application/imports/__init__.py`
- `backend/tests/unit/application/imports/test_start_import.py`
- `backend/tests/unit/application/imports/test_params.py`

## Self-Review

1. **`find_active` short-circuits BEFORE enqueue**: Yes — the active-run guard fires before `ImportRun.create` is called; if it returns a run, `Failure(ConflictError)` is returned immediately with no save or enqueue.

2. **`requested_by` from `auth.user_id`**: Yes — `requested_by: uuid.UUID = auth.user_id` is passed to `ImportRun.create`. Tested by `test_start_import_sets_requested_by_from_auth`.

3. **`validate_params` re-raises as domain `ValidationError`**: Yes — `pydantic.ValidationError` is caught and re-raised as `protcellar.domain.shared.errors.ValidationError`. Tested by `test_validate_params_proteome_missing_id_raises_domain_error` and `test_validate_params_proteome_wrong_type_raises_domain_error`.

4. **No infrastructure imports**: Confirmed by `lint-imports` — "Clean Architecture layers KEPT / Domain purity KEPT / Bounded context independence KEPT". `application.imports.*` imports only `domain.imports`, `application.shared`, `application.auth`, stdlib, `pydantic`, `returns`.

5. **Full unit suite**: `163 passed` — no regressions.

## Concerns

None. The `list_import_runs.py` passes `cursor=parsed_cursor` as a `tuple[datetime, UUID] | None` to `run_repo.list` — this matches the `ImportRunRepository` protocol signature `cursor: tuple | None`. The infrastructure implementation (Task 6) will need to unpack this tuple for the keyset WHERE clause.

## Fix wave (review)

Applied 2026-06-22 on branch `feat/import-hub`.

### Fix 1 — require organism identifier for gene enrichment
**File:** `backend/src/protcellar/application/imports/params.py` lines 28–34

Added `@pydantic.model_validator(mode="after")` to `GeneEnrichmentParams` that raises `ValueError("gene enrichment requires organism_id or tax_id")` when both `organism_id` and `tax_id` are `None`. The existing `pydantic.ValidationError → DomainValidationError` wrapping in `validate_params` ensures callers see the domain error. `target_key` logic unchanged.

### Fix 2 — invalid-input tests per type
**File:** `backend/tests/unit/application/imports/test_params.py`

Added three tests:
- `test_validate_params_gene_enrichment_no_identifier_raises_domain_error` — `validate_params(GENE_ENRICHMENT, {})` raises domain `ValidationError`
- `test_validate_params_gene_enrichment_bad_tax_id_type_raises_domain_error` — `{"tax_id": "not-an-int"}` raises domain `ValidationError`
- `test_validate_params_go_ontology_bad_force_type_raises_domain_error` — `{"force": "not-a-bool"}` raises domain `ValidationError` (pydantic **rejects** the string directly, no fallback value needed)

### Fix 3 — assert no save on duplicate guard
**File:** `backend/tests/unit/application/imports/test_start_import.py` line 97

Added `assert repo.saved == []` after the existing `assert enq.enqueued == []` in `test_start_import_rejects_duplicate_active_run`.

### Fix 4 — tighten misleading assertion
**File:** `backend/tests/unit/application/imports/test_params.py`

`test_proteome_params_missing_proteome_id_raises`: changed from `pytest.raises(Exception)` with `ProteomeParams()` to `pytest.raises(ValidationError)` routed through `validate_params(ImportType.PROTEOME, {})`. This tests the domain error contract, not the raw pydantic model.

### Side-fix — upload_ref test required identifier
**File:** `backend/tests/unit/application/imports/test_params.py`

`test_gene_enrichment_params_with_upload_ref` updated to supply `organism_id=oid` alongside `essentiality_upload_ref=ref` since the new validator now requires an identifier.

### Side-fix — all_none test converted
**File:** `backend/tests/unit/application/imports/test_params.py`

`test_gene_enrichment_params_all_none` renamed to `test_gene_enrichment_params_all_none_raises` and converted to assert domain `ValidationError` via `validate_params`.

### Commands and results

```
uv run --directory backend lint-imports
→ Contracts: 3 kept, 0 broken.

uv run --directory backend pytest tests/unit/application/imports -q
→ 26 passed in 0.18s
```
