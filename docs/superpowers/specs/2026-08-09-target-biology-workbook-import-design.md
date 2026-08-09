# Bulk target-biology import from a workbook — design

**Date:** 2026-08-09
**Status:** approved, ready for planning
**Builds on:** `2026-08-09-extension-field-registry-design.md` (the `extensions` bag and its
declarations), `2026-08-08-workspace-scoping-design.md` (the two predicates, `SHARED_WORKSPACE_ID`),
and the existing `imports` context (`ImportRun`, upload storage, the arq worker, the import-hub UI).

## Problem

A curated corpus of ~33,000 target-biology records has to move into this service from a system being
retired. Four things stand between it and here.

1. **The bulk use cases have no HTTP surface.** All eight `bulk_upsert_*.py` exist, are admin-gated
   and support `dry_run`, but nothing reaches them: `/genes/bulk` and `/organisms/bulk` have routes,
   target-biology has none. The only driver is one CLI script per kind.
2. **No importer can write `extensions`.** Not one of the eight `*ImportRecord` dataclasses carries
   the field, so the field declarations the registry just gained have no bulk write path — and the
   tail of per-method values is most of what this corpus holds that core columns don't.
3. **Every bulk upsert hardcodes `SHARED_WORKSPACE_ID`.** This corpus is private. Records written to
   the shared workspace are read-only to every tenant and cannot be edited through the application
   at all.
4. **Two upsert keys silently merge distinct records.** Measured against the real corpus, keyed as
   the code defines them today:

   | kind | rows | records | lost |
   |---|---|---|---|
   | vulnerability `(gene, condition, method)` | 28,559 | 28,557 | 2 (0.0%) |
   | essentiality `(gene, condition, method)` | 4,014 | 4,014 | 0 |
   | **hypomorph `(gene, condition, method)`** | **195** | **97** | **98 (50.3%)** |
   | resistance_mutation `(gene, mutation, compound)` | 6 | 6 | 0 |
   | protein_production `(protein, host, method)` | 24 | 21 | 3 (12.5%) |
   | protein_activity_assay `(protein, activity, method)` | 21 | 19 | 2 (9.5%) |
   | **unpublished_structure `(protein, method)`** | **53** | **12** | **41 (77.4%)** |

   This is not a property of the source corpus. `(protein_id, method)` asserts that a protein has at
   most one X-ray structure; one gene in this corpus has thirteen, distinguished by ligand. The key
   is wrong for the domain, and it would merge records on any future CSV import with no legacy data
   involved.

## Decisions

| Question | Decision |
|---|---|
| Record identity, add mode | **The whole row.** Two rows identical on every mapped domain column are one record. Deduplication happens within the sheet, at preview time; the key is never stored. |
| Record identity, update mode | **Per-kind natural key**, opt-in. Requires fixing hypomorph's and unpublished-structure's keys first, or the toggle is a trap on exactly those kinds. |
| Gene matching | **Locus tag**, with gene name accepted as an alternative. An ambiguous name fails its row. |
| Unmatched gene | **Fail the row, import the rest.** The preview lists every unmatched value. |
| Foreign identifiers | **None stored.** No source-system record id reaches this schema. |
| Workspace | **The caller's**, for this path. The existing CLI importers keep writing to `SHARED`. |

Keyed on every mapped domain column, the corpus yields **32,872 rows → 32,869 records**: three
merges, each a genuine full-row duplicate. That is the operator's own rule — *if every column
matches, it is the same record* — and on this corpus it loses nothing else.

## 1. The workbook contract

**One workbook, one sheet per record kind**, the sheet name being the kind's value
(`vulnerability`, `hypomorph`, …). A single upload migrates everything and the preview reports per
kind. A workbook holding one sheet is equally valid; a sheet whose name matches no kind is reported
and skipped, never guessed at.

Row 1 is the header. Column names are matched case-insensitively with surrounding whitespace
stripped, and fall into four groups:

| Group | Columns | Behaviour |
|---|---|---|
| Gene reference | `locus_tag`, or `gene_name` | Exactly one is required per sheet. §2. |
| Core | the kind's own field names, as the descriptor publishes them | Parsed to the column's type; a value that will not parse fails its row. |
| Provenance | `source_type`, `pmid`, `reference`, `url`, `note`, `contributor`, `observed_on` | Assembled into the shared `Provenance` value object. |
| Everything else | any remaining column | Goes to `extensions`, §4. |

