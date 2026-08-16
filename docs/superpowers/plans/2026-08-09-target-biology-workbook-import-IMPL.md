# Target-biology workbook import — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load a curated target-biology corpus from an Excel workbook into a caller's workspace,
with a dry-run preview, without silently merging distinct records.

**Architecture:** A new `ImportType.TARGET_BIOLOGY` riding the existing `imports` context — upload
store, arq worker, `ImportRun`, progress reporter, import-hub UI. The eight existing bulk-upsert use
cases gain an explicit target workspace and an `extensions` field; a new pure parser turns a workbook
into their import records. Preview and apply are two runs over the same stored upload.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic v2, openpyxl, arq, returns.Result;
Next.js + TanStack Query + shadcn on the frontend.

**Parent spec:** `docs/superpowers/specs/2026-08-09-target-biology-workbook-import-design.md`.

## Global Constraints

- **mypy `strict = true`; ruff `line-length = 99`.** Add no new mypy errors.
- **Import-linter contracts are the architecture's teeth** (`make test` runs them): domain →
  application → infrastructure/interface. The application layer never imports SQLAlchemy.
- **Two workspace predicates**, `infrastructure/persistence/sqlalchemy/workspace_scope.py`:
  `readable_by(model, ws)` = `workspace_id IN (ws, SHARED)` for reads, `owned_by(model, ws)` =
  `== ws` for every mutation. Check each new query individually; collapsing them is a tenancy leak.
- **`SHARED_WORKSPACE_ID`** is `uuid5(NAMESPACE_DNS, "shared.protcellar")`, in
  `domain/shared/global_workspace.py`. Deliberately not the null UUID.
- **No downstream/sibling application named** in code, comments or copy. This service reads as
  standalone. In-repo context names are fine.
- **The eight record kinds** are `RecordKind` in `application/target_biology/crud.py`:
  `essentiality`, `vulnerability`, `hypomorph`, `crispri_strain`, `resistance_mutation`,
  `protein_production`, `protein_activity_assay`, `unpublished_structure`.
- **Extension field types** are exactly `string|text|number|integer|boolean|date|enum`
  (`ExtensionFieldType`, `domain/workspace_config/extension_fields/field_def.py`).
- **Baseline, never a finding and never yours to fix:** `make lint` chains with `&&` and stops at a
  pre-existing `app.py:45` E501 — run `ruff check`/`ruff format --check` on touched files instead.
  `mypy src` reports 52 errors across 12 files. `make test-api` has 2 pre-existing order-dependent
  failures (`test_organisms.py`, `test_plugin_run.py`) that pass in isolation. `make test` is clean
  at 363. `make test-fe` 297, `tsc --noEmit` clean, `make lint-fe` 8 pre-existing warnings in
  `data-grid.tsx`. `alembic/` is outside the lint path. Unstaged `duar-auth` bumps in
  `backend/pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/pnpm-lock.yaml` predate
  this branch — leave them unstaged.
- **`interface/routes/target_biology.py` carries concurrent history** from another session (commit
  `10735a1`). Add only what a task owns there; reproduce, reformat and revert nothing.

---

### Task 1: An explicit target workspace on every bulk upsert

**Files:**
- Modify: `backend/src/protcellar/application/target_biology/bulk_upsert_{essentiality,vulnerability,hypomorph,crispri_strain,resistance_mutation,protein_production,protein_activity_assay,unpublished_structure}.py`
- Modify: `backend/src/protcellar/scripts/_gene_import_cli.py`
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py`
- Test: `backend/tests/unit/application/target_biology/test_bulk_upsert_workspace.py` (new)

**Interfaces:**
- Consumes: `SHARED_WORKSPACE_ID` from `domain/shared/global_workspace.py`.
- Produces: `target_workspace_id: uuid.UUID` as a **required** field on all eight
  `BulkUpsert*Command` dataclasses. Every later task passes it explicitly.

Today all eight hardcode `SHARED_WORKSPACE_ID` in three places each: the match lookup
(`find_owned_by_gene(SHARED_WORKSPACE_ID, …)`), the `.create(workspace_id=…)` call, and — for
hypomorph — `_ensure_strain`. Read one file end to end before editing; they are the same shape.

- [ ] **Step 1: Write the failing test**

```python
import uuid
import pytest
from protcellar.application.target_biology.bulk_upsert_vulnerability import (
    BulkUpsertVulnerabilityCommand, VulnerabilityImportRecord,
)

