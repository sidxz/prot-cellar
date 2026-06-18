# prot-cellar — Design & Scope (v1)

**Status:** Draft for review
**Date:** 2026-06-18
**Author:** Brainstorming session (Claude Code + sidx)

---

## 1. Problem & Vision

`prot-cellar` is the **biology-side counterpart** of `chem-cellar` (codename "Cellar",
`~/workspace/chem-vault2`), an enterprise chemical-compound registration & screening
platform. Where chem-cellar owns *chemistry* (molecules, batches, assays, screening),
prot-cellar owns *biology*: **organisms, strains, proteins, genes, and drug targets**,
mostly mirroring **UniProt** (plus NCBI Taxonomy and ChEMBL target concepts).

The two systems are siblings: same architecture, same auth, same workspace model. They
interoperate so that screening/SAR work in chem-cellar can reference canonical biological
entities owned by prot-cellar instead of duplicating them.

### Why this exists (the load-bearing justification)

Every serious reference database — ChEMBL, IUPHAR/Guide to Pharmacology, DrugBank, Pharos,
BindingDB — enforces the same modeling split:

> **A `Target` (the pharmacological entity a compound acts on) is distinct from the
> `Protein`(s) that constitute it.** A Target references **1..n Components → Proteins**.
> The protein carries the UniProt accession, gene, sequence, and organism — *not* the target.

chem-cellar currently **collapses** this distinction: its `screening_assay.Target` entity
carries `uniprot_id`, `ncbi_gene_id`, `gene_name`, and `sequence` inline. That works only
for single-protein targets and **cannot represent**:

- **Protein complexes** (e.g. GABA-A receptor = GABRA1 + GABRB2),
- **Protein families** (e.g. "p38 MAPK family"),
- multiple proteins sharing a target, or one protein appearing in many targets.

prot-cellar becoming the **canonical owner of Target + Protein**, modeled correctly, is the
core reason the project exists.

---

## 2. Relationship to chem-cellar (interop seam)

| Concern | Ownership |
|---|---|
| Organisms, strains, proteins, genes, targets | **prot-cellar (canonical)** |
| Molecules, batches, assays, screening runs, SAR | chem-cellar (canonical) |
| Compound ↔ target **activities** (IC50/Ki/EC50) | **chem-cellar**, referencing prot-cellar `Target` by ID |

**Direction of reference:** chem-cellar references prot-cellar by **stable Target ID**.
prot-cellar never depends on chem-cellar.

