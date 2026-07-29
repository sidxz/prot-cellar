# Gene locus-first display label

**Date:** 2026-07-28
**Status:** Implemented (see the ORF-name addendum at the end — the ladder shipped as
3-tier, not the 2-tier described in the original body below).
**Branch:** `feat/gene-locus-display-label`

## Problem

Biologists reference organisms by convention. For *M. tuberculosis* H37Rv, genes are
known by their **Rv locus tag** (`Rv1066`, `Rv1297`) while proteins are known by their
**gene symbol** (`rho`, `ppdK`). The catalog currently leads gene views with the gene
symbol, so the gene `rho` shows as `rho` where a TB biologist expects `Rv1297`.

The request was "make the naming convention configurable per strain." Investigation showed
the variance the user intuited is already encoded in the *data*, not something that needs a
config table (see Non-goals).

## What already works (no change)

Protein views are already correct. `Gene.primary_name` is computed at import as a ladder —
**gene symbol → ordered locus name → ORF name** (`uniprot_mapper.py:_gene_primary_name`,
280-289). So:

- `rho` → `primary_name = "rho"` → protein row leads with **rho** ✓
- `Rv1066` (no symbol) → `primary_name = "Rv1066"` → protein row leads with **Rv1066** ✓

The protein list's secondary line already shows `Rv1297, MTCY373.17` (from `synonyms`).
**No protein-side label change is required** — only a downstream fix so the split below
does not drop the locus from that secondary line.

## The convention (decided)

**Gene views lead with the ordered locus name; protein views lead with the gene symbol.**

This resolves to a single universal ladder for the *gene* context, with **no per-strain
config**:

> **Gene display label = first ordered locus name → else `primary_name`**

Because `primary_name` is already symbol-else-locus-else-orf, this one rule covers every
organism in the DB (verified 2026-07-28 against live data — 20,675 human / 8,244 TB /
5,361 *P. falciparum* genes):

| Organism | Gene example | Ordered locus name? | Gene label |
|---|---|---|---|
| *M. tuberculosis* | `rho` | `Rv1297` | **Rv1297** |
| *M. tuberculosis* | `Rv1066` (no symbol) | `Rv1066` | **Rv1066** |
| *P. falciparum* | `ATG11` | `PF3D7_0216700` | **PF3D7_0216700** |
| *H. sapiens* | `TP53` | *(none — human uses HGNC/symbols)* | **TP53** (fallback) |

The "human wants symbols, TB wants loci" difference falls out of *whether ordered locus
names exist* — human genes have none, so the ladder auto-falls-back to the symbol. No knob.

## The blocker: ordered locus names are flattened

Today the importer parses UniProt's four gene sub-fields (`geneName`, `synonyms`,
`orderedLocusNames`, `orfNames`) but **merges the last three into a single flat
`synonyms[]`** (`uniprot_mapper.py:_gene_synonyms`, 304-318, line 310). At display time the
locus tag (`Rv1066`) is indistinguishable from a real synonym or an ORF name, so a gene
view cannot cleanly lead with it — the only alternative would be regex-guessing `Rv\d+`
prefixes, which is organism-specific and hacky (explicitly rejected).

**Fix: promote `ordered_locus_names` to its own field** through the whole chain. The
importer already extracts them (line 310) — it just needs to store them separately instead
of dumping them into `synonyms`. ORF names stay in `synonyms` (they still belong on the
secondary line; splitting them too is unnecessary work).

## Design

### 1. Domain — `Gene` aggregate
`backend/src/protcellar/domain/protein_catalog/gene.py`

- Add `ordered_locus_names: list[str]` (`__init__` + `create()` params, default `[]`;
  handle in `update()` like `synonyms`).
- Add a module-level pure resolver reused by all read paths:

  ```python
  def gene_display_label(primary_name: str, ordered_locus_names: list[str]) -> str:
      # ponytail: first OLN wins; a multi-strain gene may list Rv#### + MT#### — a
      # strain-aware pick needs a strain→prefix map, defer until a view needs it.
      return ordered_locus_names[0] if ordered_locus_names else primary_name
  ```
  Location: alongside the aggregate (or `read_models.py`) — one function, two callers
  (`GeneResponse`, gene list DTO). Not a method, to keep presentation choice out of the
  aggregate's behavior.

### 2. Persistence — `GeneModel` + migration
`backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py:33`

- Add `ordered_locus_names: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)`.
- Update the domain↔model mapper both directions.
- Alembic migration: add the nullable column (no data backfill in the migration — see §6).

### 3. Importer — stop flattening, extract distinctly
`backend/src/protcellar/infrastructure/ingestion/uniprot_mapper.py`

- New `_ordered_locus_names(gene) -> tuple[str, ...]` = `_values(gene.get("orderedLocusNames"))`.
- `_gene_synonyms` (304-318): **remove line 310** (`pool.extend(_values(gene.get("orderedLocusNames")))`).
  ORF names (line 311) stay.
- `map_uniprot_genes`: populate `ordered_locus_names` on the import record.
- `_gene_checksum` (335-337): **include `ordered_locus_names` in the basis**, so change
  detection stays correct after the split (and so the backfill re-import actually updates
  rows — the moved data changes both `synonyms` and the new field).

### 4. Import application
`backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py`

- `GeneImportRecord` (23-35): add `ordered_locus_names: tuple[str, ...] = ()`.
- `BulkUpsertGenes`: thread it into `Gene.create` / `Gene.update`.

### 5. Read side — DTOs
- **Gene detail** `GeneResponse` (`interface/routes/genes.py:80-141`): add
  `ordered_locus_names: list[str]` and `display_label: str` (computed via `gene_display_label`).