def test_target_workspace_is_required_and_has_no_default() -> None:
    """A silent SHARED default is how the old hardcoding stayed invisible."""
    with pytest.raises(TypeError):
        BulkUpsertVulnerabilityCommand(  # type: ignore[call-arg]
            organism_id=uuid.uuid4(),
            records=(VulnerabilityImportRecord(locus_key="Rv0001"),),
        )
```

Add the same test for all eight command classes — parametrize over a list of
`(command_cls, record_cls)` pairs rather than writing eight near-identical bodies.

- [ ] **Step 2: Run it to verify it fails** — the field does not exist yet, so construction succeeds.

Run: `uv run pytest tests/unit/application/target_biology/test_bulk_upsert_workspace.py -v`

- [ ] **Step 3: Add the field and thread it through**

On each command: `target_workspace_id: uuid.UUID` with **no default**, placed before any defaulted
field (a `@dataclass(frozen=True, kw_only=True)` allows any order, but keep the required fields
together). In each `__call__`, replace every `SHARED_WORKSPACE_ID` literal with
`input.target_workspace_id`. Delete the now-unused `SHARED_WORKSPACE_ID` import where nothing else
uses it — leaving a dead import is how a future edit silently reinstates the hardcoding.

For **hypomorph**, `_ensure_strain` must create its strain in `input.target_workspace_id`. It
currently uses the caller's workspace, which is right by accident and wrong by construction.

- [ ] **Step 4: Make the gene lookup workspace-aware**

`GeneRepository.list_by_organism` carries a `ponytail:` saying `workspace_id` defaults to shared
"until those land on auth.workspace_id". Make the parameter **required** and delete the comment; the
condition it describes is now met.

The lookup must be **`readable_by`**, not `owned_by` — a tenant attaches private target-biology
records to shared reference genes, so `owned_by` would make every row fail as unmatched. Verify
which predicate the method uses today and state it in your report. Do the same for the protein-side
`find_by_accession` path used by `protein_production`, `protein_activity_assay` and
`unpublished_structure`.

- [ ] **Step 5: The CLI scripts pass SHARED explicitly**

`_gene_import_cli.py` builds the command for all seven CLI importers. Pass
`target_workspace_id=SHARED_WORKSPACE_ID` there. Behaviour is unchanged — these import public
reference data — but the choice is now stated at the call site.

Add a test pinning it, because this is the property a future refactor is most likely to break:

```python
def test_cli_imports_still_target_the_shared_workspace() -> None:
    """These load public reference data. A tenant workspace here would hide it from everyone else."""
```

- [ ] **Step 6: Verify and commit**

Run: `uv run pytest tests/unit -q && uv run lint-imports && uv run mypy src | tail -1`
Then `make test-api`.

```bash
git add backend/src backend/tests
git commit -m "refactor(target-biology): bulk upserts take an explicit target workspace

No default. A silent SHARED fallback is how the old hardcoding stayed
invisible; the CLI importers now say SHARED at the call site."
```

---

### Task 2: `extensions` on the import records

**Files:**
- Modify: the same eight `bulk_upsert_*.py`
- Test: `backend/tests/unit/application/target_biology/test_bulk_upsert_extensions.py` (new)

**Interfaces:**
- Consumes: Task 1's `target_workspace_id`.
- Produces: `extensions: dict[str, Any] | None = None` on all eight `*ImportRecord` dataclasses,
  passed through to the aggregate on both create and update.

- [ ] **Step 1: Write the failing test**

```python
async def test_extensions_reach_the_created_record() -> None:
    """The registry declares these fields; without this the bulk path can never fill them."""
    # build the command with one record carrying extensions={"vi_bin": 3}
    # assert the saved aggregate's .extensions == {"vi_bin": 3}