**Migration path for chem-cellar (out of scope for prot-cellar v1, but the design must enable it):**
chem-cellar's inline `Target` fields move to prot-cellar Proteins; chem-cellar's `Target`
becomes a `target_ref` (prot-cellar Target ID). The `chembl_id` retained on prot-cellar
Targets lets existing chem-cellar data be reconciled to ChEMBL during that migration. The
**mapping confidence** of a compound↔target link (ChEMBL's 0–9 confidence-score idea) lives
on the **activity link in chem-cellar**, never on the Target.

---

## 3. Architecture — full mirror of chem-cellar

prot-cellar copies chem-cellar's architecture wholesale. **Before implementing, read
chem-cellar's `docs/backend-code-guidelines.md` and `docs/patterns-and-conventions.md`** —
they are the normative source; this section summarizes only what shapes the design.

**Stack:** Python 3.13+ / FastAPI / SQLAlchemy 2.0 async (asyncpg) / PostgreSQL 16 /
Pydantic v2 / Alembic / Lagom (DI) / dry-python `returns` (Railway) / Valkey / structlog.
`uv` for Python. Sentinel auth SDK (external `identity-service`). **No RDKit cartridge**
(that is chemistry-specific) — prot-cellar may later want a sequence index (Postgres FTS /
trigram, or MMseqs2 out-of-process), but v1 needs no special Postgres extension.

**Layering (enforced by import-linter):** `domain → application → infrastructure → interface`.

| Layer | Depends on | Never depends on |
|---|---|---|
| Domain | nothing (pure Python) | application, infrastructure, interface |
| Application | domain | infrastructure, interface |
| Infrastructure | domain, application | interface |
| Interface | all | — |

**Mandatory patterns inherited from chem-cellar (apply to every new use case):**

1. **Workspace scoping (security-critical).** Every Command/Query carries
   `workspace_id: uuid.UUID`. Routes set it from `auth.workspace_id` — **never** from body/URL.
   Repositories query via `find_by_id_in_workspace(workspace_id, id)`; `save()` re-verifies
   the workspace (defence-in-depth). Uniqueness constraints are workspace-scoped.
2. **Auth guards are the first two lines of a use case:** `require_editor(auth)` (or the role
   needed), then `require_same_workspace(auth, input.workspace_id)` (raises `NotFoundError`,
   not `AuthorizationError`, to avoid leaking entity existence). Never wrap guards in
   try/except → Failure.
3. **Railway pattern.** Use cases return `Result[T, DomainError]`. Expected failures →
   `Failure(...)`; never raise for them. Error→HTTP mapping is centralized
   (`NotFoundError`→404, `ValidationError`→422, `ConflictError`→409,
   `ConcurrencyConflictError`→409+`Retry-After`, `AuthorizationError`→403).
4. **Unit of Work + sync domain events.** `async with self._uow:` → mutate → `await
   self._uow.commit()` (returns events) → dispatch events **after** commit, outside the context.
5. **Optimistic concurrency.** Every aggregate has `version: int`; updates are
   `WHERE id=? AND version=?` → `version+1`; 0 rows → `ConcurrencyConflictError`.
   (Append-only `AuditOperation` is exempt.)
6. **SA model mixins:** `Base + EntityModelMixin + WorkspaceIdMixin + VersionMixin`.
   Repositories implement `_to_domain` / `_to_model` / `_update_model`.
7. **DI via Lagom**, wired in `interface/dependencies/`; one fresh `AsyncUnitOfWork` per request.

**One deliberate divergence from chem-cellar:** taxonomy/UniProt reference data is
effectively **shared, global, read-mostly mirror data**, not per-tenant business data
(see §5.1). The design treats it as workspace-agnostic reference data that tenant entities
point at — it is *not* duplicated per workspace. Tenant-private biology (e.g. a lab's own
strains or curated targets) remains workspace-scoped. This is the one place prot-cellar's
data model differs from chem-cellar's "everything is workspace-scoped" default, and the
guidelines around it are spelled out per-aggregate below.

---

## 4. Bounded contexts

| Context | Aggregates / entities | Mirrors | Tenancy |
|---|---|---|---|
| **Taxonomy** | `Organism`, `OrganismName`, `Strain`, `Proteome` | NCBI Taxonomy + UniProt | Organism/Name/Proteome = shared reference; Strain = workspace-scoped |
| **Protein Catalog** | `Protein`, `Gene` | UniProtKB entry | shared reference (import) + workspace overlays |
| **Target** | `Target` (root) + `TargetComponent` (entity) | ChEMBL target dictionary | workspace-scoped |
| **Workspace Config** (shared) | `Organization`, `ExternalApiKey`, `DataSource`, `ControlledVocabulary` | copied from chem-cellar | workspace-scoped |
| **Audit & Compliance** (shared) | `AuditOperation` (append-only) | copied from chem-cellar | workspace-scoped |
| **Cross-cutting VOs** | `CrossReference`, `Evidence`/`Provenance`, identifier registry | identifiers.org / Bioregistry | — |

> **Tenancy nuance.** Reference entities (Organism, OrganismName, Proteome, imported
> Protein/Gene) are shared mirror data with provenance, keyed by their external accession.
> Workspace-scoped entities (Strain, Target, and any locally-curated Protein annotations)
> reference them. The exact storage boundary — single shared schema vs. a `workspace_id`
> nullable column with a "global" sentinel — is an open question (§10, Q1) to resolve in
> the plan, following chem-cellar's persistence conventions.

---

## 5. Domain model (v1)

Field lists below are the **v1 target**. Types are indicative; `?` = nullable/optional.
Every aggregate carries `id`, `version`, `created_at`, `updated_at`, and the provenance
columns of §8.

### 5.1 Taxonomy context

**`Organism`** — a mirror of an NCBI Taxonomy node (shared reference data).

| Field | Type | Notes |
|---|---|---|
| `ncbi_tax_id` | int? unique | external anchor, e.g. 9606. Nullable for locally-defined nodes |
| `parent_id` | FK→Organism | **adjacency list**; root self-references |
| `rank` | FK→rank lookup | lookup table, NOT enum (NCBI 40+ ranks; GTDB fixed 7) |
| `scientific_name` | text | denormalized convenience; truth is `OrganismName` |
| `division` | text? | e.g. Bacteria, Viruses |
| `genetic_code_id`, `mito_genetic_code_id` | int? | |
| `is_merged`, `merged_into_id` | bool, FK? | tombstone + redirect for retired tax IDs |
| `is_deleted` | bool | tombstone |
| `source` | enum | `NCBI` (v1); `GTDB` later |
| `source_version` | text | provenance (taxdump release) |

- Hierarchy = adjacency list (the natural NCBI mirror). Add a derived materialized-path /
  `ltree` column as a **read accelerator** for subtree/lineage queries (not the source of truth).
- `merged.dmp` / `delnodes.dmp` handling is **v1** — resolving stale tax IDs is a recurring need.

**`OrganismName`** — multi-name per organism (irreducible; NCBI proves it).

| Field | Type | Notes |
|---|---|---|
| `organism_id` | FK | |
| `name` | text | |
| `name_class` | enum | `scientific_name`, `common_name`, `genbank_common_name`, `synonym`, `authority`, `equivalent_name`, `acronym`, `blast_name`, **`uniprot_mnemonic`** (e.g. `HUMAN`, `ECOLI`) |
| `unique_name` | text? | homonym disambiguator |
| `is_preferred` | bool | display |

The `uniprot_mnemonic` name_class is required to parse/round-trip UniProtKB entry names
like `ALBU_HUMAN`.

**`Strain`** — its own aggregate (workspace-scoped), **not** a subtype of Organism.
Rationale: NCBI stopped minting strain-level tax IDs in 2014; modern strains live as
`(species, strain_name, BioSample/assembly)`, and lab strains are often tenant-private.

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | uuid | tenant-scoped |
| `species_organism_id` | FK→Organism (species) | **required anchor** |
| `strain_organism_id` | FK→Organism? | set iff a strain-level tax ID exists (legacy case) |
| `name` | text | e.g. "K-12 substr. MG1655", "ATCC 25922" |
| `isolate` | text? | |
| `biosample_acc` | text? | `SAMN…` / `SAME…` |
| `assembly_acc` | text? | `GCA_…` / `GCF_…` |
| `culture_collection` | text? | e.g. `ATCC:25922` |
| `host_organism_id` | FK→Organism? | viral/host case |
| `metadata` | jsonb? | MIxS-style isolation_source/geo/date (v1: loose JSONB) |

**`Proteome`** — v1-lite (store the identity + link; defer pan/redundant machinery).

| Field | Type | Notes |
|---|---|---|
| `uniprot_proteome_id` | text unique | `UP000005640` |
| `organism_id` | FK | usually strain- or species-level node |
| `strain_id` | FK? | |
| `proteome_type` | enum | reference / representative / redundant / excluded |
| `is_reference` | bool | |
| `assembly_acc` | text? | |
| `source_version` | text | |

### 5.2 Protein Catalog context

**`Protein`** — UniProt-anchored (shared reference data; the heart of the catalog).

| Field | Type | Notes |
|---|---|---|
| `primary_accession` | text unique | validated against UniProt 6/10-char regex |
| `secondary_accessions` | text[] | demerge/merge lineage |
| `entry_name` | text? | e.g. `ALBU_HUMAN` |
| `is_reviewed` | bool | Swiss-Prot (true) vs TrEMBL (false) |
| `protein_names` | jsonb/VO | recommended / alternative / submitted |
| `organism_id` | FK→Organism | **required** (UniProt `OX` line) |
| `strain_id` | FK→Strain? | UniProt `RC STRAIN=` / BioSample case |
| `gene_id` | FK→Gene? | |
| `sequence` | text | amino-acid sequence |
| `seq_length` | int | |
| `seq_mass` | int? | Da |
| `seq_crc64` | text | change-detection checksum (UniProt `SQ` line) |
| `protein_existence` | enum? | PE level 1–5 |
| `keywords` | text[]? | |
| `entry_version`, `sequence_version` | int? | UniProt's two separate counters |
| `cross_references` | `CrossReference[]` | §5.5 |

**`Gene`** — lightest-researched; sensible v1 model.

| Field | Type | Notes |
|---|---|---|
| `primary_name` | text | e.g. `TP53` |
| `synonyms` | text[]? | |
| `organism_id` | FK→Organism | |
| `ncbi_gene_id` | text? | |
| `ensembl_gene_id` | text? | `ENSG…` |
| `hgnc_id` | text? | human |
| `cross_references` | `CrossReference[]` | |

> v1 stores the gene attributes needed to back a Protein and to bridge to chem-cellar's
> `ncbi_gene_id`. Full gene-centric features (Open Targets-style) are out of scope.

### 5.3 Target context

**`Target`** (aggregate root, workspace-scoped) — the pharmacological entity.

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | uuid | |
| `pref_name` | text | |
| `target_type` | enum | ChEMBL subset: `SINGLE_PROTEIN`, `PROTEIN_COMPLEX`, `PROTEIN_FAMILY`, `PROTEIN_PROTEIN_INTERACTION`, `NUCLEIC_ACID`, `ORGANISM`, `CELL_LINE`, `TISSUE`, `UNKNOWN` |
| `organism_id` | FK→Organism? | target-level organism scoping (denormalized convenience) |
| `chembl_id` | text? | retained for migration/reconciliation |
| `pharmacological_class` | text? | GtoPdb-style (GPCR/Kinase/Ion channel/…) — flat string in v1 |
| `cross_references` | `CrossReference[]` | Pharos, GtoPdb, TTD, etc. |

**`TargetComponent`** (entity within the Target aggregate; ordered collection).

| Field | Type | Notes |
|---|---|---|
| `protein_id` | FK→Protein | the canonical protein |
| `relationship` | enum | `SINGLE_PROTEIN` / `PROTEIN_SUBUNIT` / `FAMILY_MEMBER` / `INTERACTING_PROTEIN` |

**Aggregate invariant (v1, the whole point):** cardinality must agree with `target_type`.
`SINGLE_PROTEIN` ⇒ exactly 1 component; `PROTEIN_COMPLEX` / `PROTEIN_FAMILY` /
`PROTEIN_PROTEIN_INTERACTION` ⇒ ≥ 2 components.

> **Deferred:** Pharos `TDL` facet (Tclin/Tchem/Tbio/Tdark), Open Targets tractability
> buckets, ChEMBL `target_relations`, variant/mutant sequences.

### 5.4 Shared contexts (copied from chem-cellar)

`Workspace Config` (`Organization`, `ExternalApiKey`, `DataSource`, `ControlledVocabulary`)
and `Audit & Compliance` (`AuditOperation`, append-only) are ported from chem-cellar with
minimal change. `ExternalApiKey` + `DataSource` are reused for UniProt/NCBI/ChEMBL access
configuration. `ControlledVocabulary` backs the `rank` and `name_class` lookups where a DB
enum is too rigid.

### 5.5 Cross-cutting value objects

**`CrossReference`** — one generic VO, **not** a column per database.

```
CrossReference { database: str, accession: str, properties: dict? , evidence: str? }
```

Backed by a small embedded **Bioregistry-style identifier registry**
`{prefix, regex, uri_template}` for the prefixes we support (UniProt, RefSeq, Ensembl, PDB,
GO, InterPro, Pfam, EC, KEGG, Reactome, ChEMBL, NCBI taxon/gene). Validates `accession` at
write time and renders resolvable URLs. This registry is the single highest-leverage,
lowest-cost piece — it gives CURIE resolution (`uniprot:P0DP23`) and write-time validation
for the whole long tail.

**`Evidence` / `Provenance`** — shared VO for annotation provenance, with a first-class
**curated-vs-electronic (IEA)** flag (the field users filter on most). Used by the typed
annotations that arrive **later** (GO, InterPro/Pfam region matches, EC).

---

## 6. API surface (v1)

Mirror UniProt's three REST shapes per primary aggregate (proteins, organisms, targets,
genes), all workspace-aware:

