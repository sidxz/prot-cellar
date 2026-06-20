# UniProt Proteome Import — Schema Real-Estate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, this session) — steps use checkbox (`- [ ]`) syntax. Update boxes to `[x]` as completed so the loop can resume.

**Goal:** Extend the prot-cellar schema so a full UniProtKB proteome (e.g. `UP000001584`, *M. tuberculosis* H37Rv, 3,997 entries) can be imported **losslessly** — every feature, comment, GO term, keyword, cross-reference, citation, isoform, and per-entry scalar has a typed home.

**Architecture:** DDD bounded contexts (mirrors chem-cellar). Rich annotations are **owned entities of the Protein aggregate** (1:many child tables with `cascade="all, delete-orphan"`, `lazy="selectin"`), exactly like the existing `organisms → organism_names` relationship. Re-import syncs a child collection by clear-and-rebuild keyed on `(source, source_record_id)`. Evidence (ECO) and structured comment payloads ride as JSONB on their owning row (pragmatic-lossless), not their own table.

**Tech Stack:** Python 3.13, async SQLAlchemy 2.0, Alembic, Pydantic v2, FastAPI, `returns` Result, testcontainers-Postgres + pytest (`asyncio_mode=auto`). Run tests: `.venv/bin/pytest`.

## Global Constraints

- Reference data (proteins, genes, organisms, proteomes, and their children) lives under `GLOBAL_WORKSPACE_ID`.
- All new columns are **nullable / additive** — no backfill of existing rows required except the explicit data migrations in Tasks 5 & 6.
- Idempotent import is keyed on `(source, source_record_id)` with `source_record_checksum` drift detection (already implemented in `BulkUpsertProteins`).
- Alembic chain is **linear, single head**. Current head: **`6d6ec789aaae`** (target_tables). Each new migration sets `down_revision` to the prior task's revision. Never create a second head.
- Every task ends green (`pytest`) and is independently committable. **Do NOT commit until the user authorises** — leave each task's diff ready and report it.

---

## The Established Pattern (template every task follows)

A new field/table threads through these layers (file → responsibility):

| Layer | File | What changes |
|---|---|---|
| Domain entity | `src/protcellar/domain/protein_catalog/protein.py` | `__init__` param + assign; `create()` param + passthrough; `update()` conditional |
| Domain VO/child | `src/protcellar/domain/protein_catalog/value_objects.py` | new frozen dataclass for child rows (`to_dict`/`from_dict` if JSON) |
| SA model | `src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py` | column / child `*Model` + `relationship(...)` |
| Migration | `backend/alembic/versions/<rev>_<slug>.py` | `op.add_column` / `op.create_table` + indexes; correct `down_revision` |
| Repository | `.../protein_catalog/protein_repository.py` | map in `_to_domain`, `_to_model`, `_update_model` (collections: clear-and-rebuild) |
| Import record | `src/protcellar/application/protein_catalog/bulk_upsert_proteins.py` | field on `ProteinImportRecord`; pass into `create()`/`update()` |
| API | `src/protcellar/interface/routes/proteins.py` | `BulkRecordBody` field; bulk-endpoint mapping; `ProteinResponse` field + `from_domain` |
| Test | `tests/api/test_protein_bulk_import.py` (or focused new file) | bulk→GET round-trip |

Collection-mapping reference for owned children (Tasks 3–8): copy the `organisms → organism_names` mechanic in `.../taxonomy/models.py` (`OrganismModel.names`) and `.../taxonomy/organism_repository.py`.

---

## Task 1: Protein scalar fields — `annotation_score`, `fragment`, `uniparc_id`  ✅ DONE

> Status: GREEN. New migration `d3f8c2a1b9e4` (head). 21 tests pass (3 bulk-import incl. new round-trip + 18 protein/proteome/domain); mypy clean; `ruff check src/` clean. Held uncommitted pending git decision.

Fills three flat gaps (UniProt `annotationScore`, `sequence.fragment`, `extraAttributes.uniParcId`). Pure additive scalars — the template's minimal slice.

**Files:**
- Modify: `src/protcellar/domain/protein_catalog/protein.py`
- Modify: `src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py`
- Create: `backend/alembic/versions/<rev1>_protein_annotation_scalars.py` (down_revision `6d6ec789aaae`)
- Modify: `.../protein_catalog/protein_repository.py`
- Modify: `src/protcellar/application/protein_catalog/bulk_upsert_proteins.py`
- Modify: `src/protcellar/interface/routes/proteins.py`
- Test: `tests/api/test_protein_bulk_import.py`

