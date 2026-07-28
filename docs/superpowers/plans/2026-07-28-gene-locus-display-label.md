# Gene locus-first display label — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gene views lead with the ordered locus tag (`Rv1066`, `PF3D7_0216700`); protein views keep the gene symbol (`rho`). No per-strain config.

**Architecture:** Promote `ordered_locus_names` from the flattened `synonyms[]` blob to a distinct field on the `Gene` aggregate (the importer already parses it — it just stops merging it). A pure `gene_display_label()` resolver picks *first locus → else primary_name*; human genes have no locus, so they fall back to the symbol automatically. Gene-context DTOs expose `display_label`; the protein-context summary keeps `primary_name` as its lead and gains `ordered_locus_names` only for its secondary line.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Alembic / pytest (backend); Next.js / React / ag-grid / orval / vitest / biome (frontend); Postgres 16.

## Global Constraints

- Backend tests: `cd backend && uv run pytest tests/unit -v` (unit), `cd backend && uv run pytest tests/api -v` (API, needs Docker for testcontainers). Lint: `cd backend && uv run ruff check src tests && uv run mypy src`.
- Frontend runs tools via direct binaries (pnpm exec is flaky here): `./node_modules/.bin/vitest run`, `./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/biome check src/`.
- OpenAPI → TS client regen: `make generate-api` (dumps backend OpenAPI to `frontend/openapi.json`, then runs orval).
- `ordered_locus_names` is a `list[str]` on the domain aggregate, `tuple[str, ...]` on `GeneImportRecord`, `ARRAY(String)` nullable in the DB (empty list persists as SQL NULL, matching the `synonyms` `or None` convention).
- The gene-context lead is `display_label`; the protein-context lead stays `primary_name`. Never swap these.
- `ponytail:` markers from the spec must appear in code: first-locus-wins ceiling on `gene_display_label`; "no config; add gene_label_style enum when a locus-bearing organism wants symbol-led genes."

---

### Task 1: Domain — `ordered_locus_names` field + `gene_display_label` resolver

**Files:**
- Modify: `backend/src/protcellar/domain/protein_catalog/gene.py`
- Test: `backend/tests/unit/domain/protein_catalog/test_gene.py`

**Interfaces:**
- Produces: `Gene(..., ordered_locus_names: list[str] | None = None)` attribute `gene.ordered_locus_names: list[str]`; `Gene.create(..., ordered_locus_names=...)`; `gene.update(ordered_locus_names=[...])`; module function `gene_display_label(primary_name: str, ordered_locus_names: list[str]) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/domain/protein_catalog/test_gene.py`:

```python
from protcellar.domain.protein_catalog.gene import Gene, gene_display_label


def test_gene_carries_ordered_locus_names() -> None:
    gene = Gene.create(
        primary_name="rho",
        organism_id=uuid.uuid4(),
        ordered_locus_names=["Rv1297"],
    )
    assert gene.ordered_locus_names == ["Rv1297"]


def test_gene_ordered_locus_names_default_empty() -> None:
    gene = Gene.create(primary_name="TP53", organism_id=uuid.uuid4())
    assert gene.ordered_locus_names == []


def test_gene_update_ordered_locus_names() -> None:
    gene = Gene.create(primary_name="rho", organism_id=uuid.uuid4())
    gene.update(ordered_locus_names=["Rv1297"])
    assert gene.ordered_locus_names == ["Rv1297"]


def test_display_label_prefers_locus() -> None:
    assert gene_display_label("rho", ["Rv1297"]) == "Rv1297"


def test_display_label_falls_back_to_primary_when_no_locus() -> None:
    # Human genes have no ordered locus names -> symbol wins.
    assert gene_display_label("TP53", []) == "TP53"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_gene.py -v`
Expected: FAIL — `ImportError: cannot import name 'gene_display_label'` / `TypeError: create() got an unexpected keyword argument 'ordered_locus_names'`.

- [ ] **Step 3: Add the field to `Gene.__init__`**

In `gene.py`, add the param to `__init__` (after `synonyms`, ~line 25) and assign it (after the `self.synonyms = ...` line ~53):