The descriptor at `GET /api/v1/target-biology/schema` already publishes, per kind, which names are
core and which are declared extensions, with their types. **The import screen renders the expected
column list from it** rather than restating the field lists a third time.

## 2. Matching a row to its gene

`locus_tag` is the recommended column and the one this migration will use: the source corpus's
accession numbers are unique across all 4,196 of its genes, whereas gene names are neither stable
nor guaranteed unique.

`build_locus_index` already indexes each gene's `primary_name`, its synonyms, and the tail of its
`source_record_id`, all upper-cased — so a locus tag matches, and so does a gene name that happens
to be a primary name or synonym. Supporting both columns therefore costs nothing.

**One behaviour must change.** The index is built with `setdefault`, so when two genes share a
synonym the first one silently wins. That is tolerable for a code-driven CLI importer and not
tolerable for an operator-supplied spreadsheet. The importer detects the ambiguity and **fails the
row**, naming every candidate, rather than picking one.

Protein-attached kinds (`protein_production`, `protein_activity_assay`, `unpublished_structure`)
resolve per accession through `find_by_accession`, as they do today — proteins are too numerous to
index in memory.

An unmatched gene fails its row and the run continues. The preview lists every distinct unmatched
value with a count, so a wrong-organism mistake is obvious before anything is applied.

## 3. Workspace scoping

Every one of the eight bulk commands gains an explicit target workspace. **No default** — a silent
fallback is how the current `SHARED` hardcoding became invisible.

- The seven CLI import scripts pass `SHARED_WORKSPACE_ID` explicitly. Today's behaviour for public
  reference data is unchanged, and now it is stated at the call site rather than buried.
- The workbook path passes `auth.workspace_id`.

Three consequences to carry through:

- **Genes and proteins resolve `readable_by`**, so a tenant's private records attach to shared
  reference genes. `GeneRepository.list_by_organism` carries a `ponytail:` saying exactly this —
  *"make required once those land on auth.workspace_id"* — and this work retires it.
- **The match lookup becomes workspace-scoped**: `find_owned_by_gene(target_workspace, gene.id)`, so
  a tenant import can never update a shared record.
*(Corrected during Task 1: an earlier draft of this section claimed `_ensure_strain` creates a strain
in the importing tenant's workspace and should follow the target. No such call exists on the
hypomorph path — the only `_ensure_strain` in the repository is a taxonomic-strain helper in
`import_runner.py` which already resolves against the shared catalogue. `Hypomorph.knockdown_strain_id`
exists but is dormant: nothing on the bulk path populates it. §5 is where that gets built.)*

## 4. Extensions on import

The eight `*ImportRecord` dataclasses gain `extensions: dict[str, Any] | None`, populated from the
sheet's unrecognised columns.

**Validation is a property of the import path, not of the target.** The workbook importer runs
submitted extensions through `ExtensionValidator` against the target workspace's declarations; the
CLI importers do not. That distinction is the honest one: a spreadsheet column name is operator
input and a typo there should fail loudly in the preview, naming the column, whereas
`bulk_upsert_essentiality`'s `raw_call` and `source_run_id` keys are written by code from a fixed
parser and there is nothing to typo. It also avoids inventing declarations for `SHARED`, which by
design holds none — an invariant the registry's `find_by_name` scoping already depends on.

A column that is neither core, nor provenance, nor a declared extension field fails its rows with
the column named. The remedy is either to fix the header or to declare the field in
`/admin/extension-fields`, and the preview says so.

## 5. Two natural keys are wrong and get fixed

Independent of this migration, because they will merge records on any import:

- **`hypomorph`** → `(gene_id, knockdown_strain_id, condition, method)`. A hypomorph *is* a
  knockdown strain of a gene; two strains of one gene under the same condition are two hypomorphs.
- **`unpublished_structure`** → `(protein_id, method, ligands)`, ligands normalised to a sorted,
  case-folded tuple. A protein has many structures, distinguished by what is bound.

This is what makes the §6 update toggle safe on those kinds rather than a data-loss trap.

The other two non-zero collapse rates need no key change: keyed on the full row, `protein_production`
gives 24 → 24 and `protein_activity_assay` 21 → 21. Their current keys under-discriminate only
because this corpus leaves `expression_host` and `activity_measured` empty.

## 6. Preview, then apply

The two phases are one `ImportRun`, and the stored upload is what makes that cheap: **Apply re-reads
the uploaded file rather than the client re-posting 28,000 rows.**

1. **Upload** — the workbook goes to the existing upload store; an `ImportRun` is created carrying
   `upload_ref` and the operator's parameters.