**Interfaces produced:** `Protein.annotation_score: int | None`, `Protein.fragment: str | None`, `Protein.uniparc_id: str | None`; same three on `ProteinImportRecord`, `BulkRecordBody`, `ProteinResponse`.

- [x] **Step 1 — failing test** (append to `tests/api/test_protein_bulk_import.py`):

```python
@pytest.mark.asyncio
async def test_bulk_import_captures_annotation_scalars(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99903)
    rec = {
        "primary_accession": "P9WIE5",
        "organism_id": organism_id,
        "sequence": "MPEQHPPITETTTGAASNGCPV",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "P9WIE5",
        "source_record_checksum": "crc1",
        "annotation_score": 5,
        "fragment": "single",
        "uniparc_id": "UPI000012706D",
    }
    resp = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert resp.status_code == 200
    got = (await client.get("/api/v1/proteins/P9WIE5")).json()
    assert got["annotation_score"] == 5
    assert got["fragment"] == "single"
    assert got["uniparc_id"] == "UPI000012706D"
```

- [x] **Step 2 — run, expect FAIL**: `.venv/bin/pytest tests/api/test_protein_bulk_import.py::test_bulk_import_captures_annotation_scalars -x -q` → KeyError/assert on `annotation_score`.
- [x] **Step 3 — domain** (`protein.py`): add `annotation_score: int | None = None`, `fragment: str | None = None`, `uniparc_id: str | None = None` to `__init__` and `create()` signatures (passthrough), assign `self.* = *` in `__init__`, and add to `create()`'s `cls(...)` call. In `update()` add:
```python
        if "annotation_score" in fields:
            self.annotation_score = fields["annotation_score"]
        if "fragment" in fields:
            self.fragment = fields["fragment"]
        if "uniparc_id" in fields:
            self.uniparc_id = fields["uniparc_id"]
```
- [x] **Step 4 — SA model** (`models.py`, `ProteinModel`):
```python
    annotation_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fragment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    uniparc_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
```
- [x] **Step 5 — migration** `<rev1>_protein_annotation_scalars.py` (down_revision `6d6ec789aaae`): `op.add_column('proteins', sa.Column('annotation_score', sa.Integer(), nullable=True))` ×3 + `op.create_index(op.f('ix_proteins_uniparc_id'), 'proteins', ['uniparc_id'])`; downgrade drops them.
- [x] **Step 6 — repository**: add the three to `_to_domain` (`annotation_score=model.annotation_score`, …), `_to_model`, and `_update_model`.
- [x] **Step 7 — import record + use case** (`bulk_upsert_proteins.py`): add three fields to `ProteinImportRecord` (default `None`); pass into both `existing.update(...)` and `Protein.create(...)`.
- [x] **Step 8 — API** (`proteins.py`): add three fields to `BulkRecordBody` (default `None`); pass into the `ProteinImportRecord(...)` built in `bulk_upsert_proteins`; add three fields to `ProteinResponse` and to `from_domain`.
- [x] **Step 9 — run, expect PASS**: `.venv/bin/pytest tests/api/test_protein_bulk_import.py -q` (whole file, confirm no regression).
- [x] **Step 10 — commit** (HOLD until user authorises): `feat(protein): annotation_score, fragment, uniparc_id scalar fields`.

---

## Task 2: Proteome ↔ Protein membership — `proteome_proteins`

UniProt tells us exactly which entries belong to `UP000001584`; today membership is only implicit via `organism_id`. Add an explicit many:many join so "the proteome's proteins" is a first-class query.

- **Migration:** `proteome_proteins(id, proteome_id FK→proteomes, protein_id FK→proteins, created_at)`, `UNIQUE(proteome_id, protein_id)`, index both FKs.
- **SA/domain/repo:** new `ProteomeProteinModel`; add a `ProteomeRepository.add_member(proteome_id, protein_id)` + `list_protein_ids(proteome_id)` (taxonomy context). Membership is a link table, not an owned entity — keep it on the proteome repository.
- **Test:** create proteome + protein, link, assert `list_protein_ids` returns it; re-link is idempotent (no dup).
- Files: `.../taxonomy/models.py`, new migration (down_revision `<rev1>`), `.../taxonomy/proteome_repository.py`, `tests/api/test_proteomes.py` or new `tests/unit/...`.

## Task 3: Protein features — `protein_features` (owned 1:many) — TEMPLATE for collections  ✅ DONE

