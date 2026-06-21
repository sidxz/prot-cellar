# Gene Page Enrichment — Locus & Evolutionary Context

- **Date:** 2026-06-21
- **Status:** Approved (autonomous build authorized via `/loop`)
- **Branch:** `feat/gene-locus-context`

## 1. Problem & context

Gene detail pages are sparse: name, synonyms, a few external IDs (NCBI/Ensembl/HGNC), and
linked proteins. This is not an oversight — **UniProt, our only ingestion source, carries
almost no gene-level data.** Everything genuinely *gene-shaped* (genomic coordinates,
essentiality, conservation, operon structure) lives in databases we have not ingested.

> Enriching gene pages is fundamentally a data-sourcing problem, not a layout problem.

The app targets early drug discovery — primarily *M. tuberculosis*, then malaria, cancer,
and other infectious disease.

## 2. Conceptual model — gene vs protein vs target

| Entity | Is the… | Nature | Scope |
|---|---|---|---|
| **Gene** | locus — *where it is, how conserved, whether it matters* | intrinsic biology, factual | global reference |
| **Protein** | molecule — *structure, function, domains* | intrinsic biochemistry, factual | global reference |
| **Target** | hypothesis — *"we're pursuing this; here's the chemistry"* | campaign decision | workspace-scoped |

Gene and protein are both **factual/global**; the target is **decisional/workspace**.
Essentiality and conservation *feel* like "target" data but are **intrinsic facts about the
locus** — they *inform* target triage without *being* a target. The gene page answers
"should this even become a target?"; the verdict (weighing the facts + chemistry) lives on
the future target page.

**Decision:** facts (essentiality, conservation, ortholog calls) live on the gene with
provenance; the triage *verdict* is deferred to the target page. The gene page presents
facts **neutrally — no druggability score.**

## 3. The gene page = four universal axes + a bridge

Early-discovery target validation reduces to four universal questions. They are
organism-agnostic; only the datasets that answer them differ.

| Axis | Question | TB | Malaria | Cancer |
|---|---|---|---|---|
| **Vulnerability** | does losing it hurt? | DeJesus TnSeq (ES/GD/NE) | piggyBac MIS/MFS | DepMap dependency |
| **Selectivity** | will hitting it hurt the patient? | human ortholog? | human ortholog? | cancer-vs-normal differential |
| **Robustness** | holds across the treated population? | conservation across isolates | conservation across spp. | recurrence / mutation freq |
| **Context** | where/when does it live? | operon + hypoxia expression | life-stage expression | tissue + amplicon locus |

**Bridge — Encodes:** the protein(s) this gene makes (already wired). Kept as a bridge, not
expanded into protein detail.

## 4. Genericity strategy — *model the question, not the disease*

Three layers:

1. **Generic domain layer.** Gene carries a typed, provenance-stamped annotation list
   `{axis, key, value, value_type, dataset, condition, evidence, source}` — **not** TB-shaped
   columns like `is_essential`. Extends the existing `CrossReference` value-object pattern.
2. **Disease/source adapters at ingestion.** Per-source mappers (Mycobrowser, DeJesus, later
   DepMap/PlasmoDB) translate into the generic shape. All organism-specificity is quarantined
   here, mirroring `uniprot_mapper.py`.
3. **Conditional genome-shape modules.** The operon/neighborhood map is *prokaryote-only* —
   renders when applicable, hides otherwise (same conditional-rendering discipline the protein
   page already uses for the subcellular diagram).

**YAGNI:** design the axis-shaped schema now, implement only the TB instance. Adding a future
disease is "write a mapper + a render branch," never "migrate the schema."

**Guardrail (non-goals):** no protein function/structure/GO on the gene page; no
compounds/SAR/druggability score; triage verdict deferred to the target page.

## 5. Data model

### 5.1 Genomic location — first-class, singular, intrinsic
Add nullable scalar fields to `Gene` + `GeneModel` (populated by genome adapters, never by
UniProt):

- `genomic_accession: str | None` — replicon/sequence accession (e.g. `NC_000962.3`)
- `genomic_start: int | None`, `genomic_end: int | None` (1-based, inclusive)
- `genomic_strand: str | None` — `'+'` / `'-'`
- `assembly: str | None` — e.g. `ASM19595v2`

Composite index `(organism_id, genomic_accession, genomic_start)` for neighborhood queries.
`length_bp` is derived (`end - start + 1`), not stored.

### 5.2 Annotations — generic, multi-valued evidence body
New frozen value object `GeneAnnotation` (mirrors `CrossReference`):

