# Gene Enrichment Ingestion — Implementation Plan (Phase 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Populate *M. tuberculosis* H37Rv genes with real **genomic location + functional category** (Mycobrowser GFF) and **essentiality** (DeJesus 2017 TnSeq), via an idempotent match-and-append enrichment pipeline — so the gene page's genomic-context map and vulnerability panel light up with real data.

**Architecture:** Source-specific **pure parsers** (GFF, DeJesus table) → `GeneEnrichmentRecord`s → a `BulkEnrichGenes` application use case that matches each record to an existing gene by **locus tag** (primary_name / synonyms / `source_record_id` suffix) and idempotently **sets** location fields + **merges** dataset-scoped annotations. Thin httpx clients fetch the files; a runner + CLI orchestrate; a documented command runs the real import. All organism/source specificity stays in the adapters (mirrors `uniprot_mapper.py` / `go_obo.py`).

**Tech Stack:** Python / httpx / SQLAlchemy / pytest. Data: Mycobrowser H37Rv GFF3; DeJesus 2017 (mBio, PMID:28096490) essentiality calls.

## Global Constraints

- **Idempotent:** re-running an import **replaces** annotations sharing the same `(dataset, key)` and **sets** (never appends) location fields — no duplicates, stable on re-run.
- Genes are **global reference data**; enrichment matches **within an `organism_id`**.
- **Match key = locus tag** (e.g. `Rv0667`), matched against a gene's `primary_name`, any `synonyms`, or `source_record_id` suffix (`"{tax_id}:{locus}"`).
- **Pure parsers** (no I/O) tested with fixtures; only clients/runner do network/DB I/O.
- Annotation mapping: functional category → **CONTEXT** axis (`key="functional_category"`); essentiality → **VULNERABILITY** axis (`key="essentiality"`, value normalized `essential|growth-defect|non-essential|growth-advantage|uncertain`, `dataset="DeJesus 2017"`, `condition="in vitro 7H9"`, `evidence="PMID:28096490"`).
- Backend tests: `uv run --directory backend pytest <path> -q`. Commit per task (scope `genes`), Co-Authored-By trailer.
- **Data sourcing:** location/functional-category from the **Mycobrowser H37Rv GFF** (primary; confirm exact release URL at impl — fallback NCBI RefSeq GFF `GCF_000195955.2_ASM19595v2` for location only). Essentiality from **DeJesus 2017** — best-effort fetch of a clean table; if no programmatic source, the loader reads a **local file** and Task 7's essentiality step is documented rather than auto-run. Location is the reliable primary deliverable.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `application/protein_catalog/bulk_enrich_genes.py` | `GeneEnrichmentRecord` + `BulkEnrichGenes` match-and-merge use case | Create |
| `domain/protein_catalog/repository.py` | `list_by_organism` (batched) for the match index | Modify |
| `infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py` | impl `list_by_organism` | Modify |
| `infrastructure/ingestion/mycobrowser_gff.py` | pure GFF3 parser → `GffGeneRecord` | Create |
| `infrastructure/ingestion/dejesus_essentiality.py` | pure essentiality-table parser → `{locus: call}` | Create |
| `infrastructure/ingestion/gene_enrichment_mapper.py` | combine parsed GFF + essentiality → `GeneEnrichmentRecord`s | Create |
| `infrastructure/ingestion/mycobrowser_client.py` | httpx fetch of the GFF (+ essentiality loader) | Create |
| `infrastructure/ingestion/gene_enrichment_runner.py` | orchestrate fetch → parse → map → enrich | Create |
| `scripts/enrich_genes.py` (or a typer cmd) | documented CLI entry | Create |
| `tests/unit/...` + `tests/fixtures/...` | tests + small GFF/DeJesus fixtures | Create |

---

### Task 1: `GeneEnrichmentRecord` + `BulkEnrichGenes` use case (matching core)

**Files:** Create `application/protein_catalog/bulk_enrich_genes.py`; Modify `repository.py` + `gene_repository.py` (add `list_by_organism`); Test `tests/unit/application/protein_catalog/test_bulk_enrich_genes.py`.

**Interfaces:**
- Produces: `GeneEnrichmentRecord` (frozen, kw_only): `locus_key: str`, `genomic_accession/genomic_start/genomic_end/genomic_strand/assembly` (optional, mirror `Gene`), `annotations: tuple[GeneAnnotation, ...] = ()`.
- `BulkEnrichGenes.__call__(organism_id: uuid.UUID, records: Sequence[GeneEnrichmentRecord], auth) -> Result[EnrichSummary, DomainError]` where `EnrichSummary = {matched: int, unmatched: int, locations_set: int, annotations_written: int, unmatched_loci: list[str]}`.
- `GeneRepository.list_by_organism(organism_id, *, batch=1000) -> list[Gene]`.