async def test_a_record_without_extensions_leaves_the_bag_alone_on_update() -> None:
    """An importer that does not mention extensions must not wipe values already stored —
    same rule the single-record PATCH path follows."""
```

Mirror the fixtures in the existing bulk-upsert unit tests rather than inventing new ones.

- [ ] **Step 2: Run to verify they fail** — the field does not exist.

- [ ] **Step 3: Add the field**

`extensions: dict[str, Any] | None = None` on each `*ImportRecord`. On the **create** branch pass
`extensions=rec.extensions`. On the **update** branch pass it only when it is not `None`:

```python
if rec.extensions is not None:
    match.update(..., extensions={**(match.extensions or {}), **rec.extensions})
```

The aggregates do `self.extensions = dict(fields["extensions"] or {})` — a wholesale replace — so a
bare pass-through on update would destroy stored values. Merge, do not replace. This mirrors what
`UpdateTargetBiologyRecord` already does via `ExtensionValidator.validate_and_merge`.

**`bulk_upsert_essentiality` already writes its own `extensions`** (`raw_call`, `source_run_id`) via
a local `_extensions()` helper. Merge the record's extensions over that, do not replace it, and do
not delete the helper.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/unit -q && uv run mypy src | tail -1`

```bash
git commit -m "feat(target-biology): bulk imports can write the extensions bag

Merged over what is stored, never replacing it — the aggregates replace
wholesale, so a pass-through on update would destroy imported values."
```

---

### Task 3: Fix the two upsert keys that merge distinct records

**Files:**
- Modify: `backend/src/protcellar/application/target_biology/bulk_upsert_hypomorph.py`
- Modify: `backend/src/protcellar/application/target_biology/bulk_upsert_unpublished_structure.py`
- Test: `backend/tests/unit/application/target_biology/test_bulk_upsert_keys.py` (new)

**Interfaces:** no new symbols; the `match = next(...)` predicate in each file changes.

This is a latent bug, not a migration workaround. `(protein_id, method)` asserts a protein has at
most one X-ray structure; a real corpus has one with thirteen, distinguished by ligand. It merges
records on any import, with or without a migration.

- [ ] **Step 1: Write the failing tests**

```python
async def test_two_knockdown_strains_of_one_gene_are_two_hypomorphs() -> None:
    """A hypomorph IS a knockdown strain of a gene. Keyed without the strain, a real
    corpus collapsed 195 rows into 97."""
    # two records, same gene, same (condition=None, method=None), different knockdown_strain
    # assert two records created, not one created + one updated


async def test_two_ligand_bound_structures_of_one_protein_are_two_structures() -> None:
    """Keyed on (protein, method) alone, a real corpus collapsed 53 rows into 12 —
    one protein held thirteen X-ray structures differing only by ligand."""


async def test_the_same_strain_twice_still_updates_rather_than_duplicating() -> None:
    """The key must still be a key."""
```

- [ ] **Step 2: Run to verify they fail** — currently one record, updated twice.

- [ ] **Step 3: Widen the keys**

- `hypomorph` → `(gene_id, knockdown_strain_id, condition, method)`
- `unpublished_structure` → `(protein_id, method, ligands)`

`ligands` is a list of value objects. Normalise both sides through one local helper before
comparing — sorted, case-folded, on whatever field identifies a ligand — so `[A, B]` and `[B, A]`
are one key. Put the helper next to the match, not in `_import_support.py`; it has exactly one
caller.

