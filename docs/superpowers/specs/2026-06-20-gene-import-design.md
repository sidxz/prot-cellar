# prot-cellar Gene Import Design

**Date:** 2026-06-20
**Status:** Approved (scope confirmed: proteins + genes; targets out of scope)

## Goal

Extend the UniProt proteome importer so a single run creates **genes** alongside
proteins and links each protein to its gene. Concretely, after this work,
`python -m protcellar.scripts.import_proteome UP000001584` loads the full
*Mycobacterium tuberculosis* H37Rv (NCBI taxon **83332**) catalog — Organism,
Proteome, ~4,000 Proteins, **and their Genes** — with `protein.gene_id`
populated.

## Background / Current State

- **Proteins**: fully imported today. `ProteomeImportRunner` streams a proteome's
  UniProtKB entries, maps each via `map_uniprot_entry` → `ProteinImportRecord`,
  and bulk-upserts through `BulkUpsertProteins` (idempotent on
  `(source, source_record_id)` + checksum). Organism + Proteome are auto-created;
  membership is reconciled.
- **Genes**: the `Gene` aggregate (GLOBAL reference data, `workspace_id =
  GLOBAL_WORKSPACE_ID`), its SQLAlchemy model, repository (incl.
  `find_by_source_record_id`), and CRUD use cases all exist — but **nothing
  creates genes**. `uniprot_mapper.py` ignores the entry `genes` field and
  `protein.gene_id` is never set. There is no `BulkUpsertGenes`.
- **Targets**: out of scope for this work (explicitly deferred by the user).

The `Gene` aggregate already carries import-provenance fields (`source`,
`source_release`, `source_record_id`, `source_record_checksum`, `imported_at`),
so it was designed for exactly this import. The fix is additive.

## Architecture

Mirror the proven protein-import pipeline. Four units, each with one purpose:

### 1. `application/protein_catalog/bulk_upsert_genes.py` (new)

A near-exact analogue of `bulk_upsert_proteins.py`:

- `GeneImportRecord` (frozen dataclass): `primary_name`, `organism_id`,
  `synonyms: tuple[str, ...]`, `ncbi_gene_id`, `ensembl_gene_id`,
  `cross_references`, `source`, `source_release`, `source_record_id`,
  `source_record_checksum`.
- `BulkUpsertGenesCommand(records: tuple[GeneImportRecord, ...], dry_run: bool)`.
- `BulkUpsertGenes` use case: `require_admin(auth)`; for each record,
  `find_by_source_record_id(source, source_record_id)`:
  - none → `Gene.create(...)`, set provenance, save → `created`;
  - exists, checksum equal → `skipped`;
  - exists, checksum differs → `gene.update(...)`, bump checksum/release/
    imported_at, save → `updated`.
  Returns `list[ItemResult]` (reuse the existing `ItemResult{index,status,id,error}`
  shape; import it from `bulk_upsert_proteins` or lift to a shared module — see
  Decisions). One UoW per command; commit then dispatch; no commit on dry-run.

`Gene` is GLOBAL reference data, so (like proteins) the upsert runs under
`require_admin`. The import script's `_ServiceAuth` already satisfies this.

### 2. `infrastructure/ingestion/uniprot_mapper.py` (extend — stays pure)

Add two pure functions; do not change `map_uniprot_entry`'s signature.

- `map_uniprot_genes(entry, *, organism_id, tax_id, source, source_release) ->
  list[GeneImportRecord]` — one record per element of the entry `genes` array
  that yields a usable name.
- `gene_key_for_entry(entry, *, tax_id) -> str | None` — the
  `source_record_id` of the entry's **primary** gene (first `genes` element),
  used by the runner to resolve `gene_id` for the protein. Must produce the same
  key `map_uniprot_genes` assigns to that gene.

Shared private helpers:

- `_gene_primary_name(gene) -> str | None`: `geneName.value` if present, else
  first `orderedLocusNames[].value`, else first `orfNames[].value`, else `None`.
- `_gene_key_basis(gene) -> str | None`: first `orderedLocusNames[].value` if
  present (stable — locus tags never change), else `geneName.value`, else first
  `orfNames[].value`, else `None`. `source_record_id = f"{tax_id}:{basis}"`.
- `_gene_synonyms(gene, primary_name) -> tuple[str, ...]`: union of
  `synonyms[]`, `orfNames[]`, `orderedLocusNames[]`, and `geneName` minus
  `primary_name`; order-preserving dedupe.
- `_gene_checksum(record) -> str`: stable content hash
  (`hashlib.sha1` of `primary_name | sorted(synonyms) | ncbi_gene_id |
  ensembl_gene_id`), so unchanged genes are `skipped` on re-import.
- `_ncbi_gene_id(entry) -> str | None`: the `id` of the entry's `GeneID`
  cross-reference when exactly one is present, else `None` (defensive — avoids
  mis-attribution).

**Name vs. key split is intentional:** `primary_name` prefers the human-friendly
`geneName`; the identity key prefers the immutable `orderedLocusName`. A later
UniProt release that adds a gene name to a locus-only entry updates the display
name without creating a duplicate gene.