- [ ] **Step 1: failing test** — build 3 fake genes (one with locus in `primary_name`, one in `synonyms`, one in `source_record_id`); enrich with location + a vulnerability annotation; assert each matched, location set, annotation present; re-run and assert no duplicate annotations (idempotent); assert an unknown locus increments `unmatched`.

```python
def _gene(primary, organism, synonyms=(), srid=None):
    return Gene.create(primary_name=primary, organism_id=organism, synonyms=list(synonyms),
                       source="uniprot", source_record_id=srid)

async def test_enrich_matches_by_name_synonym_and_srid_idempotently():
    org = uuid.uuid4()
    repo = _FakeGeneRepo([_gene("rpoB", org, synonyms=["Rv0667"]),
                          _gene("katG", org, synonyms=["Rv1908c"]),
                          _gene("Rv0001", org)])
    uc = BulkEnrichGenes(_FakeUoW(), repo, _NoopDispatcher())
    recs = [GeneEnrichmentRecord(locus_key="Rv0667", genomic_accession="NC_000962.3",
              genomic_start=759807, genomic_end=763325, genomic_strand="+",
              annotations=(GeneAnnotation(axis=GeneAnnotationAxis.VULNERABILITY, key="essentiality",
                 value="essential", dataset="DeJesus 2017"),))]
    s1 = (await uc(org, recs, auth=_admin())).unwrap()
    assert s1.matched == 1 and s1.locations_set == 1
    s2 = (await uc(org, recs, auth=_admin())).unwrap()  # idempotent
    g = repo.by_locus("Rv0667")
    assert len([a for a in g.annotations if a.key == "essentiality"]) == 1
```

- [ ] **Step 2-4:** Run (fail) → implement: `list_by_organism` (repo: `select(GeneModel).where(organism_id==...)`, batched); use case builds a locus→Gene index (`primary_name`, each synonym, and `source_record_id.split(":")[-1]`, all upper-cased for match); for each record `gene.update(genomic_*=..., assembly=...)` when present, and `gene.update(annotations=_merge(gene.annotations, record.annotations))` where `_merge` drops existing annotations whose `(dataset, key)` matches an incoming one then concatenates; `repo.save(gene)`; tally summary → green.
- [ ] **Step 5: commit** `feat(genes): BulkEnrichGenes match-and-merge use case`

---

### Task 2: Mycobrowser GFF parser (pure)

**Files:** Create `infrastructure/ingestion/mycobrowser_gff.py`; Test `tests/unit/infrastructure/test_mycobrowser_gff.py` + a ~6-line GFF fixture.

**Interfaces:** Produces `GffGeneRecord` (frozen): `locus_tag, seqid, start: int, end: int, strand, gene_name: str|None, product: str|None, functional_category: str|None`; and `parse_mycobrowser_gff(text: str) -> list[GffGeneRecord]`.

- [ ] **Step 1: failing test** — feed a 2-gene GFF3 fixture (a `gene` line with `locus_tag=Rv0667;gene=rpoB;...` and a `CDS`/`Functional_Category` attribute); assert the parsed record has locus_tag, coords, strand `+`, gene_name `rpoB`, functional_category.
- [ ] **Step 2-4:** parse: split on tabs, skip `#`/empty; take `gene` (or feature carrying `locus_tag`) lines; parse col4/5 (start/end, 1-based), col7 (strand), col1 (seqid), col9 attributes (`key=value;` → dict, URL-decoded); map `locus_tag`, `gene`, `product`, `Functional_Category`/`functional_category`. Coalesce gene+CDS by locus_tag if needed. → green.
- [ ] **Step 5: commit** `feat(ingestion): Mycobrowser GFF parser`

---

### Task 3: DeJesus essentiality parser (pure)

**Files:** Create `infrastructure/ingestion/dejesus_essentiality.py`; Test + a small TSV/CSV fixture.

**Interfaces:** Produces `parse_dejesus_essentiality(text: str) -> dict[str, str]` mapping locus_tag → normalized call in `{"essential","growth-defect","non-essential","growth-advantage","uncertain"}`.

- [ ] **Step 1: failing test** — feed a 4-row fixture (`Rv0667  ES`, `Rv0668  GD`, `Rv0669  NE`, `Rv0670  GA`); assert the dict normalizes ES→essential, GD→growth-defect, NE→non-essential, GA→growth-advantage.
- [ ] **Step 2-4:** parse header + rows (TSV/CSV sniff), pick locus + call columns, normalize via a code map (`ES/ESD→essential`, `GD→growth-defect`, `NE→non-essential`, `GA→growth-advantage`, else `uncertain`). → green.
- [ ] **Step 5: commit** `feat(ingestion): DeJesus 2017 essentiality parser`

