# Target-Biology Data Model — Design

**Date:** 2026-07-15
**Status:** Approved (design); implementation plan to follow
**Scope:** Backend data model for prot-cellar's target-biology facts — the 8 legacy
DAIKON "Gene sub-entities" that this app now owns.

## 1. Context & goal

Legacy DAIKON conflated a single "Gene" god-object holding locus + molecule +
eight kinds of downstream biology. In the new suite, ownership was settled
(2026-07-15) by a **FACT-vs-DECISION** rule: a fact a bench scientist records
regardless of any pipeline lives in a **cellar**; a decision/score/pipeline
artifact lives in **daikon**. By that rule prot-cellar — the target-biology
knowledge base — owns **all 8** sub-entities as raw facts; daikon only
references and rolls them up.

The 8 sub-entities and their attachment (decided; see §7):

- **Gene-side (genetics):** Essentiality, Vulnerability, Hypomorph, CRISPRi
  Strain, Resistance Mutation.
- **Protein-side (molecule):** Protein Production, Protein Activity Assay,
  Unpublished Structure.

This document designs the **record shape** for those facts and specifies the
**first slice** (2 records, end-to-end) that validates the shape before it is
stamped onto the remaining six.

Upstream design memory (daikon-gen3 project): `daikon-gen3-data-ownership-model`
and `daikon-gen3-target-biology-schema`. Those captured the daikon-side
understanding and explicitly deferred the prot-cellar entity design to
"prot-cellar research" — which is this spec. The cores below are validated
against prot-cellar's real code, not taken as gospel.

## 2. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Schema shape | **Hybrid** (typed cores + keep generic `GeneAnnotation`) | Typed where daikon computes or where a relational/cross-app ref or lifecycle exists; generic annotation stays for descriptive-only axes. Best maintainability + daikon integration without throwing away a working mechanism. |
| First slice | **Essentiality + CRISPRi Strain**, end-to-end | Proves the pattern (typed core + provenance + extensions + flat→typed migration + intra-cellar reference) on the two hardest representative cases before replicating. |
| Slice-1 Gene fact | **Essentiality** (not Vulnerability) | The ~489 existing rows are `GeneAnnotation(axis=vulnerability, key="essentiality")` — categorical DeJesus calls. That IS essentiality; a continuous vulnerability index is not loaded. Essentiality has real data to migrate; Vulnerability is the identical shape, new-import-only, and lands next. |
| Resistance Mutation attachment | **Gene** + protein-coordinate cross-ref | Heritable variant catalogued with genetics; a `L273A→residue` cross-ref lets structure views render it. |
| Package | **New `target_biology` bounded context** | Distinct concern (observations about a target) from the reference catalog (Gene/Protein identity). Honors the bounded-context independence contract; references genes/proteins by bare UUID. |
| App name | **Keep `protcellar`** | Scope is "target-biology knowledge base," but a package/repo rename is pure churn for zero functional gain. Revisit only on request. |

## 3. The record shape (Hybrid)

Each typed sub-entity record = **typed core** + **`Provenance`** VO + **`extensions`** JSONB.

- **Core** — 3–5 typed columns intrinsic to the concept. We own & version this
  spec; it is the contract daikon rolls up on. Standardization is mandatory:
  daikon cannot compare/roll up / feed the copilot without a predictable core.
- **Provenance** — one shared value object (§4), reused by every record.
- **Extensions** — a free `dict` persisted as a JSONB column. Method-/org-specific
  tail lives here so legacy migration is lossless (every legacy column maps to
  exactly one layer). The **governing registry is deferred** (§4).

**The hybrid line** — typed record vs. keep `GeneAnnotation`:

> If daikon computes on it, or it carries a relational reference (a strain), a
> cross-app reference (a compound/ligand), or a lifecycle (production status) →
> **typed record**. If it is a cited display fact nobody computes on
> (`functional_category`, expression note) → **`GeneAnnotation`** (unchanged).