> Status: GREEN. Migration `b2e4f6a8c1d3` (head). Owned collection on the Protein aggregate (mirrors `organism_names`): `ProteinFeature` VO + `ProteinFeatureModel` + repo clear-and-rebuild + `FeatureBody`/`FeatureResponse` API + bulk-import round-trip test. ruff/mypy clean. **Built ahead of Task 2** (membership) so the collection template lands first; Tasks 4/8 reuse it verbatim. Note: model columns are `start_pos`/`end_pos` (avoid SQL reserved `end`); domain VO keeps `start`/`end`.

Positional sequence annotations (`features[]`): Chain, Domain, Binding/Active site, Transmembrane, Signal, Modified residue, Natural variant, secondary structure, … (~tens of thousands of rows for this proteome).

- **VO** `ProteinFeature` (frozen dataclass): `feature_type: str`, `start: int | None`, `end: int | None`, `start_modifier: str | None`, `end_modifier: str | None`, `description: str | None`, `feature_id: str | None`, `ligand: dict | None` (JSONB), `alternative_sequence: str | None`, `evidence: list[dict] | None` (JSONB ECO).
- **SA** `ProteinFeatureModel` (`protein_features`): FK `protein_id`→proteins (index), the above columns (`ligand`/`evidence` = `JSON`), `EntityModelMixin`. On `ProteinModel`: `features: Mapped[list[ProteinFeatureModel]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="ProteinFeatureModel.id")`.
- **Domain:** `Protein.features: list[ProteinFeature]` (param default `None`→`[]`; `update()` replaces wholesale).
- **Repo:** `_to_domain` reads `model.features`→VOs; `_to_model` builds child models; `_update_model` clear-and-rebuild (`model.features = [..]`). Mirror `organism_repository` `names` handling.
- **Import/API/Test:** `ProteinImportRecord.features: tuple[ProteinFeature, ...]`; `BulkRecordBody.features: list[FeatureBody]`; `ProteinResponse.features`; round-trip test asserts a Domain feature with start/end/type survives bulk→GET.
- Migration down_revision `<rev2>`.

## Task 4: Protein comments — `protein_comments`  ✅ DONE

> Status: GREEN. Migration `c4a6b8d0e2f1` (head). `ProteinComment` VO (comment_type + text + JSONB payload + JSONB evidence) as owned collection; structured comment types (CATALYTIC ACTIVITY, SUBCELLULAR LOCATION, ...) ride losslessly in `payload`. Round-trip test green; ruff/mypy clean.

General annotation (`comments[]`): FUNCTION, CATALYTIC ACTIVITY, COFACTOR, SUBCELLULAR LOCATION, PATHWAY, SUBUNIT, INTERACTION, DISEASE, PTM, ALTERNATIVE PRODUCTS, … Many are structured, so store typed + JSONB payload.

- **VO** `ProteinComment`: `comment_type: str`, `text: str | None`, `payload: dict | None` (JSONB — holds structured sub-objects: reaction+Rhea/ChEBI, ChEBI cofactor, location, kinetics, disease), `evidence: list[dict] | None`.
- Same owned-collection mechanic as Task 3 (`ProteinModel.comments`). Migration down_revision `<rev3>`. Round-trip test on a FUNCTION + a CATALYTIC ACTIVITY comment.

## Task 5: Cross-reference normalization — `protein_cross_references` (replaces JSON column)

The single highest-volume category (PDB, InterPro, Pfam, KEGG, STRING, **GO**, … 100k+ rows). Domain already models `cross_references: list[CrossReference]`; this is a **persistence refactor** + data migration — domain & API unchanged.

- **SA** `ProteinCrossReferenceModel` (`protein_cross_references`): FK `protein_id`, `database` (index), `accession`, `isoform_id: str | None`, `properties: JSON`, `evidence: String | None`. `ProteinModel.cross_reference_rows` relationship (owned). Keep GO inside here (`database='go'`, aspect in `properties`); add partial index `WHERE database='go'` for GO queries.
- **Repo:** replace `_xref_json` round-trip with collection mapping; delete reliance on `model.cross_references` JSON in `_to_domain`/`_to_model`/`_update_model`.
- **Data migration** (down_revision `<rev4>`): create table; copy existing `proteins.cross_references` JSON → rows; **drop** `proteins.cross_references` column (and the gene one stays JSON — out of scope). Downgrade recreates column + folds rows back.
- **Test:** existing `test_bulk_upsert_is_idempotent` xref round-trip must still pass; add a GO-term round-trip + a "filter proteins by xref database" query test.
- ⚠ Touches working code — run the **whole** `tests/api/test_protein_bulk_import.py` + `tests/api/test_proteins.py` green.