2. **Preview** — the worker parses, resolves genes, validates, deduplicates, and runs the existing
   `dry_run` path. It writes the outcome to the run's `summary` and stops. Nothing is committed.
3. **Apply** — an explicit action on the previewed run re-reads the same upload and commits.

The `summary` holds counts, never 28,000 rows of detail:

```jsonc
{ "kind": "vulnerability",
  "rows": 28559, "records": 28557, "merged_identical": 2,
  "create": 28557, "update": 0, "failed": 0,
  "unmatched_loci": {"count": 0, "examples": []},
  "problems": [ /* first 50, each with sheet, row number and reason */ ] }
```

**Add mode is the default**, per §Decisions. The preview warns when the target workspace already
holds records of that kind, with the count, because add-mode's failure case is running it twice.
Applying always requires an explicit confirmation.

**Update mode is an opt-in toggle** using §5's keys. In update mode the preview reports create and
update counts separately, so the operator sees what would be overwritten before it is.

## 7. Where it lives in the UI

A new `ImportType.TARGET_BIOLOGY` reusing the import hub end to end — `start-import-dialog`,
`param-forms`, `import-list`, `import-detail`. No new subsystem.

The parameter form takes: the workbook, the organism, the gene-matching column, and the update
toggle. The preview renders as the run's detail view: per-kind counts, the unmatched list, the
problem list, and Apply / Discard as explicit buttons.

## 8. Scale

28,559 rows in one sheet is the sizing case. openpyxl is already a dependency with a `read_only`
precedent in `dejesus_xlsx.py`; parsing happens on the arq worker, not in a request. Progress goes
through the existing reporter, so the run detail shows movement rather than a spinner.

**Cap what is stored and what is rendered.** Problems beyond the first 50 are counted, not listed,
and the run summary says so — a truncation nobody is told about reads as "no further problems".

## 9. Testing

- **The measured collapse table in §Problem is the regression test.** Fixture sheets reproducing the
  hypomorph 9-way and unpublished-structure 13-way buckets must yield 9 and 13 records, not 1 and 1.
- **Full-row deduplication** — two identical rows yield one record; changing any single column
  yields two.
- **Workspace isolation** — an import into workspace A creates nothing visible to B, updates no
  shared record, and its `_ensure_strain` strain belongs to A. Extend
  `tests/api/test_workspace_isolation.py`.
- **Ambiguous gene name fails its row** and names the candidates; an unmatched locus fails its row
  and the rest of the sheet still imports.
- **Extension validation** — an undeclared column fails its rows with the column named; a declared
  one round-trips; the CLI path still writes its own unvalidated keys.
- **Preview commits nothing** — a previewed run leaves the record count unchanged; applying the same
  run produces exactly the previewed counts.
- **The CLI importers are unchanged** — each still writes to `SHARED`, pinned by a test, because
  they now pass explicitly what they used to get by default.

## 10. Build order

1. Explicit target workspace on all eight bulk commands; CLI scripts pass `SHARED`; genes and
   proteins resolve `readable_by`; `_ensure_strain` follows the target.
2. `extensions` on the eight import records, plus `ExtensionValidator` on the workbook path only.
3. The two natural-key fixes (§5).
4. Workbook parsing: sheet-per-kind, the column contract, full-row deduplication, ambiguity and
   unmatched handling.
5. `ImportType.TARGET_BIOLOGY`, the worker job, preview into `summary`, apply from `upload_ref`.
6. The UI: parameter form and preview detail.

Steps 1-3 leave the service working and are independently reviewable. Nothing user-visible appears
until step 6.

## Deliberately out of scope

- **Storing any source-system identifier.** This is a one-time migration; keying future imports to
  a retired system's primary keys would outlive the reason for it.
- **Undoing an applied run.** Real, wanted eventually, and a separate feature — it needs the
  `source_run_id` column the `ponytail:` in `bulk_upsert_essentiality` already describes.
- **Migrating the source data itself.** This builds the road; the export is produced elsewhere.
- **Reconciling the source's tri-state `GrowthDefect` with the boolean core column**, and deciding
  which source field is the canonical `vulnerability_score`. Both are recorded as open questions in
  the extension-field ledger and both are migration decisions, not import-mechanism ones.
- **Promoting the source's essentiality calls out of vulnerability extensions.** Same reason.
- **A column-mapping UI.** The contract is name-based and the descriptor publishes the names; a
  mapping step earns its place only once a sheet arrives whose headers cannot be changed.