Update each module's docstring: the `Upsert key is (...)` line is the only statement of these keys
anywhere, and Task 4 reads them.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/unit -q && make test-api`

```bash
git commit -m "fix(target-biology): hypomorph and structure keys kept the discriminator out

(protein_id, method) asserts a protein has at most one X-ray structure. A real
corpus has one with thirteen, differing only by ligand — 53 rows became 12.
Hypomorph keyed without the strain collapsed 195 into 97."
```

---

### Task 4: The workbook parser

**Files:**
- Create: `backend/src/protcellar/infrastructure/ingestion/target_biology_workbook.py`
- Test: `backend/tests/unit/infrastructure/ingestion/test_target_biology_workbook.py`

**Interfaces:**
- Consumes: `RecordKind`; the eight `*ImportRecord` classes from Tasks 1-2.
- Produces:

```python
@dataclass(frozen=True, kw_only=True)
class RowProblem:
    sheet: str
    row: int          # 1-based, as the spreadsheet shows it
    reason: str

@dataclass(frozen=True, kw_only=True)
class SheetPlan:
    kind: RecordKind
    records: list[Any]        # the kind's *ImportRecord instances, deduplicated
    rows_read: int
    merged_identical: int
    problems: list[RowProblem]

def parse_workbook(
    data: bytes,
    *,
    match_by: str,                       # "locus_tag" | "gene_name"
    known_extension_fields: dict[str, dict[str, str]],   # kind -> {name: field_type}
) -> tuple[list[SheetPlan], list[RowProblem]]:
    """Parse a workbook into one plan per recognised sheet. The second element holds
    workbook-level problems (unrecognised sheet, missing gene column)."""
```

Pure: bytes in, dataclasses out. No database, no network, no I/O. That is what makes the collapse
numbers testable.

Mirror `infrastructure/ingestion/dejesus_xlsx.py` for the openpyxl idiom —
`load_workbook(io.BytesIO(data), read_only=True, data_only=True)`.

- [ ] **Step 1: Write the failing tests**

Build workbooks in-memory with openpyxl in a fixture helper; do not commit binary fixtures.

```python
def test_a_sheet_per_kind_is_parsed_and_an_unknown_sheet_is_reported() -> None: ...

def test_two_identical_rows_become_one_record() -> None:
    """The operator's rule: if every mapped column matches, it is the same record."""

def test_changing_any_single_column_yields_two_records() -> None:
    """The other half of that rule — and the half that protects against silent merging."""

def test_thirteen_structures_differing_only_by_ligand_stay_thirteen() -> None:
    """The measured regression: this corpus bucket collapsed to 1 under the old key."""

def test_nine_hypomorphs_of_one_gene_stay_nine() -> None: ...

def test_an_unrecognised_column_becomes_an_extension_when_declared() -> None: ...

def test_an_undeclared_column_fails_its_rows_and_names_the_column() -> None:
    """The remedy is to fix the header or declare the field, so the message must say which
    column it is."""

def test_a_row_missing_the_gene_column_is_a_problem_not_a_crash() -> None: ...