```python
        synonyms: list[str] | None = None,
        ordered_locus_names: list[str] | None = None,
```
```python
        self.synonyms = synonyms if synonyms is not None else []
        self.ordered_locus_names = (
            ordered_locus_names if ordered_locus_names is not None else []
        )
```

- [ ] **Step 4: Thread it through `create()` and `update()`**

In `create()` (add param after `synonyms`, ~line 77; pass through in the `cls(...)` call ~line 93):

```python
        synonyms: list[str] | None = None,
        ordered_locus_names: list[str] | None = None,
```
```python
            synonyms=synonyms,
            ordered_locus_names=ordered_locus_names,
```

In `update()` (add after the `synonyms` block ~line 128-129):

```python
        if "ordered_locus_names" in fields:
            self.ordered_locus_names = list(fields["ordered_locus_names"] or [])
```

- [ ] **Step 5: Add the module-level resolver**

Add at the end of `gene.py` (module level, not a method — keeps the presentation rule out of the aggregate's behavior):

```python
def gene_display_label(primary_name: str, ordered_locus_names: list[str]) -> str:
    """Gene-context label: the ordered locus tag (Rv1066, PF3D7_0216700) when present,
    else the primary name. Protein-context views keep the symbol (primary_name)."""
    # ponytail: first OLN wins; a multi-strain gene may list Rv#### + MT#### — a
    # strain-aware pick needs a strain->prefix map, defer until a view needs it.
    return ordered_locus_names[0] if ordered_locus_names else primary_name
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_gene.py -v`
Expected: PASS (all new tests green).

- [ ] **Step 7: Commit**

```bash
git add backend/src/protcellar/domain/protein_catalog/gene.py backend/tests/unit/domain/protein_catalog/test_gene.py
git commit -m "feat(gene): ordered_locus_names field + locus-first display_label resolver"
```

---

### Task 2: Importer — extract loci distinctly, stop flattening, fold into checksum

**Files:**
- Modify: `backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py` (add field to `GeneImportRecord`)
- Modify: `backend/src/protcellar/infrastructure/ingestion/uniprot_mapper.py`
- Test: `backend/tests/unit/infrastructure/test_uniprot_mapper.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `GeneImportRecord.ordered_locus_names: tuple[str, ...] = ()`; `map_uniprot_genes` now sets it; `_gene_synonyms` no longer contains ordered-locus names; `_gene_checksum(primary_name, synonyms, ordered_locus_names, ncbi_gene_id)`.

- [ ] **Step 1: Add the field to `GeneImportRecord`**

In `bulk_upsert_genes.py`, add to the dataclass (after `synonyms`, ~line 31):

```python
    synonyms: tuple[str, ...] = ()
    ordered_locus_names: tuple[str, ...] = ()
```

- [ ] **Step 2: Write the failing tests**

In `test_uniprot_mapper.py`, **update** the existing `test_extracts_gene_with_name_and_locus` (the split moves `Rv1908c` out of `synonyms`) and **add** new cases:

```python
def test_extracts_gene_with_name_and_locus() -> None:
    org = uuid.uuid4()
    genes = map_uniprot_genes(
        _ENTRY, organism_id=org, tax_id=83332, source="uniprot", source_release="2026_02"
    )
    assert len(genes) == 1
    g = genes[0]
    assert g.primary_name == "katG"
    assert g.source_record_id == "83332:Rv1908c"  # locus tag is the stable key
    assert "Rv1908c" in g.ordered_locus_names       # now its own field...
    assert "Rv1908c" not in g.synonyms              # ...and no longer flattened into synonyms
    assert g.organism_id == org
    assert g.source == "uniprot"
    assert g.source_record_checksum  # non-empty content hash


def test_locus_only_entry_populates_ordered_locus_names() -> None:
    entry = {"genes": [{"orderedLocusNames": [{"value": "Rv0001"}]}]}
    genes = map_uniprot_genes(entry, organism_id=uuid.uuid4(), tax_id=83332)
    assert genes[0].primary_name == "Rv0001"
    assert genes[0].ordered_locus_names == ("Rv0001",)
    assert genes[0].synonyms == ()


def test_ordered_locus_names_change_checksum() -> None:
    base = {"genes": [{"geneName": {"value": "rho"}}]}
    with_locus = {"genes": [{"geneName": {"value": "rho"}, "orderedLocusNames": [{"value": "Rv1297"}]}]}
    org = uuid.uuid4()
    a = map_uniprot_genes(base, organism_id=org, tax_id=83332)[0]
    b = map_uniprot_genes(with_locus, organism_id=org, tax_id=83332)[0]
    assert a.source_record_checksum != b.source_record_checksum
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && uv run pytest tests/unit/infrastructure/test_uniprot_mapper.py -v`
Expected: FAIL — `AttributeError: 'GeneImportRecord' object has no attribute 'ordered_locus_names'` and the updated assertions failing.

- [ ] **Step 4: Stop flattening loci in `_gene_synonyms`**

In `uniprot_mapper.py`, **delete** the ordered-locus line from `_gene_synonyms` (currently line 310):

```python
    pool.extend(_values(gene.get("synonyms")))
    pool.extend(_values(gene.get("orfNames")))
```
(The `pool.extend(_values(gene.get("orderedLocusNames")))` line is removed. ORF names stay.)

- [ ] **Step 5: Fold loci into the checksum**

Replace `_gene_checksum` (lines 335-337):

```python
def _gene_checksum(
    primary_name: str,
    synonyms: tuple[str, ...],
    ordered_locus_names: tuple[str, ...],
    ncbi_gene_id: str | None,
) -> str:
    basis = "|".join(
        [
            primary_name,
            ",".join(sorted(synonyms)),
            ",".join(sorted(ordered_locus_names)),
            ncbi_gene_id or "",
        ]
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 6: Populate the field in `map_uniprot_genes`**

In `map_uniprot_genes` (the loop body, ~lines 250-266), extract loci and pass both new args:

```python
        ncbi = _ncbi_gene_id(entry)
        synonyms = _gene_synonyms(gene, primary)
        ordered_locus_names = _values(gene.get("orderedLocusNames"))
        out.append(
            GeneImportRecord(
                primary_name=primary,
                organism_id=organism_id,
                source=source,
                source_release=source_release,
                source_record_id=f"{tax_id}:{basis}",
                source_record_checksum=_gene_checksum(
                    primary, synonyms, ordered_locus_names, ncbi
                ),
                synonyms=synonyms,
                ordered_locus_names=ordered_locus_names,
                ncbi_gene_id=ncbi,
            )
        )
```

- [ ] **Step 7: Run to verify it passes**

Run: `cd backend && uv run pytest tests/unit/infrastructure/test_uniprot_mapper.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/infrastructure/ingestion/uniprot_mapper.py backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py backend/tests/unit/infrastructure/test_uniprot_mapper.py
git commit -m "feat(ingestion): extract ordered_locus_names distinctly (stop flattening into synonyms)"
```

---

### Task 3: Persistence + import handler — make the field durable

**Files:**
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py`
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py`
- Modify: `backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py` (`BulkUpsertGenes` handler)
- Create: `backend/alembic/versions/<generated>_add_ordered_locus_names_to_genes.py`
- Test: `backend/tests/unit/application/protein_catalog/test_bulk_upsert_genes.py`

**Interfaces:**
- Consumes: `Gene.ordered_locus_names` (Task 1), `GeneImportRecord.ordered_locus_names` (Task 2).
- Produces: `genes.ordered_locus_names` column persisted round-trip; handler threads the record field onto the aggregate.

- [ ] **Step 1: Write the failing handler test**

In `test_bulk_upsert_genes.py`, extend the `_rec` helper to accept loci and add a test:

```python
def _rec(
    srid: str = "83332:Rv1908c",
    checksum: str = "c1",
    primary: str = "katG",
    ordered_locus_names: tuple[str, ...] = ("Rv1908c",),
) -> GeneImportRecord:
    return GeneImportRecord(
        primary_name=primary,
        organism_id=uuid.uuid4(),
        source="uniprot",
        source_release="2026_02",
        source_record_id=srid,
        source_record_checksum=checksum,
        synonyms=(),
        ordered_locus_names=ordered_locus_names,
    )


@pytest.mark.asyncio
async def test_created_gene_carries_ordered_locus_names() -> None:
    repo = _FakeGeneRepo()
    uc = _uc(repo)
    auth = FakeAuth(role="admin")
    await uc(BulkUpsertGenesCommand(records=(_rec(),)), auth=auth)
    saved = repo.by_srid[("uniprot", "83332:Rv1908c")]
    assert saved.ordered_locus_names == ["Rv1908c"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/unit/application/protein_catalog/test_bulk_upsert_genes.py -v`
Expected: FAIL — saved gene's `ordered_locus_names == []` (handler doesn't thread it yet).

- [ ] **Step 3: Thread the field through the handler**

In `bulk_upsert_genes.py`, add to `update_fields` (~line 72) and to `Gene.create(...)` (~line 87):

```python
                        update_fields: dict[str, Any] = {
                            "primary_name": rec.primary_name,
                            "synonyms": list(rec.synonyms),
                            "ordered_locus_names": list(rec.ordered_locus_names),
                            "ncbi_gene_id": rec.ncbi_gene_id,
                            "ensembl_gene_id": rec.ensembl_gene_id,
                            "cross_references": list(rec.cross_references),
                        }
```
```python
                        gene = Gene.create(
                            primary_name=rec.primary_name,
                            organism_id=rec.organism_id,
                            strain_id=rec.strain_id,
                            synonyms=list(rec.synonyms),
                            ordered_locus_names=list(rec.ordered_locus_names),
                            ncbi_gene_id=rec.ncbi_gene_id,
                            ensembl_gene_id=rec.ensembl_gene_id,
                            cross_references=list(rec.cross_references),
                        )
```

- [ ] **Step 4: Run to verify the handler test passes**

Run: `cd backend && uv run pytest tests/unit/application/protein_catalog/test_bulk_upsert_genes.py -v`
Expected: PASS.

- [ ] **Step 5: Add the DB column**

In `models.py` `GeneModel`, add after the `synonyms` column (~line 33):

```python
    synonyms: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    ordered_locus_names: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
```

- [ ] **Step 6: Map the field both directions**

In `gene_repository.py`:

`_to_domain` (after `synonyms=...`, ~line 35):
```python
            synonyms=list(model.synonyms) if model.synonyms else [],
            ordered_locus_names=list(model.ordered_locus_names) if model.ordered_locus_names else [],
```
`_to_model` (after `synonyms=...`, ~line 63):
```python
            synonyms=aggregate.synonyms or None,
            ordered_locus_names=aggregate.ordered_locus_names or None,
```
`_update_model` (after `model.synonyms = ...`, ~line 86):
```python
        model.synonyms = aggregate.synonyms or None
        model.ordered_locus_names = aggregate.ordered_locus_names or None
```

- [ ] **Step 7: Create the Alembic migration**

Generate a stamped, correctly-chained revision file, then fill in the ops:

Run: `cd backend && uv run alembic revision -m "add ordered_locus_names to genes"`

Edit the generated file's `upgrade()`/`downgrade()`:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.add_column(
        "genes",
        sa.Column("ordered_locus_names", postgresql.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("genes", "ordered_locus_names")
```

- [ ] **Step 8: Apply the migration + typecheck**

Run: `cd backend && uv run alembic upgrade head && uv run mypy src`
Expected: migration applies cleanly; mypy passes.

- [ ] **Step 9: Commit**

```bash
git add backend/src/protcellar/infrastructure/persistence backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py backend/alembic/versions backend/tests/unit/application/protein_catalog/test_bulk_upsert_genes.py
git commit -m "feat(gene): persist ordered_locus_names (column + mapper + migration + import handler)"
```

---

### Task 4: Read DTOs — expose `display_label` + `ordered_locus_names`

**Files:**
- Modify: `backend/src/protcellar/interface/routes/genes.py` (`GeneResponse`, route `GeneNeighborSummary`, neighborhood endpoint)
- Modify: `backend/src/protcellar/interface/routes/proteins.py` (`GeneSummaryResponse`)
- Modify: `backend/src/protcellar/application/protein_catalog/get_gene_neighborhood.py` (app `GeneNeighborSummary` + handler)
- Test: `backend/tests/api/test_genes.py`

**Interfaces:**
- Consumes: `gene_display_label` (Task 1), `Gene.ordered_locus_names` (Task 1).
- Produces: `GeneResponse.display_label` + `.ordered_locus_names`; `GeneSummaryResponse.ordered_locus_names`; neighbor `.display_label`.

- [ ] **Step 1: Write the failing API test**

In `tests/api/test_genes.py`, add (uses the existing `_seed_gene` helper + `client`/`database_url` fixtures):

```python
@pytest.mark.asyncio
async def test_gene_list_and_detail_lead_with_locus(client: AsyncClient, database_url: str) -> None:
    gene = Gene.create(
        primary_name="rho",
        organism_id=uuid.uuid4(),
        synonyms=["MTCY373.17"],
        ordered_locus_names=["Rv1297"],
    )
    await _seed_gene(database_url, gene)

    detail = await client.get(f"/api/v1/genes/{gene.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["display_label"] == "Rv1297"          # gene context leads with the locus
    assert body["ordered_locus_names"] == ["Rv1297"]
    assert body["primary_name"] == "rho"               # symbol still present

    listed = await client.get("/api/v1/genes", params={"name": "rho"})
    item = next(g for g in listed.json()["items"] if g["id"] == str(gene.id))
    assert item["display_label"] == "Rv1297"


@pytest.mark.asyncio
async def test_human_gene_falls_back_to_symbol(client: AsyncClient, database_url: str) -> None:
    gene = Gene.create(primary_name="TP53", organism_id=uuid.uuid4(), synonyms=["P53"])
    await _seed_gene(database_url, gene)
    detail = await client.get(f"/api/v1/genes/{gene.id}")
    assert detail.json()["display_label"] == "TP53"    # no locus -> symbol wins
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_genes.py -v -k "locus or fallback_to_symbol"`
Expected: FAIL — `KeyError: 'display_label'` (field not in response).

- [ ] **Step 3: Extend `GeneResponse`**

In `genes.py`, import the resolver (top of file with the other domain imports):

```python
from protcellar.domain.protein_catalog.gene import Gene, gene_display_label
```

Add the fields to `GeneResponse` (after `synonyms`, ~line 85):

```python
    synonyms: list[str]
    ordered_locus_names: list[str]
    display_label: str
```

Set them in `from_domain` (in the `cls(...)`, after `synonyms=g.synonyms`, ~line 118):

```python
            synonyms=g.synonyms,
            ordered_locus_names=g.ordered_locus_names,
            display_label=gene_display_label(g.primary_name, g.ordered_locus_names),
```

- [ ] **Step 4: Extend the protein-embedded `GeneSummaryResponse`**

In `proteins.py` (~lines 159-168) add `ordered_locus_names` (lead stays `primary_name`):

```python
class GeneSummaryResponse(BaseModel):
    """Lightweight gene fields embedded in the protein list for at-a-glance display."""

    id: uuid.UUID
    primary_name: str
    synonyms: list[str]
    ordered_locus_names: list[str]

    @classmethod
    def from_domain(cls, g: Gene) -> GeneSummaryResponse:
        return cls(
            id=g.id,
            primary_name=g.primary_name,
            synonyms=list(g.synonyms),
            ordered_locus_names=list(g.ordered_locus_names),
        )
```

- [ ] **Step 5: Add `display_label` to the gene neighborhood**

In `get_gene_neighborhood.py`, import the resolver and add the field to the app `GeneNeighborSummary` (~lines 48-55):

```python
from protcellar.domain.protein_catalog.gene import gene_display_label
```
```python
@dataclass(frozen=True, kw_only=True)
class GeneNeighborSummary:
    id: uuid.UUID
    primary_name: str
    display_label: str
    genomic_start: int | None
    genomic_end: int | None
    genomic_strand: str | None
    essentiality: str | None
```

In the handler construction (~lines 101-110):

```python
                summaries.append(
                    GeneNeighborSummary(
                        id=n.id,
                        primary_name=n.primary_name,
                        display_label=gene_display_label(n.primary_name, n.ordered_locus_names),
                        genomic_start=n.genomic_start,
                        genomic_end=n.genomic_end,
                        genomic_strand=n.genomic_strand,
                        essentiality=_consensus_essentiality(records),
                    )
                )
```

In `genes.py`, the route `GeneNeighborSummary` (~lines 171-177) and its construction (~line 313):

```python
class GeneNeighborSummary(BaseModel):
    id: uuid.UUID
    primary_name: str
    display_label: str
    genomic_start: int | None = None
    genomic_end: int | None = None
    genomic_strand: str | None = None
    essentiality: str | None = None
```
```python
            GeneNeighborSummary(
                id=n.id,
                primary_name=n.primary_name,
                display_label=n.display_label,
                genomic_start=n.genomic_start,
                genomic_end=n.genomic_end,
                genomic_strand=n.genomic_strand,
                essentiality=n.essentiality,
            )
```

- [ ] **Step 6: Run to verify it passes + typecheck**

Run: `cd backend && uv run pytest tests/api/test_genes.py -v -k "locus or fallback_to_symbol" && uv run mypy src`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/protcellar/interface/routes/genes.py backend/src/protcellar/interface/routes/proteins.py backend/src/protcellar/application/protein_catalog/get_gene_neighborhood.py backend/tests/api/test_genes.py
git commit -m "feat(api): expose gene display_label + ordered_locus_names on read DTOs"
```

---

### Task 5: Frontend — regen client + lead gene views with the locus

**Files:**
- Regen: `frontend/openapi.json`, `frontend/src/shared/lib/api/model/*` (via `make generate-api`)
- Create: `frontend/src/features/protein-catalog/lib/gene-label.ts`, `frontend/src/features/protein-catalog/lib/gene-label.test.ts`
- Modify: `frontend/src/features/protein-catalog/components/gene-columns.tsx`
- Modify: `frontend/src/features/protein-catalog/components/gene-detail.tsx`
- Modify: `frontend/src/features/protein-catalog/components/protein-columns.tsx`
- Modify: `frontend/src/shared/components/common/gene-ref.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/genomic-context-section.tsx`

**Interfaces:**
- Consumes: regenerated `GeneResponse` (now has `display_label`, `ordered_locus_names`), `GeneSummaryResponse` (now has `ordered_locus_names`), `GeneNeighborSummary` (now has `display_label`).
- Produces: `secondaryNames(names, lead)` helper; gene views leading with `display_label`.

- [ ] **Step 1: Regenerate the API client** (backend running / OpenAPI dumpable)

Run: `make generate-api`
Expected: `frontend/src/shared/lib/api/model/geneResponse.ts` now includes `ordered_locus_names: string[]` and `display_label: string`; `geneSummaryResponse.ts` includes `ordered_locus_names: string[]`.

- [ ] **Step 2: Write the failing helper test**

Create `frontend/src/features/protein-catalog/lib/gene-label.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { secondaryNames } from "./gene-label";

describe("secondaryNames", () => {
  it("drops the lead and dedupes", () => {
    // protein context: lead = symbol, secondary = loci + synonyms
    expect(secondaryNames(["Rv1297", "MTCY373.17"], "rho")).toEqual(["Rv1297", "MTCY373.17"]);
  });
  it("removes the lead when it appears in the list", () => {
    // gene context: lead = locus, secondary includes the symbol
    expect(secondaryNames(["rho", "Rv1297", "MTCY373.17"], "Rv1297")).toEqual(["rho", "MTCY373.17"]);
  });
  it("filters empties and duplicates", () => {
    expect(secondaryNames(["rho", "rho", "", "MTCY"], "Rv1")).toEqual(["rho", "MTCY"]);
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/protein-catalog/lib/gene-label.test.ts`
Expected: FAIL — cannot find module `./gene-label`.

- [ ] **Step 4: Write the helper**

Create `frontend/src/features/protein-catalog/lib/gene-label.ts`:

```ts
/** Names to show under a gene's lead label, minus the lead itself, deduped. */
export function secondaryNames(names: (string | null | undefined)[], lead: string): string[] {
  const seen = new Set<string>([lead]);
  const out: string[] = [];
  for (const n of names) {
    if (n && !seen.has(n)) {
      seen.add(n);
      out.push(n);
    }
  }
  return out;
}
```

- [ ] **Step 5: Run to verify the helper passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/protein-catalog/lib/gene-label.test.ts`
Expected: PASS.

- [ ] **Step 6: Gene list — lead with `display_label`, keep the symbol in the secondary**

In `gene-columns.tsx`, change the "Gene Name" column `field` and rewrite `SynonymsCell` to compose symbol + loci + synonyms minus the lead:

```tsx
  {
    headerName: "Gene Name",
    field: "display_label",
    width: 140,
    cellRenderer: PrimaryNameCell,
  },
```

Rewrite `SynonymsCell` (import the helper at top: `import { secondaryNames } from "../lib/gene-label";`):

```tsx
function SynonymsCell({ data }: ICellRendererParams<Gene>) {
  if (!data) return <span>—</span>;
  const rest = secondaryNames(
    [data.primary_name, ...(data.ordered_locus_names ?? []), ...(data.synonyms ?? [])],
    data.display_label,
  );
  return rest.length > 0 ? (
    <span className="text-muted-foreground">{rest.join(", ")}</span>
  ) : (
    <span>—</span>
  );
}
```
(Keep the `field: "synonyms"` on the Synonyms column def, or drop it — `SynonymsCell` now reads from `data`. Leave the def otherwise unchanged.)

- [ ] **Step 7: Gene detail — lead with `display_label`, show the symbol as subtitle**

In `gene-detail.tsx`, breadcrumb (~line 198):

```tsx
  useBreadcrumbOverride(geneId, data?.display_label ?? "");
```

Header (~lines 227-235) — h1 becomes `display_label`; add the symbol beneath when it differs:

```tsx
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {data.display_label}
          </h1>
          <Badge variant="default">Gene</Badge>
        </div>
        {data.display_label !== data.primary_name && (
          <p className="text-sm text-muted-foreground">{data.primary_name}</p>
        )}
      </header>
```

- [ ] **Step 8: Gene ref + genomic context — use `display_label`**

`gene-ref.tsx` (~line 37): `{data.primary_name}` → `{data.display_label}`.

`genomic-context-section.tsx` (~line 130): `name: n.primary_name,` → `name: n.display_label,`.

- [ ] **Step 9: Protein list — keep symbol lead, add loci to the secondary line**

In `protein-columns.tsx` `IdentityCell`, replace the `synonyms` computation (~line 23) so the locus survives the split (import the helper: `import { secondaryNames } from "../lib/gene-label";`):

```tsx
  const gene = data.gene;
  const synonyms = gene
    ? secondaryNames([...(gene.ordered_locus_names ?? []), ...(gene.synonyms ?? [])], gene.primary_name)
    : [];
```
(The rest of `IdentityCell` is unchanged — it still leads with `gene.primary_name` and renders `synonyms.join(", ")`.)

- [ ] **Step 10: Typecheck, lint, test**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/biome check src/ && ./node_modules/.bin/vitest run`
Expected: all green.

- [ ] **Step 11: Commit**

```bash
git add frontend/openapi.json frontend/src/shared/lib/api frontend/src/features/protein-catalog/lib/gene-label.ts frontend/src/features/protein-catalog/lib/gene-label.test.ts frontend/src/features/protein-catalog/components/gene-columns.tsx frontend/src/features/protein-catalog/components/gene-detail.tsx frontend/src/features/protein-catalog/components/protein-columns.tsx frontend/src/shared/components/common/gene-ref.tsx frontend/src/features/protein-catalog/components/sections/genomic-context-section.tsx
git commit -m "feat(frontend): gene views lead with the ordered locus tag"
```

---

### Task 6: Backfill — re-import locus-bearing proteomes

**Files:** none (data operation). Requires Postgres up and the migration from Task 3 applied.

**Interfaces:** Consumes the importer from Task 2 + persistence from Task 3.

- [ ] **Step 1: Confirm which proteomes carry loci**

Human genes have no ordered locus names, so **skip human** (re-importing 147k proteins for zero display delta). Confirm the two locus-bearing proteome IDs that are already loaded:

Run: `docker exec -e PGPASSWORD=protcellar prot-cellar-postgres-1 psql -U protcellar -d protcellar -tAc "select accession, name from proteomes order by name;"`
Expected: an *M. tuberculosis* H37Rv proteome (`UP000001584`) and a *P. falciparum* proteome. Note the exact accessions.

- [ ] **Step 2: Re-import M. tuberculosis H37Rv**

Run: `cd backend && uv run python -m protcellar.scripts.import_proteome UP000001584 --force`
Expected: genes report as `updated` (checksums changed by the Task 2 split), no errors.

- [ ] **Step 3: Re-import P. falciparum**

Run: `cd backend && uv run python -m protcellar.scripts.import_proteome <PF_PROTEOME_ID> --force`
(Use the *P. falciparum* accession from Step 1, e.g. `UP000001450` for 3D7.)

- [ ] **Step 4: Verify the backfill**

Run:
```bash
docker exec -e PGPASSWORD=protcellar prot-cellar-postgres-1 psql -U protcellar -d protcellar -tAc "
select o.scientific_name,
       count(*) filter (where g.ordered_locus_names is not null) as with_locus,
       count(*) as total
from genes g join organisms o on o.id = g.organism_id
group by 1 order by 1;"
```
Expected: TB and *P. falciparum* rows have `with_locus` ≈ their totals; *H. sapiens* `with_locus` = 0.

Spot-check the reference gene:
```bash
docker exec -e PGPASSWORD=protcellar prot-cellar-postgres-1 psql -U protcellar -d protcellar -tAc "
select primary_name, ordered_locus_names, synonyms from genes where primary_name = 'rho' limit 5;"
```
Expected: `rho` has `ordered_locus_names = {Rv1297}` and `Rv1297` no longer in `synonyms`.

- [ ] **Step 5: Manual smoke in the app**

Open `/genes` filtered to H37Rv → rows lead with `Rv####`, symbol shown as secondary. Open `/proteins` search `rho` → still leads with `rho`, secondary line still shows `Rv1297, MTCY373.17`. No commit (data-only).

---

## Self-Review

**Spec coverage:**
- Universal locus-first ladder, no config → Task 1 (`gene_display_label`) + Non-goal preserved via ponytail comment (Global Constraints). ✓
- Split `ordered_locus_names` distinct field (domain→model→migration→importer→record→handler→DTOs) → Tasks 1–4. ✓
- Protein secondary keeps the locus after the split → Task 5 Step 9. ✓
- Gene neighborhood display_label → Task 4 Step 5, consumed Task 5 Step 8. ✓
- Backfill re-import TB + Pf, skip human → Task 6. ✓
- Checksum includes loci (change detection) → Task 2 Step 5. ✓
- Frontend leads gene views with locus, keeps symbol visible → Task 5 Steps 6–9. ✓

**Placeholder scan:** `<PF_PROTEOME_ID>` in Task 6 Step 3 and `<generated>` migration filename are intentional runtime values resolved in Step 1 / by `alembic revision`; every code step has concrete code. No TODO/TBD in logic.

**Type consistency:** `gene_display_label(primary_name: str, ordered_locus_names: list[str]) -> str` used identically in Tasks 1, 4. `ordered_locus_names`: `list[str]` (domain/DTO), `tuple[str, ...]` (import record) — consistent with the `synonyms` precedent. `secondaryNames(names, lead)` signature identical in test + helper + both call sites. Gene-context lead = `display_label`, protein-context lead = `primary_name` throughout.