`GeneAnnotation` (existing generic axis-tagged VO on Gene) is **kept** for the
`context`/`expression` axes. Its `vulnerability`-axis essentiality rows migrate
into the typed `Essentiality` record (§6); its `context` rows stay put.

## 4. Shared building blocks (`domain/shared/`)

### `Provenance` (new frozen VO)

Scientific provenance — who observed a fact and where it is published.

```
Provenance:
    source_type: ProvenanceSourceType   # published | preprint | private_comm | internal | patent
    citations: list[Citation]           # 0..n
    contributor_researcher: str | None
    contributor_organization_id: uuid.UUID | None   # -> existing Organization aggregate
    observed_on: date | None
    note: str | None
```

### `Citation` (new frozen VO)

```
Citation:
    pmid: str | None
    doi: str | None
    url: str | None
    label: str | None
    # invariant: at least one identifier present
```

### Reconciliation with what already exists

- **`ProvenanceMixin`** (infra: `persistence/sqlalchemy/provenance.py`) is
  *import lineage* — `source`, `source_release`, `source_record_id`,
  `source_record_checksum`, `imported_at`. It answers "which import produced
  this row." It is **not** the scientific `Provenance` VO and does **not**
  change. A typed record MAY carry both: import-lineage columns (when imported)
  and the domain `Provenance` VO (the citation/contributor). Different concerns,
  different layers.
- **`CrossReference`** (`database:accession` + properties) is reused for external
  DB links but NOT for citations (a citation may carry pmid AND doi AND label —
  it does not fit `database`+`accession`). Hence a dedicated `Citation` VO.

### Extensions registry — DEFERRED (ponytail)

The `extensions` **column** ships now (free JSONB; lossless parking of
method-specific tail). The **per-org field-definition registry +
JSON-Schema/Pydantic validation** is **deferred** until a second org actually
needs a validated custom field — the convergence loop then promotes a
commonly-added extension to a core column (a rare, deliberate migration).
Building the registry now is speculative infrastructure with no consumer.

### `workspace_id` on every record — published vs. private, unified

Every typed record carries `workspace_id`, which unifies visibility:

- **Published fact** (DeJesus 2017, Cell 184 CRISPRi-VI) → `GLOBAL_WORKSPACE_ID`
  (same reserved workspace Gene/Protein reference data uses).