- `GET /api/v1/proteins/{accession}` — content-negotiated `json` / `fasta` / `tsv`.
- `GET /api/v1/proteins/search?query=&fields=&format=&size=` — **cursor (keyset)
  pagination** via opaque next-link (default 25, max 500); `fields=` column whitelist;
  `format=` via `?format=` or `Accept`.
- `GET /api/v1/proteins/stream?query=` — full result export.

**Search filters (v1):** by accession (resolving secondary→primary), gene (exact + fuzzy),
organism (by tax ID, **including descendants**), protein name, reviewed flag, length range.
Backed by Postgres (GIN/trigram indexes); a dedicated search index is a later concern.

**ID-resolution endpoint (v1):** resolve an input ID (accession, secondary accession, gene
name, ChEMBL target, Ensembl, RefSeq) to the canonical protein — pivoting through accession,
honoring merged / demerged / deleted lifecycle.

**Bulk import (v1, for the loader):** `POST /api/v1/proteins/bulk` (and `/organisms/bulk`,
`/targets/bulk`) accepting NDJSON/array; **requires provenance** (`source`, `source_release`);
**upsert keyed on `(source, source_record_id)`** with checksum skip; large jobs →
`202 Accepted` + `jobId`, poll `GET /api/v1/jobs/{jobId}`; per-item results with original
index; **dry-run/validation mode**; `Idempotency-Key` header; honors 429 backoff.