def test_a_value_that_will_not_parse_fails_only_its_own_row() -> None: ...
```

- [ ] **Step 2: Run to verify they fail** — module missing.

- [ ] **Step 3: Write the parser**

Column classification, in this order, on a case-folded and stripped header:

1. the gene column named by `match_by`
2. provenance: `source_type`, `pmid`, `reference`, `url`, `note`, `contributor`, `observed_on`
3. the kind's core field names
4. anything left → `extensions`, checked against `known_extension_fields[kind]`

Coerce each extension value to its declared type using the same rules as
`application/target_biology/extension_validator.py`. **Do not import that module** — it is
application-layer and this is infrastructure; the layer contract forbids it. If the coercion rules
want sharing, that is a follow-up, not this task: duplicating four small rules beats breaking the
contract. Note the duplication in your report.

Two traps that module already fixed and this one must not reintroduce:

- **`isinstance(True, int)` is `True`.** `integer` and `number` must both reject booleans.
- **`date` values must be stored as ISO-8601 strings**, never a Python `date`/`datetime` — the bag
  is JSONB and cannot serialise one. openpyxl returns real `datetime` objects for date-formatted
  cells, so this will happen unless you convert.

Deduplicate within a sheet on the full tuple of mapped domain values — core plus extensions,
**excluding provenance**, which is metadata about the row rather than the record's identity. Count
the merges; do not report them as problems.

**Unresolvable ligand text is this parser's job, and Task 3's review proved why.** `ligands` is a
list of `CompoundRef`, whose `compound_id` is a required UUID; the existing
`unpublished_structure_csv.py:_uuids()` silently drops any token that will not parse as one. The
corpus holds `"Apo"`, `"SO4 and PEG bound"` and raw SMILES strings — all of which become
`ligand_ids=()`, making thirteen distinct structures identical under Task 3's widened
`(protein_id, method, ligands)` key. Reproduced against the shipped code: two such records give
`['created', 'updated']`, one record stored.

So for `unpublished_structure`, a ligand cell token that is **not** a UUID goes to
`extensions["ligand_reported"]` (joined in source order when a cell holds several) rather than being
dropped. Full-row deduplication then keeps those rows distinct, which is what makes the add-mode
legacy load correct. Declare `ligand_reported` alongside `resolution_reported` in
`scripts/seed_legacy_extension_fields.py` — it exists for the same reason: a value the core column
cannot hold.

This closes the gap for add mode only. **Update mode's natural key still cannot discriminate
structures whose ligands do not resolve**, so Task 5's preview warns when update mode is selected
and a structure sheet contains unresolved ligand text.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/unit/infrastructure/ingestion -v`

```bash
git commit -m "feat(ingestion): parse a target-biology workbook, one sheet per kind

Identity is the whole row: two rows identical on every mapped domain column
are one record. On the corpus this was built for, 32,872 rows yield 32,869
records — three merges, each a genuine duplicate."
```

---

### Task 5: The import type, its adapter, and preview

**Files:**
- Modify: `backend/src/protcellar/domain/imports/enums.py`
- Modify: `backend/src/protcellar/application/imports/params.py`
- Modify: `backend/src/protcellar/infrastructure/ingestion/import_adapters.py`
- Modify: `backend/src/protcellar/interface/routes/imports.py`
- Modify: `backend/src/protcellar/application/target_biology/_import_support.py`
- Test: `backend/tests/api/test_target_biology_import.py` (new)

**Two corrections from Task 4's review, both settled before this task starts:**

- **`build_locus_index` is in `_import_support.py` and is this task's to fix.** Its `setdefault`
  means the first gene sharing a synonym silently wins, so the index cannot report that a second
  existed. The parser has no gene catalogue and could never detect this; an earlier draft of the
  Self-Review wrongly attributed it to Tasks 1 and 4. Make the index able to report ambiguity — a
  second gene claiming a key marks that key ambiguous — and fail those rows naming the candidates.
- **Five provenance columns are read and discarded** (`source_type`, `url`, `note`, `contributor`,
  `observed_on`): only `pmid` and `dataset` have a field on any `*ImportRecord`, and `source_type`
  is a command-level default rather than per-row. **The owner has decided these values are not
  needed**, so do not build the plumbing to carry them. Instead make the drop visible: the preview
  summary carries an `ignored_columns` list, per sheet, naming every header the parser recognised
  but did not use. A column that vanishes without a word is the failure mode worth closing, whether
  or not anyone wants the value.

**Interfaces:**
- Consumes: Task 4's `parse_workbook`; Tasks 1-3's commands.
- Produces: `ImportType.TARGET_BIOLOGY`; `TargetBiologyParams`; `TargetBiologyAdapter` registered in
  `IMPORT_ADAPTERS`.

