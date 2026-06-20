# Queryable Rich Protein Data — Design (Sub-project 1 of 3)

**Goal:** Make the already-captured UniProt annotation **queryable across the catalog** — filter the protein list by cross-reference database, GO term (exact), structure availability, and keyword — by normalizing the `cross_references` JSON blob into an indexed table. Also make the proteome **re-sync correct** (release-version-gated + membership reconciliation), **manually triggered** (in-app auto-scheduler deferred).

**Context:** The schema + import pipeline already capture full UniProtKB entries; `GET /api/v1/proteins/{accession}` already returns features, comments, GO/PDB cross-refs, keywords, citations, etc. The gap is that `proteins.cross_references` is a generic `JSON` column — lossless but **not indexable**, so the catalog can't be filtered by it. This is the foundation sub-project; **GO ontology ingestion (piece 2)** and the **frontend viewer (piece 3)** are separate specs.

**Non-goals (separate specs):** GO ontology / subtree queries (piece 2); the frontend protein page with graph/diagram/3D viewer (piece 3); an in-app scheduled sync worker (future).

---

## Part A — Cross-reference normalization

Replace the `proteins.cross_references` JSON column with an owned 1:many table, mirroring the established `protein_features` / `protein_comments` pattern. The domain `CrossReference` VO and the API response shape are **unchanged** — only persistence changes.

- **New table `protein_cross_references`** (`ProteinCrossReferenceModel`, owned collection on `ProteinModel` with `cascade="all, delete-orphan"`, `lazy="selectin"`):
  - `protein_id` UUID FK→proteins (index), `database` String(64) (index), `accession` String(128), `isoform_id` String(20) nullable, `properties` JSONB nullable, `evidence` String nullable.
  - Indexes: `(protein_id)`, `(database)` (for "has any PDB"), `(database, accession)` (for "annotated with GO:X").
  - Use Postgres `JSONB` for `properties` (the current column is `JSON`; JSONB is indexable and the right choice going forward).
- **Domain:** `Protein.cross_references: list[CrossReference]` unchanged.
- **Repository:** `_to_domain` reads `model.cross_reference_rows`; `_to_model`/`_update_model` clear-and-rebuild from the VO list (same mechanic as features/comments). Retire `_xref_json.py`.
- **Migration `<rev>` (destructive, approved):** create `protein_cross_references`; copy existing `proteins.cross_references` JSON → rows; drop the `proteins.cross_references` column. (Trivial volume — a handful of proteins so far; re-import is equally fine.) Downgrade recreates the column and folds rows back.
- **API:** `ProteinResponse.cross_references` still built from the VO list → **no breaking change** to consumers.

## Part B — Catalog filters on `GET /api/v1/proteins`

New optional query params, composing with the existing `organism_id` / `gene_id` / `reviewed` / `min_length` / `max_length` filters under the same cursor pagination. Each is an indexed `EXISTS` subquery:

| Param | Semantics | Query |
|---|---|---|
| `xref_db=PDB` | has a cross-ref in that database | `EXISTS (SELECT 1 FROM protein_cross_references x WHERE x.protein_id = proteins.id AND x.database = :db)` |
| `has_structure=true` | has any 3D-structure ref | same, `x.database IN ('PDB','PDBsum','AlphaFoldDB','EMDB','SMR')` |
| `go_term=GO:0016491` | annotated with exactly this GO term (subtree → piece 2) | same, `x.database='GO' AND x.accession=:go` |
| `keyword=KW-0560` | has this UniProt keyword | `EXISTS (… protein_keywords k WHERE k.protein_id = proteins.id AND k.kw_id = :kw)` |

- `ListProteinsQuery` gains `xref_db: str | None`, `has_structure: bool | None`, `go_term: str | None`, `keyword: str | None`.
- `SQLAlchemyProteinRepository.find_all` adds the corresponding `EXISTS` clauses.
- The `list_proteins` route adds the params and threads them through.

## Part C — Correct re-sync (manual trigger; auto deferred)

- **Version gate:** before streaming entries, the runner compares the live `/proteomes/{id}` `modified` date against the stored `Proteome.source_version`. If equal (and no `--force`), it no-ops and returns a summary with `skipped_unchanged=True`. On import it stores `source_version = meta["modified"]` so the next run can compare. (`Proteome.create`/`update` already accept `source_version`; the runner just needs to pass + persist it.)
- **Reconciliation:** the runner records the set of accessions seen this run; afterward, it lists the proteome's current `proteome_proteins` members and **removes membership links** whose protein's `primary_accession` was not seen (i.e. it left the proteome — deprecated/merged). Proteins themselves are left intact (they may be referenced by targets; a deeper soft-delete is out of scope). Reports `members_pruned`.
- **Trigger:** the existing `python -m protcellar.scripts.import_proteome` CLI, plus a documented `cron` example in the script docstring. A `--force` flag bypasses the version gate. **In-app scheduler is explicitly deferred.**
- New repo support: `ProteomeRepository.remove_protein(proteome_id, protein_id)` (mirrors `add_protein`), and `list_members(proteome_id) -> list[tuple[uuid.UUID, str]]` returning `(protein_id, primary_accession)` by joining `proteome_proteins → proteins`, so the runner can diff the accessions it saw this run against the current members and prune the difference.

## Error handling

- UniProt HTTP/network errors abort the run (idempotent → safe to re-run); the version-gate + checksum upsert make retries cheap.
- Unknown `xref_db` / `go_term` / `keyword` simply return an empty page (no error).
- The cross-ref migration runs inside Alembic's transactional DDL — a failure rolls back cleanly.

## Testing

- **Normalization round-trip:** import → cross-refs persist as rows; `ProteinResponse.cross_references` is byte-for-byte what it was from the JSON column.
- **Each filter** (integration, real DB via the function-scoped UoW pattern): seed proteins with/without PDB, GO terms, keywords; assert each filter returns exactly the right set and composes with `reviewed`/length filters + pagination.
- **Reconciliation:** import accessions {A,B,C}; re-import {A,B} with a bumped proteome version; assert C's membership is pruned and `members_pruned == 1`, A/B untouched.
- **Version gate:** re-run with the same `modified` → `skipped_unchanged`, no writes; `--force` overrides.

## Rollout sequence (for the plan)

1. `protein_cross_references` table + model + repo mapping + data migration (Part A).
2. `ListProteinsQuery` filters + repo `EXISTS` clauses + route params + tests (Part B).
3. Runner version-gate + reconciliation + `remove_protein` + `--force` + tests (Part C).