---

## 7. Provenance & versioning

Baseline provenance columns on every imported record: `source`, `source_release`,
`import_timestamp`, `source_record_checksum`, `source_record_id`, `source_uri?`. A control
table records processed releases so re-running the same release is a no-op (idempotent).
Snapshot-only sources (UniProt, ChEMBL) publish no deltas — prot-cellar computes its own
via CRC64 / entry-version / content-hash, and a **mandatory delete/obsolete pass** anti-joins
the live table against the full snapshot (taxonomy uses native `merged`/`delnodes`).
Refresh via **blue/green table swap** (or `source_release` partitioning) for zero downtime.

> **Deferred:** SCD Type 2 / bi-temporal history, UniSave-style version archive + history UI.

---

## 8. `prot-cellar-loader` (separate project, scoped here, built separately)

A sibling Python/Jupyter ETL project (analogous to `daikon-chemvault-loader`) that ingests
reference data and **calls prot-cellar's bulk API** — it does *not* write the DB directly.
Architecture borrows Open Targets' fetch/freeze ↔ transform split:

1. **Fetch/freeze:** per-source download modules pinned to an immutable snapshot keyed by
   release. Poll tiny markers (`reldate.txt`, ChEMBL release notes, taxdump timestamps)
   **before** pulling multi-GB files.