- **Gene list DTO** (the item type behind `gene-columns.tsx`, populated by `ListGenesQuery`):
  add `ordered_locus_names` + `display_label`.
- **Protein-embedded** `GeneSummaryResponse` (`interface/routes/proteins.py:159-168`): add
  `ordered_locus_names: list[str]`. **Lead unchanged** (`primary_name`). This is what keeps
  `Rv1297` on the protein row's secondary line after it leaves `synonyms`.
- **Gene neighborhood** DTO (`get_gene_neighborhood`): add `display_label` if the genomic
  context section is to show loci (see frontend §7).

### 6. Backfill
Existing genes have the locus buried in `synonyms` with no marker → it **cannot** be
re-derived in place (that is the whole problem). Repopulate by re-running the existing
import via CLI — idempotent upsert, and the checksum change (§3) forces the update:

- **TB (H37Rv)** and **P. falciparum** proteomes: re-import. ~8.2k + ~5.4k genes.
- **Human**: **skip** — human genes have no ordered locus names, so the field stays empty
  and `display_label == primary_name` (no behavior change), and re-importing 147k proteins
  is not worth zero display delta.

No new backfill script — reuse `import_proteome`.

### 7. Frontend
Regenerate orval types first (new fields on `GeneResponse` / `GeneSummaryResponse` / gene
list item / neighborhood).

- **Gene list** `gene-columns.tsx:86`: `field: "primary_name"` → `"display_label"`.
- **Gene detail** header `gene-detail.tsx:231` + breadcrumb `:198`: use `display_label`.
- **Gene ref** `shared/components/common/gene-ref.tsx:37`: use `display_label`.
- **Genomic context** `sections/genomic-context-section.tsx:130`: `name` → `display_label`.
- **Protein list** `protein-columns.tsx` `IdentityCell` (secondary line, 39-43): render
  `gene.ordered_locus_names` **before** the filtered `synonyms`, so the protein row's
  secondary still reads `Rv1297, MTCY373.17`. Lead (`gene.primary_name`) unchanged.

## Non-goals (deferred)

- **Per-strain / per-organism config knob.** A `gene_label_style: SYMBOL_FIRST | LOCUS_FIRST`
  enum on the organism was considered and dropped — the universal ladder already produces the
  right label for every current organism. Add it only when a *locus-bearing* organism needs
  **symbols** in its gene view (none does today). `// ponytail: no config; add gene_label_style enum on Organism when a locus-bearing organism wants symbol-led genes`.
- **Strain-aware locus selection.** When a gene lists loci from multiple strains
  (`Rv0815c` + `MT0837`), the lead is `ordered_locus_names[0]`. A strain-filtered pick needs
  a strain→prefix map; defer until a view demands it.
- **The dead `proteinPrimaryName` helper** (`protein-catalog/lib/protein-format.ts`) is
  unrelated and out of scope.

## Test checkpoints (ponytail: one runnable check per non-trivial change)

- `uniprot_mapper`: given a gene block with `orderedLocusNames` + `orfNames` + `synonyms`,
  assert OLN land in `ordered_locus_names` and are **absent** from `synonyms`; ORF names
  remain in `synonyms`; `_gene_checksum` changes when OLN change.
- `gene_display_label`: locus present → returns first locus; empty → returns `primary_name`
  (the human fallback case).
- Migration applies cleanly (column added, nullable).

## Affected files (summary)

Backend: `gene.py`, `models.py` (+ alembic), `uniprot_mapper.py`, `bulk_upsert_genes.py`,
`interface/routes/genes.py`, `interface/routes/proteins.py`, gene-list read model +
neighborhood DTO.
Frontend: orval regen, `gene-columns.tsx`, `gene-detail.tsx`, `gene-ref.tsx`,
`genomic-context-section.tsx`, `protein-columns.tsx`.
Ops: re-import TB + *P. falciparum* proteomes.

---

## Addendum (2026-07-28) — ORF-name extension, as implemented

The original body assumed *P. falciparum*'s `PF3D7_…` identifiers were UniProt
**ordered locus names**. Backfill proved otherwise: UniProt files them as **ORF
names** (`orfNames`), the same category as TB's cosmid names (`MTCY373.17`). So the
2-tier ladder (`ordered_locus → symbol`) left *named* Pf genes leading with their
symbol instead of `PF3D7_…`.

**Shipped instead — a 3-tier ladder and a second distinct field:**

> **Gene display label = first ordered locus name → else first ORF name → else `primary_name`**

- `orf_names` is promoted to its own field alongside `ordered_locus_names`, through the
  same chain (Gene aggregate → `GeneModel` +migration → importer `_gene_synonyms` stops
  flattening `orfNames` too → `GeneImportRecord` → DTOs → both frontend secondary-line
  composes). `_gene_checksum` includes it.
- **TB is unaffected**: its `Rv####`/`MT####` ordered locus names take precedence, so the
  ORF tier is never reached for TB genes that have a locus.
- **Pf named genes now lead with `PF3D7_…`** (ORF tier); symbol-less Pf genes already did.
- **Human** still falls through both tiers to the symbol (no loci, no ORF names).
- Ceiling accepted (per the "extend" decision): a gene with *only* an ORF name and no
  ordered locus name leads with the ORF name — desired for Pf, and harmless for the few
  such TB genes.

**Backfill:** re-import the three locus/ORF-bearing proteomes — `UP000001584` (TB H37Rv),
`UP000001020` (TB CDC1551), `UP000001450` (*P. falciparum*). Human (`UP000005640`) skipped.

The "no per-strain config" property is unchanged and now covers every Mycobacterium
strain/species and Plasmodium by construction — each organism's locus/ORF prefix lives in
its own data.