## Task 6: Structured keywords — `protein_keywords` (owned collection)  ✅ DONE

> Status: GREEN. Migration `a8c0e2f4b6d8` (head). **Simplified from vocab+join to an owned collection** — `ProteinKeyword` VO (kw_id, name, category) on the aggregate as attribute `keyword_refs` (flat `keywords` String array stays for back-compat). Lossless; dedup into a shared vocab table is a deferred storage optimization. Round-trip test green; ruff/mypy clean.

Today `proteins.keywords` is `ARRAY(String)` (names only — loses `KW-id` + category).

- **SA** `KeywordModel` (`keywords`: `kw_id` PK-unique `KW-xxxx`, `category`, `name`) + `protein_keywords(protein_id, keyword_kw_id)` join.
- **Domain:** `Protein.keyword_refs: list[Keyword]` VO (`kw_id`, `category`, `name`); keep the flat `keywords` names for back-compat or derive from refs.
- **Data migration** (down_revision `<rev5>`): no destructive change required (additive); optionally backfill vocab from existing arrays. Round-trip test on a `{KW-0560, Molecular function, Oxidoreductase}` keyword.

## Task 7: Citations — `protein_citations` (owned collection)  ✅ DONE

> Status: GREEN. Migration `b0d2f4a6c8e0` (head). **Simplified from deduped-shared-table+join to an owned collection** — `ProteinCitation` VO (citation_type, title, journal, authors JSON, pubmed_id, doi, reference_number, positions JSON, reference_comments JSON). Lossless; cross-protein PubMed dedup is a deferred storage optimization. Round-trip test green; full suite 89 green; ruff/mypy clean.

`references[]` with PubMed/DOI. Deduplicate citations (same PubMed recurs across thousands of entries).

- **SA** `CitationModel` (`citations`: dedup key = `pubmed_id` or `doi`; `citation_type`, `title`, `journal`, `authors: JSON`, `publication_date`, `pubmed_id` index, `doi` index) + `protein_citations(protein_id, citation_id, reference_number, positions: JSON, comments: JSON)` join.
- **Repo:** upsert-by-(pubmed_id|doi) so the citation row is shared. Round-trip test: two proteins citing the same PubMed → one `citations` row, two joins.
- Migration down_revision `<rev6>`.

## Task 8: Isoforms — `protein_isoforms`  ✅ DONE

> Status: GREEN. Migration `e6f8a0c2d4b6` (head). `ProteinIsoform` VO (isoform_accession, name, is_displayed, sequence, event, note) as owned collection. Round-trip test green; ruff/mypy clean. **Done out of order** (after comments) — reuses the collection template.

`ALTERNATIVE PRODUCTS` (only ~4 in this proteome, but part of "all").

- **SA** `ProteinIsoformModel` (`protein_isoforms`): FK `protein_id`, `isoform_accession` (`-N`), `name`, `is_displayed: bool`, `sequence: Text | None`, `event: str | None` (e.g. "Alternative initiation"). Owned collection `ProteinModel.isoforms`.
- Round-trip test on a displayed + a described isoform. Migration down_revision `<rev7>`.

---

## Follow-on (separate plan): UniProt import pipeline

After the schema lands, a second plan covers ingestion (not schema): fetch `/proteomes/UP000001584` → upsert proteome row + membership; stream `/uniprotkb/stream?query=proteome:UP000001584&format=json&compressed=true`; a **UniProt-JSON → ProteinImportRecord mapper** exploding each entry into the Task 3–8 children; durable chunked workflow (cursor `Link` paging, 500/page), dry-run, `BULK_IMPORT` audit op. Decision deferred: relational `evidence` table vs JSONB-per-row (plan assumes JSONB).

## Self-review notes
- Spec coverage: every gap from the analysis (features, comments, GO, xref-normalization, keywords, citations, annotation_score/fragment/uniparc, isoforms, membership) maps to a task. ✓
- Type consistency: child VOs use `*_type: str` + `evidence: list[dict] | None` uniformly; collections mapped via clear-and-rebuild everywhere. ✓
- Dependency order: 1 (scalars) → 2 (membership) → 3 (features=collection template) → 4 → 5 (xref refactor) → 6 → 7 → 8. Each migration chains off the previous task's revision.