2. **Parse/transform:**
   - UniProt → `Bio.SwissProt.parse` over `uniprot_sprot.dat.gz`. **Swiss-Prot first**
     (~575k entries, tractable); TrEMBL (~110 GB) gated behind an explicit flag.
   - NCBI Taxonomy → parse `new_taxdump` `.dmp` (preprocess the `\t|\t` delimiter); load
     nodes/names/lineage; remap via `merged.dmp`, tombstone via `delnodes.dmp`.
   - ChEMBL → restore the Postgres dump locally; extract `chembl_uniprot_mapping.txt` +
     target/component tables (the target→UniProt edges that tie back to chem-cellar).
3. **Load:** batch to NDJSON, POST to the bulk endpoints with provenance, dry-run then commit,
   poll the job, surface per-item failures.

> v1 of prot-cellar ships a **loader skeleton** proving the Swiss-Prot + taxonomy + ChEMBL
> mapping path end-to-end; the full loader is its own project/plan.

---

## 9. v1 scope vs later

**v1 (MUST):**

- Shared foundation: Workspace Config + Audit & Compliance (ported from chem-cellar).
- Taxonomy: `Organism` (adjacency list, ncbi_tax_id, rank-as-lookup, merged/deleted
  tombstones, source-tagged), `OrganismName` (multi-name + UniProt mnemonic), `Strain`
  aggregate, basic `Proteome`.