---

### Task 4: Enrichment mapper (pure)

**Files:** Create `infrastructure/ingestion/gene_enrichment_mapper.py`; Test.

**Interfaces:** Consumes `GffGeneRecord[]` (Task 2) + `dict[locus,call]` (Task 3). Produces `build_enrichment_records(gff, essentiality, *, assembly="ASM19595v2") -> list[GeneEnrichmentRecord]`.

- [ ] **Step 1: failing test** — given one GFF record (Rv0667, coords, functional_category="Information pathways") + essentiality `{Rv0667: "essential"}`, assert the produced `GeneEnrichmentRecord` has location set, a CONTEXT annotation `functional_category="Information pathways"`, and a VULNERABILITY annotation `essentiality="essential"` with `dataset="DeJesus 2017"`, `condition="in vitro 7H9"`, `evidence="PMID:28096490"`.
- [ ] **Step 2-4:** for each GFF record, emit a `GeneEnrichmentRecord(locus_key=locus_tag, genomic_*=..., assembly=..., annotations=(... CONTEXT functional_category if present ..., ... VULNERABILITY essentiality if locus in dict ...))`. → green.
- [ ] **Step 5: commit** `feat(ingestion): enrichment mapper (location + functional-category + essentiality)`

---

### Task 5: Clients + runner

**Files:** Create `mycobrowser_client.py` (httpx fetch GFF; + a `load_essentiality(path|url)`), `gene_enrichment_runner.py`; Test the runner against an in-memory client + fake `BulkEnrichGenes` (no real network in unit tests; mark any live fetch test as integration/skippable).

**Interfaces:** `GeneEnrichmentRunner(uow, bulk_enrich, gff_client, essentiality_loader).run(organism_id, auth) -> EnrichSummary` — fetch GFF text → `parse_mycobrowser_gff` → load essentiality → `parse_dejesus_essentiality` → `build_enrichment_records` → `BulkEnrichGenes` inside the UoW.

- [ ] **Step 1-4:** test the runner wires parse→map→enrich correctly with a fake client returning fixture text and a fake use case capturing records; assert the summary propagates. Implement the httpx client (timeout, gunzip if `.gz`) and the runner. → green.
- [ ] **Step 5: commit** `feat(ingestion): gene-enrichment client + runner`

---

### Task 6: CLI command + docs

**Files:** Create `scripts/enrich_genes.py` (resolve the H37Rv organism by ncbi_tax_id 83332, build the runner via DI/container, run); add a short **"Enriching genes"** section to the backend README or a docstring with the exact command.

- [ ] **Step 1-3:** implement the script (argparse/typer: `--tax-id 83332` default, `--gff-url`, `--essentiality-file` optional); print the summary. Smoke-test `--help`. Document: `uv run --directory backend python scripts/enrich_genes.py --tax-id 83332`.
- [ ] **Step 4: commit** `feat(ingestion): enrich-genes CLI + docs`

---

### Task 7: Real H37Rv import + verify (live)

- [ ] **Step 1:** Confirm the dev DB has H37Rv genes (`list_by_organism` count > 0 for tax 83332). If 0, stop and report (genes must be imported first).
- [ ] **Step 2:** Run the CLI against the **real** Mycobrowser GFF (location + functional category). Capture the summary (matched / unmatched / locations_set). Investigate if match rate is low (locus-tag casing, `c`-suffix for complement genes, etc.).
- [ ] **Step 3:** Essentiality — if a clean DeJesus table is fetchable, include it; else document the manual `--essentiality-file` path and skip live.
- [ ] **Step 4: verify** a known gene end-to-end: `GET /genes` for `Rv0667`/`rpoB` (or query the repo) shows `genomic_accession="NC_000962.3"`, coords, and (if essentiality ran) a vulnerability annotation. Spot-check the neighborhood endpoint returns ordered neighbors.
- [ ] **Step 5:** Report match rate + a couple of enriched examples. (No code commit unless a matching fix was needed.)

---

## Final verification

- [ ] `uv run --directory backend pytest tests/unit tests/api -q` → green; `uv run --directory backend lint-imports` → passes.
- [ ] Real import summary recorded (matched count, examples). Gene page for an enriched locus now renders the Genomic Context map (+ vulnerability panel if essentiality ran).

## Out of scope / deferred

- Selectivity (human ortholog / OrthoDB) + Robustness (conservation) adapters — schema ready; separate effort.
- Expression (RNA-seq condition) annotations.
- Malaria (PlasmoDB/piggyBac) and cancer (DepMap) adapters — same generic pipeline, different sources.