**Preview and apply are two runs over one upload.** A preview run has `dry_run: true` and finishes
`SUCCEEDED` with its findings in `summary`; Apply starts a **new** run with the same `upload_ref` and
`dry_run: false`. No new `ImportStatus`, no state machine change, and the history shows both.

- [ ] **Step 1: Write the failing API test**

```python
async def test_a_preview_run_commits_nothing(client, database_url) -> None:
    """Count records before and after. A preview that writes is the one unrecoverable bug here."""

async def test_apply_produces_exactly_the_previewed_counts(client) -> None: ...

async def test_the_import_lands_in_the_callers_workspace_not_shared(client) -> None:
    """This corpus is private. A row in SHARED is readable by every tenant and editable by none."""

async def test_a_second_workspace_sees_none_of_it(client, other_workspace_client) -> None: ...

async def test_an_unmatched_locus_fails_its_row_and_the_rest_still_import(client) -> None: ...

async def test_an_ambiguous_gene_name_fails_its_row_and_names_the_candidates(client) -> None:
    """build_locus_index uses setdefault, so today the first match silently wins. Tolerable
    for a code-driven CLI, not for an operator's spreadsheet."""
```

- [ ] **Step 2: Run to verify they fail** — the import type does not exist.

- [ ] **Step 3: The enum, the params, the routing helpers**

`ImportType.TARGET_BIOLOGY = "target_biology"`. Then in `params.py`:

```python
class TargetBiologyParams(pydantic.BaseModel):
    upload_ref: uuid.UUID
    organism_id: uuid.UUID
    match_by: Literal["locus_tag", "gene_name"] = "locus_tag"
    update_existing: bool = False
    dry_run: bool = True          # preview is the default; applying is the deliberate act
```

Register it in `_PARAM_MODELS`, and extend **`target_key`** and **`upload_ref_of`** — both are
`if/elif` chains over `ImportType` with a fallthrough, so a new member silently takes the wrong
branch unless you add it. `upload_ref_of` currently returns the ref only for `PLUGIN`.

- [ ] **Step 4: The adapter**

Mirror `ProteomeAdapter` in the same file — it is the closest shape. The adapter:

1. reads the upload via `GetUpload`,
2. calls `parse_workbook`, passing the declarations for `rt`'s workspace read through
   `SQLAlchemyExtensionFieldDefRepository.list_all` (a normal repository: it must run inside
   `async with uow`, or you get `RuntimeError: UnitOfWork is not active` at runtime while mypy stays
   silent — this exact mistake has been made once already in this codebase),
3. dispatches each `SheetPlan` to its kind's bulk command with `target_workspace_id=rt.auth`'s
   workspace, `dry_run` from params, and `update_existing` selecting add-versus-match,
4. reports progress through `rt.reporter`,
5. returns the summary dict.

Summary shape, per the spec:

```python
{"kinds": {"vulnerability": {"rows": 28559, "records": 28557, "merged_identical": 2,
                             "create": 28557, "update": 0, "failed": 0}},
 "unmatched": {"count": 0, "examples": []},
 "problems": [...],          # first 50 only
 "problems_truncated": 1204, # the rest, counted
 "already_present": {"vulnerability": 0}}
```

**Cap `problems` at 50 and state the remainder in `problems_truncated`.** A silent cut reads as
"no further problems".

`already_present` counts existing records of each kind in the target workspace, so the UI can warn
that add-mode run twice doubles the data.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/unit -q && make test-api && uv run mypy src | tail -1 && make generate-api`

```bash
git commit -m "feat(imports): target-biology workbook import type, preview first