- **Private measurement** (a lab's unpublished essentiality) → that workspace.

`source_type` drives the default; the field is explicit on the record.

## 5. New bounded context: `target_biology`

Mirrors every existing context (`taxonomy`, `protein_catalog`, `target`, …):

```
domain/target_biology/            aggregates, enums.py, events.py, repository.py (ports)
application/target_biology/       use-case services
infrastructure/persistence/sqlalchemy/target_biology/   models.py, *_repository.py, _provenance_json.py
```

- Added to the **`Bounded context independence`** import-linter contract.
- References `gene_id` / `protein_id` as **bare `uuid.UUID`** — never imports
  `protein_catalog` (exactly how `target` holds `protein_id` and everything
  holds `organism_id`). Independence preserved.
- Shared VOs (`Provenance`, `Citation`) live in `domain/shared/`, importable by
  all contexts (the common kernel is not in the independence contract).

## 6. First slice — two aggregates, end-to-end

Both follow prot-cellar's existing aggregate pattern exactly: `AggregateRoot`
subclass, `create()` classmethod registering a `*Created` event, `update()`
registering `*Updated`, an `enums.py`, an `events.py`, a repository port, an
imperative SQLAlchemy model + repository, an alembic migration, and unit tests.
`provenance` persists as a JSONB column via a `_provenance_json.py` helper
(mirrors `_annotation_json.py`); `extensions` as a JSONB column directly.

### 6.1 `Essentiality` (Gene-side aggregate) — validates typed core + flat→typed migration

Core:

| Field | Type | Notes |
|---|---|---|
| `gene_id` | uuid | the locus this fact is about (bare ref) |
| `classification` | `EssentialityClass` (vocab) | essential / essential_domain / growth_defect / non_essential |
| `condition` | str? | configurable vocab (e.g. "in vitro 7H10") |
| `method` | str? | configurable vocab (e.g. "TnSeq") |
| `confidence` | float? | normalized, optional |
| `workspace_id` | uuid | GLOBAL for published |
| `provenance` | Provenance | DeJesus 2017 citation |
| `extensions` | dict (JSONB) | raw call string + any table-specific stats |

**Migration (real data):**

1. Read the ~489 `GeneAnnotation(axis=vulnerability, key="essentiality")` rows.
2. Create one `Essentiality` record per gene: `classification` normalized from
   the raw call (raw preserved in `extensions`), `method="TnSeq"`,
   `provenance.source_type=published` citing DeJesus 2017.
3. Drop those `vulnerability/essentiality` `GeneAnnotation` rows (single source
   of truth). `context`/`functional_category` annotations are untouched.
4. Repoint the enrichment importer (`gene_enrichment_mapper`) to write
   `Essentiality` records instead of the flat annotation, so re-import does not
   recreate flat rows.

### 6.2 `CrispriStrain` (Gene-side aggregate) — validates the relational-reference case

A physical CRISPRi knockdown strain (a lab reagent) that Hypomorph will
reference in a later slice.

| Field | Type | Notes |
|---|---|---|
| `name` | str | strain designation (required, non-empty) |
| `target_gene_id` | uuid | the Gene it knocks down (bare ref) |
| `workspace_id` | uuid | the lab that built it (or GLOBAL if published) |
| `provenance` | Provenance | |
| `extensions` | dict (JSONB) | vector / promoter / induction specifics |

This proves an intra-cellar reference that a *later* sub-entity (Hypomorph)
points at — the reference pattern the remaining entities reuse.

## 7. Full 8-entity map (built after the pattern is proven)

Attach by what you manipulate/measure. Cores are the daikon-gen3 baseline,
to be validated per-entity when each slice lands. `*` = portable id resolved to
chem via daikon's link map (denormalized ref VO mirroring chem-cellar's
`TargetRef{id,name,type}`; **not** an FK).

- **Gene-side**
  - Essentiality — classification, condition, method *(slice 1)*
  - Vulnerability — condition, method, `vulnerability_score` (normalized), confidence; **keep CRISPRi-VI index/bounds/%max/bin/rank in extensions — do NOT bake one methodology into core**
  - Hypomorph — `knockdown_strain` (→ CrispriStrain), `growth_defect` (bool), severity
  - CRISPRi Strain — name, target gene ref *(slice 1)*
  - Resistance Mutation — mutation, `compound*`, `mic_shift` (fold), parent_strain, protein-coordinate cross-ref
- **Protein-side**
  - Protein Production — status, expression_host, purity
  - Protein Activity Assay — activity_measured, format/readout, throughput
  - Unpublished Structure — method, resolution (Å), `ligands*`, is_published/is_experimental

## 8. Out of scope / deferred

- The extensions **registry** + JSON-Schema validation (§4).
- The cross-cellar ref VO (`compound*`/`ligands*`) — lands with Resistance
  Mutation / Structure; mirror chem-cellar's `TargetRef` shape then.
- The other six records.
- daikon-side rollups/scorecards (daikon's repo; it references these facts).
- App/package rename to "target-cellar".

## 9. Testing (minimal, per record)

- Unit tests for each aggregate's invariants (`create`, `update`, empty-name /
  bad-enum rejection, event registration).
- A migration test asserting a sample of `Essentiality` records is produced from
  fixture `GeneAnnotation` rows and the source rows are removed.
- No new frameworks; mirror the existing `tests/unit/domain/**` style.