- `axis: GeneAnnotationAxis` — enum: `VULNERABILITY | SELECTIVITY | ROBUSTNESS | CONTEXT | EXPRESSION`
- `key: str` — e.g. `"essentiality"`, `"functional_category"`, `"human_ortholog"`
- `value: str` — display value (numeric values stringified)
- `value_type: str` — `"categorical" | "continuous" | "boolean" | "text"` (render hint)
- `dataset: str | None`, `condition: str | None`, `evidence: str | None`, `source: str | None`, `source_url: str | None`

Stored as JSON column `annotations` on `genes` (mirrors `cross_references`); grouped by axis
in-app for display. A separate indexed table (for cross-gene queries like "all essential
genes") is **deferred until needed** — YAGNI.

### 5.3 Neighborhood — derived, no storage
Query genes in the same `organism_id` + `genomic_accession`, ordered by `genomic_start`,
N up/downstream of the target. Returns lightweight summaries (id, primary_name, start, end,
strand, + the vulnerability annotation for coloring).

## 6. API

- Extend `GeneResponse`: genomic-location fields, `length_bp`, and `annotations` (with axis).
- New `GET /api/v1/genes/{gene_id}/neighborhood?window=N` → ordered neighbor summaries with
  essentiality (meaningful only when location is present).
- Regenerate the frontend client (orval) after the schema change — **gated** on a clean tree (§9).

## 7. Frontend (gene detail)

New sections, all **conditional-null-when-empty**, matching existing section conventions
(`Card` wrapper, early null return, `{ gene }` prop):

- **Genomic Context module** (prokaryote-conditional): location row (accession, coords,
  strand, length) + a horizontal **neighborhood/operon map** of surrounding genes, each shaded
  by vulnerability, current gene highlighted, neighbors linking to their gene pages.
- **Axis panels:** one panel per axis present. v1 implements **Vulnerability** (essentiality
  chips with dataset/condition provenance). Selectivity/Robustness/Context render generically
  when annotations exist (scaffolded; data deferred).
- **Encodes** (linked proteins) retained as the bridge.

Prokaryote detection via Organism `division` (`"Bacteria"`) or lineage walk; helper
`isProkaryote(organism)`.

## 8. Ingestion adapters (last; behind a documented import step)

- **Mycobrowser GFF adapter** → genomic location + functional-category annotation (CONTEXT
  axis) + operon grouping. Keyed by Rv locus tag → matched to existing genes via
  `source_record_id` / `primary_name` / synonyms.
- **DeJesus 2017 adapter** → vulnerability annotations (ES/GD/NE), `dataset="DeJesus 2017"`,
  `condition="in vitro 7H9"`, `evidence=PMID:28096490`.

Pure mappers tested with small fixtures; full import via a documented CLI/import command (real
data files fetched separately). Idempotent upsert keyed on `(source, source_record_id)` +
checksum, consistent with the existing gene import.

## 9. Working-tree constraint (build sequencing)

The working tree holds uncommitted, unrelated work (protein-list gene-summary; auth/re-auth)
overlapping `gene_repository.py`, `repository.py`, and the generated frontend client. To avoid
entangling it:

- Phases touching only **clean/new** files (domain model, ORM columns, migration, unit tests,
  docs) proceed immediately.
- Phases touching **dirty** files (repository mapping/neighborhood query, API client
  regeneration, frontend) wait until the tree is committed/stashed.

## 10. Phasing

1. **Domain foundation** — `GeneAnnotation` value object + axis enum + `Gene` location/annotation
   fields + unit tests. *(clean)*
2. **Persistence** — `GeneModel` columns + JSON mapping + migration + repo neighborhood query +
   tests. *(touches dirty `gene_repository.py` — gated)*
3. **API** — `GeneResponse` fields + neighborhood endpoint + tests; regenerate client. *(gated)*
4. **Frontend** — genomic-context module + neighborhood map + vulnerability panel + generic axis
   panels + `isProkaryote` helper + component tests. *(gated)*
5. **Ingestion adapters** — Mycobrowser GFF + DeJesus, fixture-tested, documented import.
   *(mostly new files)*

## 11. Deferred / open

- Selectivity (human ortholog via OrthoDB/eggNOG) and Robustness (conservation) adapters —
  schema ready, data deferred.
- Expression axis (RNA-seq conditions) — deferred.
- Resistance/variant annotations (WHO TB catalog) — deferred.
- Cross-gene queries (indexed annotations table) — deferred until needed.
- Malaria / cancer adapters — schema is generic; not implemented in v1.