Preview and apply are two runs over one stored upload — no new ImportStatus,
and the history shows both. Apply re-reads the upload rather than the client
re-posting 28,000 rows."
```

---

### Task 6: The import screen

**Files:**
- Create: `frontend/src/features/import-hub/components/param-forms/target-biology-params.tsx`
- Create: `frontend/src/features/import-hub/components/target-biology-preview.tsx`
- Modify: `start-import-dialog.tsx`, `import-detail.tsx`
- Test: `target-biology-params.test.tsx`, `target-biology-preview.test.tsx`

Read the neighbouring param forms first; this is extension by addition, not a new surface.

**The form** takes the workbook (file upload, reusing the existing upload endpoint), the organism
(`organism-combobox.tsx` already exists), the gene-matching column, and the update toggle. Show the
expected column names per kind **read from `GET /api/v1/target-biology/schema`** — it already
publishes core and extension fields with their types, so do not restate the lists.

**The preview** renders on the run detail. Everything the summary carries has to appear — each of
these exists because something would otherwise be silent:

| Summary key | Renders as |
|---|---|
| `kinds[k]` | per-kind counts: rows, records, merged, create, update, failed |
| `unmatched` | the distinct unmatched gene values, with counts |
| `problems` | the list, **with `problems_truncated` stated when non-zero** — a silent cut reads as "no further problems" |
| `ignored_columns` | per sheet, the headers the parser recognised but did not use |
| `already_present` | a warning, in add mode only, that the target workspace already holds records of that kind |
| the update-mode ligand warning | a warning, in update mode only, naming the sheet and affected row count |

The last one is not decoration: in update mode two structure rows whose ligand text did not resolve
collide on the natural key and overwrite each other, and the operator has no other way to know.

Apply and Discard are explicit buttons.

**UI rules, hard, not preferences:**
- Visible positive and negative buttons on every confirm surface. Esc and click-outside are
  accelerators, never the only way out.
- **No layout jump** — switching between preview states must not resize the surface. Size for the
  tallest pane; scroll long lists internally.
- No `→`/`←` glyphs or arrow icons inside button or menu text labels. Chevrons for affordance only.
- No explanatory subtitles narrating what a screen is for. Terse labels; `sr-only` where a11y needs
  a description.
- Sentence case. **Plain "Save"/"Apply", not "Save changes"** — this repo's own convention, checked.
- Semantic tokens only, no hardcoded colours. Both themes.
- Empty and error states are never dead ends.

Tests: the form requires a file and an organism before it will submit; the preview renders per-kind
counts; the truncation notice appears when `problems_truncated > 0`; the `already_present` warning
appears only in add mode.

Verify: `make test-fe`, `make lint-fe`, `pnpm exec tsc --noEmit`.

---

## Self-Review

**Spec coverage.** §1 workbook contract → Task 4. §2 gene matching, including the `setdefault`
ambiguity fix → Tasks 1 and 4, pinned by an API test in 5. §3 workspace scoping → Task 1. §4
extensions on import → Tasks 2 and 4. §5 the two natural keys → Task 3. §6 preview and apply →
Task 5. §7 UI → Task 6. §8 scale, caps and progress → Task 5 Step 4. §9 testing → distributed, with
the measured collapse numbers as Task 3's and Task 4's regression tests.

**Type consistency.** `target_workspace_id` is added in Task 1 and passed in Tasks 4-5.
`extensions` is added to the import records in Task 2 and populated in Task 4. `SheetPlan` /
`RowProblem` / `parse_workbook` are defined in Task 4 and consumed in Task 5. `TargetBiologyParams`
is defined and consumed within Task 5.

**Check the code, not this plan, for:** which predicate `list_by_organism` and `find_by_accession`
use today (Task 1 Step 4); the exact `*ImportRecord` field sets (Tasks 1-2); and the current
`ligands` value-object shape (Task 3).

**Known style deviation.** Task 6 specifies frontend behaviour and tests rather than complete
component code. The exact shadcn props are better read from the neighbouring param forms than
guessed here, and the task names the files to mirror.

**One thing this plan deliberately does not do.** It does not share the type-coercion rules between
`extension_validator.py` (application) and the workbook parser (infrastructure). The layer contract
forbids the import, and four small duplicated rules are cheaper than the abstraction that would
avoid them. Task 4 records the duplication so the final review can rule on it.