### 3. `infrastructure/ingestion/import_runner.py` (modify)

- Constructor gains an **optional** collaborator:
  `gene_bulk: BulkUpsertGenes | None = None`. When `None`, behavior is identical
  to today (no gene work) — this keeps every existing runner test green.
- `run()`: accumulate **raw entries** into `chunk` (instead of mapping inline),
  so the chunk processor has the entry available for gene extraction. `seen`
  (accessions for membership reconcile) and the version gate are unchanged.
- `_load_chunk(entries, ...)`:
  1. If `gene_bulk`: for each entry collect `map_uniprot_genes(...)`; dedupe by
     `source_record_id` across the chunk; `BulkUpsertGenes` → correlate
     `ItemResult.index` back to records to build `{source_record_id: gene_id}`.
  2. Map each entry → `ProteinImportRecord`; if `gene_bulk`, compute
     `gene_key_for_entry(entry)` and, when found in the map,
     `dataclasses.replace(record, gene_id=...)`.
  3. `BulkUpsertProteins` (unchanged) + membership link (unchanged).
  4. Update summary protein + gene counters.
- `ImportSummary` gains `genes_created`, `genes_updated`, `genes_skipped`.

**Transaction strategy:** genes commit (their own UoW) before proteins commit in
the same chunk, so `protein.gene_id` FK is always satisfied. This preserves the
existing chunk-granularity resumable/idempotent design.

### 4. `scripts/import_proteome.py` (modify)

Construct `SQLAlchemyGeneRepository(uow)` + `BulkUpsertGenes(uow, gene_repo,
_NoopDispatcher())` and pass `gene_bulk=...` into `ProteomeImportRunner`. Extend
the printed summary with `genes_created`/`genes_updated`. No CLI flag change
(gene import is always on for proteome import).

## Data Flow

```
UniProt proteome stream
  └─ chunk of raw entries
       ├─ map_uniprot_genes  → GeneImportRecord[]  ─┐
       │                                            ├─ BulkUpsertGenes (commit)
       │                              {srid → gene_id}┘        │
       ├─ map_uniprot_entry  → ProteinImportRecord            │
       │      └─ replace(gene_id = map[gene_key_for_entry]) ◄──┘
       └─ BulkUpsertProteins (commit) → membership link (commit)
```

## Idempotency

- Genes keyed on `(source="uniprot", source_record_id="{tax_id}:{locus|name}")`;
  content checksum gates skip-vs-update. Re-running the import is safe.
- The proteome version gate still short-circuits an unchanged proteome. To
  backfill genes into an already-imported proteome, run with `--force`.

## Error Handling

- A `DomainError` on a single gene/protein record is captured as a `failed`
  `ItemResult` (existing behavior) — one bad record never aborts the chunk.
- An entry with no `genes` (or no usable name) yields no gene; its protein is
  imported with `gene_id = None` (valid — the column is nullable).

## Testing

1. **`tests/unit/infrastructure/test_uniprot_mapper.py`** (extend): gene
   extraction from the existing `katG`/`Rv1908c` fixture (primary_name `katG`,
   key `83332:Rv1908c`, `Rv1908c` in synonyms); locus-only entry (primary_name =
   Rv number); no-`genes` entry → `[]` and `gene_key_for_entry` → `None`;
   synonyms/orfNames composition; `GeneID` xref → `ncbi_gene_id`.
2. **`tests/api/test_gene_bulk_import.py`** (new, mirrors
   `test_protein_bulk_import.py`): `BulkUpsertGenes` create / skip-unchanged /
   update-on-checksum-change against the real test DB.
3. **`tests/unit/infrastructure/test_proteome_import_runner.py`** (extend): a new
   test wiring `gene_bulk` with gene-bearing fixtures asserting genes are created
   and `protein.gene_id` is linked; a shared gene is deduped across two proteins.
   Existing tests (no `gene_bulk`) remain unchanged and green.
4. Full gates: `make test` (unit + import-linter), `make test-api`, `make lint`
   (ruff + ruff-format + mypy) all clean. The import-linter `independence`
   contract still holds (Gene and Protein are both in `protein_catalog`; no
   cross-context import is introduced).

## Decisions / Risks

- **`ItemResult` reuse:** import the existing dataclass from
  `bulk_upsert_proteins`, or lift it to `application/shared/bulk.py` and have both
  import it. Prefer the small shared-module lift to avoid an application→
  application sideways import; confirm import-linter is happy either way during
  implementation.
- **Optional runner collaborator** keeps the change additive and existing tests
  untouched — chosen over making gene import mandatory in the runner.
- **One organism per proteome** means `{tax_id}:{basis}` keys are unique within a
  run; cross-organism collisions are impossible by construction.

## Final Step (the actual ask)

After all gates are green:

```bash
# ensure local Postgres is up + migrated (make up), then:
cd backend && uv run python -m protcellar.scripts.import_proteome UP000001584
```

Verify via the API (`GET /api/v1/genes`, `GET /api/v1/proteins?...`) or a direct
count that genes exist and proteins are linked.