- Protein Catalog: `Protein` (UniProt core + sequence/CRC64 + organism link), `Gene`.
- Target: `Target` + `TargetComponent` → `Protein`, `target_type`, `chembl_id`, the
  single-vs-complex invariant.
- Cross-cutting: generic `CrossReference` VO + identifier (Bioregistry-style) registry;
  provenance columns + idempotent-reload control table.
- API: per-aggregate CRUD + search (accession/gene/organism) + FASTA + ID-resolution +
  bulk import (202+jobId, dry-run, idempotency, upsert).
- A loader skeleton (Swiss-Prot + taxonomy + ChEMBL UniProt mapping).
- Backend + API only. **No frontend in v1.**

**Later:**

- Typed annotations: GO (aspect + evidence_code), InterPro/Pfam **region** matches
  (start/end + entry_type), EC numbers; shared `Evidence` VO with IEA flag.
- Structure references (PDB ids incl. extended form + AlphaFold `AF-<acc>-F<n>`); viewers
  (PDBe-Molstar, Nightingale/protvista) in the frontend.
- Sequence similarity search (EBI BLAST REST → self-hosted MMseqs2; Foldseek for structure);
  MSA.
- First-class Proteomes / reference-proteome subsets; pan-proteomes.
- TDL / tractability facets (derived from chem-cellar bioactivity + GO + bibliometrics).
- SCD2 / bi-temporal history + UniSave-style version archive.
- GTDB as a second taxonomy source.
- **The Next.js frontend**, built per-context after each backend slice (chem-cellar's
  Domain→…→UI→E2E layering order).
- The full `prot-cellar-loader` project.

---

## 10. Open questions (resolve during planning)

1. **Reference-data tenancy boundary.** Shared schema for global reference data (Organism,
   imported Protein/Gene, Proteome) vs. a nullable `workspace_id` with a "global" sentinel.
   Affects every repository query and the workspace-scoping guards. Resolve against
   chem-cellar's persistence conventions before writing the first migration.
2. **First-context build order.** Taxonomy is the dependency root (Protein needs Organism;
   Target needs Protein), so likely: Taxonomy → Protein/Gene → Target. Confirm in the plan.
3. **Repo strategy.** New standalone repo (`git@github.com:sidxz/prot-cellar.git`?) mirroring
   chem-cellar's monorepo layout (`backend/`, later `frontend/`, `docs/`, compose files), and
   how much of chem-cellar's shared code (Workspace Config, Audit, auth, base repository, UoW)
   is **copied** vs. extracted into a shared package. v1 assumption: **copy** (no premature
   shared-library extraction).
4. **Sequence storage at scale.** Swiss-Prot is tractable in plain columns; if TrEMBL is ever
   enabled, sequence storage/index strategy needs revisiting (out of scope for v1).

---

## 11. Key sources

NCBI Taxonomy (PMC3245000) · taxdump format · UniProtKB user manual (web.expasy.org/docs/userman.html)
· UniProt NAR 2017 (PMC5210571) · UniProt REST/ID-mapping/entry-history help · EBI Reference Proteomes
· Strain taxids→BioSample (PMC4149001) · GTDB (NAR 2022) · ChEMBL interface docs (target/schema questions)
· Open Targets Platform docs (target, tractability, data pipeline/PIS) · Guide to Pharmacology (NAR 2024/2026)
· Pharos/TCRD (NAR 2023) · DrugBank 6.0 (NAR 2024) · BindingDB TSV format · InterPro/Pfam docs · Gene Ontology
docs (GAF 2.2, evidence codes) · ExPASy ENZYME / Rhea · PDB extended IDs (wwPDB) / SIFTS · AlphaFold DB API
· identifiers.org/MIRIAM · Bioregistry · PDBe-Molstar · Nightingale · MMseqs2 / Foldseek.

(Full URLs captured in the brainstorming research transcript.)
