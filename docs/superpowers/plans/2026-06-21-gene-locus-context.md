# Gene Locus & Evolutionary Context — Implementation Plan (Display Vertical)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the gene detail page with first-class genomic location, a genomic-neighborhood map, and generic axis-typed annotations (vulnerability/essentiality first) — all data-driven and conditionally rendered.

**Architecture:** Add singular genomic-location fields + a generic, provenance-stamped `GeneAnnotation` list to the `Gene` aggregate (mirroring the existing `CrossReference` value-object pattern). Persist location as indexed scalar columns and annotations as a JSON column. Expose them on `GeneResponse`, allow setting them via create/update (the v1 enrichment path), and add a derived neighborhood endpoint. The frontend renders new conditional sections matching the protein page's section conventions.

**Tech Stack:** Python 3.12 / SQLAlchemy / Alembic / FastAPI / Pydantic / pytest (backend); Next.js / React / TypeScript / orval / vitest / @testing-library/react (frontend).

## Global Constraints

- Genes are **global reference data** (`workspace_id == GLOBAL_WORKSPACE_ID`); never workspace-scope them.
- New domain fields are **value objects / frozen dataclasses**, kw-only, mirroring `domain/shared/cross_reference.py`.
- All new persisted fields are **nullable** (existing rows have no data).
- All new frontend sections **return `null` when their data is empty** (no empty Card).
- Backend tests: `uv run --directory backend pytest <path> -q`. Frontend tests/tsc/biome via `./node_modules/.bin/<tool>` from `frontend/`.
- Commit per task. Conventional-commit messages, scope `genes`. End commit bodies with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.
- **No protein-level data** on the gene (no GO/structure/function); **no druggability score** (verdict belongs to the future target page).

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `backend/src/protcellar/domain/protein_catalog/gene_annotation.py` | `GeneAnnotationAxis` enum + `GeneAnnotation` value object | Create |
| `backend/src/protcellar/domain/protein_catalog/gene.py` | location fields + `annotations` + `length_bp` on `Gene` | Modify |
| `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py` | `GeneModel` columns + composite index | Modify |
| `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/_annotation_json.py` | annotations ↔ JSON helpers | Create |
| `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py` | map new fields + `find_genomic_neighbors` | Modify |
| `backend/src/protcellar/domain/protein_catalog/repository.py` | `GeneRepository.find_genomic_neighbors` signature | Modify |
| `backend/alembic/versions/<rev>_gene_locus_context.py` | migration | Create |
| `backend/src/protcellar/interface/routes/genes.py` | response/body fields + neighborhood route | Modify |
| `frontend/src/features/protein-catalog/components/sections/genomic-context-section.tsx` | location row + neighborhood map | Create |
| `frontend/src/features/protein-catalog/components/sections/axis-annotations-section.tsx` | generic axis panel (vulnerability first) | Create |
| `frontend/src/features/protein-catalog/hooks/use-genes.ts` | `useGeneNeighborhood` wrapper | Modify |
| `frontend/src/features/protein-catalog/components/gene-detail.tsx` | wire new sections | Modify |

---

## Phase 1 — Domain foundation (clean files)

### Task 1: `GeneAnnotation` value object + axis enum

**Files:**
- Create: `backend/src/protcellar/domain/protein_catalog/gene_annotation.py`
- Test: `backend/tests/unit/domain/protein_catalog/test_gene_annotation.py`

**Interfaces:**
- Produces: `GeneAnnotationAxis(StrEnum)` with members `VULNERABILITY, SELECTIVITY, ROBUSTNESS, CONTEXT, EXPRESSION`; `GeneAnnotation` frozen dataclass (kw_only) with fields `axis: GeneAnnotationAxis`, `key: str`, `value: str`, `value_type: str = "categorical"`, `dataset: str | None = None`, `condition: str | None = None`, `evidence: str | None = None`, `source: str | None = None`, `source_url: str | None = None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/domain/protein_catalog/test_gene_annotation.py
import pytest
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.domain.shared.errors import ValidationError


def test_create_vulnerability_annotation() -> None:
    a = GeneAnnotation(
        axis=GeneAnnotationAxis.VULNERABILITY,
        key="essentiality",
        value="essential",
        dataset="DeJesus 2017",
        condition="in vitro 7H9",
        evidence="PMID:28096490",
    )
    assert a.axis is GeneAnnotationAxis.VULNERABILITY
    assert a.value == "essential"
    assert a.value_type == "categorical"  # default


def test_axis_is_string_enum() -> None:
    assert GeneAnnotationAxis.VULNERABILITY == "vulnerability"


def test_key_and_value_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="  ", value="x")
    with pytest.raises(ValidationError):
        GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="functional_category", value="")


def test_is_frozen() -> None:
    a = GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="functional_category", value="Cell wall")
    with pytest.raises(Exception):
        a.value = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/unit/domain/protein_catalog/test_gene_annotation.py -q`
Expected: FAIL (module `gene_annotation` not found).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/protcellar/domain/protein_catalog/gene_annotation.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protcellar.domain.shared.errors import ValidationError


class GeneAnnotationAxis(StrEnum):
    """The drug-discovery question a gene annotation speaks to.

    Universal across diseases; only the datasets that fill each axis differ.
    """

    VULNERABILITY = "vulnerability"  # does losing it hurt? (essentiality/dependency)
    SELECTIVITY = "selectivity"      # will hitting it hurt the patient? (host ortholog)
    ROBUSTNESS = "robustness"        # holds across the treated population? (conservation)
    CONTEXT = "context"              # where/when does it live? (functional category, operon)
    EXPRESSION = "expression"        # condition/stage expression


@dataclass(frozen=True, kw_only=True)
class GeneAnnotation:
    """A provenance-stamped fact about a gene locus, grouped by axis.

    Generic by design: `value` is always a display string, with `value_type`
    as a render hint, so categorical/continuous/boolean facts share one shape.
    """

    axis: GeneAnnotationAxis
    key: str
    value: str
    value_type: str = "categorical"  # "categorical" | "continuous" | "boolean" | "text"
    dataset: str | None = None
    condition: str | None = None
    evidence: str | None = None
    source: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValidationError("GeneAnnotation.key must not be empty")
        if self.value is None or str(self.value).strip() == "":
            raise ValidationError("GeneAnnotation.value must not be empty")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend pytest tests/unit/domain/protein_catalog/test_gene_annotation.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/protein_catalog/gene_annotation.py backend/tests/unit/domain/protein_catalog/test_gene_annotation.py
git commit -m "feat(genes): GeneAnnotation value object + axis enum"
```

---

### Task 2: Genomic location + annotations on the `Gene` entity

**Files:**
- Modify: `backend/src/protcellar/domain/protein_catalog/gene.py`
- Test: `backend/tests/unit/domain/protein_catalog/test_gene.py` (extend)

**Interfaces:**
- Consumes: `GeneAnnotation` (Task 1).
- Produces: `Gene.__init__`/`Gene.create` accept `genomic_accession: str | None = None`, `genomic_start: int | None = None`, `genomic_end: int | None = None`, `genomic_strand: str | None = None`, `assembly: str | None = None`, `annotations: list[GeneAnnotation] | None = None`. New read-only property `Gene.length_bp -> int | None`. `Gene.update()` accepts the same keys plus `annotations`.

- [ ] **Step 1: Write the failing test** (append to existing `test_gene.py`)

```python
def test_gene_holds_genomic_location_and_length() -> None:
    g = Gene.create(
        primary_name="rpoB",
        organism_id=uuid.uuid4(),
        genomic_accession="NC_000962.3",
        genomic_start=759807,
        genomic_end=763325,
        genomic_strand="+",
        assembly="ASM19595v2",
    )
    assert g.genomic_accession == "NC_000962.3"
    assert g.genomic_strand == "+"
    assert g.length_bp == 763325 - 759807 + 1


def test_gene_length_bp_none_when_coords_missing() -> None:
    g = Gene.create(primary_name="x", organism_id=uuid.uuid4())
    assert g.length_bp is None


def test_gene_holds_annotations_and_update_replaces_them() -> None:
    from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis

    g = Gene.create(primary_name="katG", organism_id=uuid.uuid4())
    assert g.annotations == []
    ann = GeneAnnotation(axis=GeneAnnotationAxis.VULNERABILITY, key="essentiality", value="non-essential")
    g.update(annotations=[ann])
    assert g.annotations == [ann]
    g.update(genomic_strand="-")
    assert g.genomic_strand == "-"
    assert g.annotations == [ann]  # untouched keys preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/unit/domain/protein_catalog/test_gene.py -q`
Expected: FAIL (`Gene.create()` got an unexpected keyword argument `genomic_accession`).

- [ ] **Step 3: Write minimal implementation**

In `gene.py`: add the parameters to `__init__` (after `cross_references`), assign them; add the same kwargs to the `create()` classmethod and forward them; add `length_bp` property; extend `update()`.

```python
# __init__ additions (assignments)
self.genomic_accession = genomic_accession
self.genomic_start = genomic_start
self.genomic_end = genomic_end
self.genomic_strand = genomic_strand
self.assembly = assembly
self.annotations = annotations if annotations is not None else []

# new property
@property
def length_bp(self) -> int | None:
    if self.genomic_start is None or self.genomic_end is None:
        return None
    return self.genomic_end - self.genomic_start + 1

# update() additions (inside the existing method, same style as other fields)
for _loc in ("genomic_accession", "genomic_start", "genomic_end", "genomic_strand", "assembly"):
    if _loc in fields:
        setattr(self, _loc, fields[_loc])
if "annotations" in fields:
    self.annotations = list(fields["annotations"] or [])
```

Add the kwargs to `create()`’s signature and pass them through to `cls(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend pytest tests/unit/domain/protein_catalog/test_gene.py -q`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/protein_catalog/gene.py backend/tests/unit/domain/protein_catalog/test_gene.py
git commit -m "feat(genes): genomic location + annotations on Gene aggregate"
```

---

## Phase 2 — Persistence (touches gene_repository.py — now clean)

### Task 3: `GeneModel` columns + migration

**Files:**
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py`
- Create: `backend/alembic/versions/<rev>_gene_locus_context.py`

- [ ] **Step 1: Add columns to `GeneModel`** (after `cross_references`)

```python
genomic_accession: Mapped[str | None] = mapped_column(String(64), nullable=True)
genomic_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
genomic_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
genomic_strand: Mapped[str | None] = mapped_column(String(1), nullable=True)
assembly: Mapped[str | None] = mapped_column(String(64), nullable=True)
annotations: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)

__table_args__ = (
    Index("ix_genes_locus", "organism_id", "genomic_accession", "genomic_start"),
)
```

Ensure `Integer` and `Index` are imported from `sqlalchemy`.

- [ ] **Step 2: Generate an empty migration (correct down_revision, DB-independent)**

Run: `uv run --directory backend alembic revision -m "gene_locus_context"`
This creates `backend/alembic/versions/<rev>_gene_locus_context.py` with `down_revision` pointing at the current head.

- [ ] **Step 3: Fill the migration body**

```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column("genes", sa.Column("genomic_accession", sa.String(length=64), nullable=True))
    op.add_column("genes", sa.Column("genomic_start", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("genomic_end", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("genomic_strand", sa.String(length=1), nullable=True))
    op.add_column("genes", sa.Column("assembly", sa.String(length=64), nullable=True))
    op.add_column("genes", sa.Column("annotations", sa.JSON(), nullable=True))
    op.create_index("ix_genes_locus", "genes", ["organism_id", "genomic_accession", "genomic_start"])


def downgrade() -> None:
    op.drop_index("ix_genes_locus", table_name="genes")
    for col in ("annotations", "assembly", "genomic_strand", "genomic_end", "genomic_start", "genomic_accession"):
        op.drop_column("genes", col)
```

- [ ] **Step 4: Apply + verify it round-trips**

Run: `uv run --directory backend alembic upgrade head && uv run --directory backend alembic downgrade -1 && uv run --directory backend alembic upgrade head`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py backend/alembic/versions/
git commit -m "feat(genes): persist genomic location + annotations columns"
```

---

### Task 4: Repository mapping for the new fields

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/_annotation_json.py`
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py`
- Test: `backend/tests/unit/infrastructure/test_annotation_json.py`

**Interfaces:**
- Produces: `annotations_to_json(list[GeneAnnotation]) -> list[dict]`, `annotations_from_json(list[dict] | None) -> list[GeneAnnotation]`. Repository `_to_model`/`_to_domain`/`_update_model` round-trip all location fields + annotations.

- [ ] **Step 1: Write the failing test** (helper round-trip)

```python
# backend/tests/unit/infrastructure/test_annotation_json.py
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._annotation_json import (
    annotations_from_json,
    annotations_to_json,
)


def test_round_trip() -> None:
    anns = [
        GeneAnnotation(
            axis=GeneAnnotationAxis.VULNERABILITY, key="essentiality", value="essential",
            dataset="DeJesus 2017", condition="in vitro 7H9", evidence="PMID:28096490",
        )
    ]
    restored = annotations_from_json(annotations_to_json(anns))
    assert restored == anns


def test_from_json_handles_none() -> None:
    assert annotations_from_json(None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_annotation_json.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement the helper**

```python
# _annotation_json.py
from __future__ import annotations

from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis


def annotations_to_json(annotations: list[GeneAnnotation]) -> list[dict[str, object]]:
    return [
        {
            "axis": a.axis.value, "key": a.key, "value": a.value, "value_type": a.value_type,
            "dataset": a.dataset, "condition": a.condition, "evidence": a.evidence,
            "source": a.source, "source_url": a.source_url,
        }
        for a in annotations
    ]


def annotations_from_json(data: list[dict[str, object]] | None) -> list[GeneAnnotation]:
    if not data:
        return []
    return [
        GeneAnnotation(
            axis=GeneAnnotationAxis(str(d["axis"])), key=str(d["key"]), value=str(d["value"]),
            value_type=str(d.get("value_type") or "categorical"),
            dataset=_opt(d.get("dataset")), condition=_opt(d.get("condition")),
            evidence=_opt(d.get("evidence")), source=_opt(d.get("source")),
            source_url=_opt(d.get("source_url")),
        )
        for d in data
    ]


def _opt(v: object) -> str | None:
    return str(v) if v is not None else None
```

- [ ] **Step 4: Wire the repository** — in `gene_repository.py`, in `_to_model` set the six new columns (`genomic_accession`, `genomic_start`, `genomic_end`, `genomic_strand`, `assembly`, `annotations=annotations_to_json(aggregate.annotations) or None`); in `_to_domain` read them back (`annotations=annotations_from_json(model.annotations)`); in `_update_model` copy the same six. Import the helpers.

- [ ] **Step 5: Run tests**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_annotation_json.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/_annotation_json.py backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py backend/tests/unit/infrastructure/test_annotation_json.py
git commit -m "feat(genes): map genomic location + annotations in gene repository"
```

---

### Task 5: `find_genomic_neighbors` repository query

**Files:**
- Modify: `backend/src/protcellar/domain/protein_catalog/repository.py` (protocol)
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py`
- Test: `backend/tests/api/test_genes.py` or an integration test with a DB session (follow existing repo-test convention; if repo tests use a real session fixture, add there).

**Interfaces:**
- Produces: `async def find_genomic_neighbors(self, *, organism_id: uuid.UUID, genomic_accession: str, center_start: int, window: int) -> list[Gene]` — genes on the same `(organism_id, genomic_accession)` whose `genomic_start` falls within the `window` nearest upstream and `window` nearest downstream of `center_start` (inclusive of the center gene), ordered ascending by `genomic_start`.

- [ ] **Step 1: Add the protocol signature** in `repository.py`:

```python
async def find_genomic_neighbors(
    self, *, organism_id: uuid.UUID, genomic_accession: str, center_start: int, window: int
) -> list[Gene]: ...
```

- [ ] **Step 2: Implement** in `SQLAlchemyGeneRepository` (two bounded queries, then merge — avoids loading the whole replicon):

```python
async def find_genomic_neighbors(
    self, *, organism_id: uuid.UUID, genomic_accession: str, center_start: int, window: int
) -> list[Gene]:
    base = (GeneModel.organism_id == organism_id) & (GeneModel.genomic_accession == genomic_accession)
    up = (
        select(GeneModel).where(base, GeneModel.genomic_start < center_start)
        .order_by(GeneModel.genomic_start.desc()).limit(window)
    )
    down = (
        select(GeneModel).where(base, GeneModel.genomic_start >= center_start)
        .order_by(GeneModel.genomic_start.asc()).limit(window + 1)  # +1 includes the center gene
    )
    rows = list((await self._session.execute(up)).scalars()) + list((await self._session.execute(down)).scalars())
    rows.sort(key=lambda m: (m.genomic_start if m.genomic_start is not None else 0))
    return [self._to_domain_tracked(m) for m in rows]
```

- [ ] **Step 3: Write the test** (seed several genes with coords, assert window + ordering). Use the project's repo/session test fixture convention.

```python
# Sketch — adapt to the repo session fixture in tests/
async def test_find_genomic_neighbors_returns_window_ordered(gene_repo, session) -> None:
    org = uuid.uuid4()
    for i, start in enumerate([100, 200, 300, 400, 500]):
        await gene_repo.add(Gene.create(
            primary_name=f"g{i}", organism_id=org,
            genomic_accession="NC_000962.3", genomic_start=start, genomic_end=start + 50, genomic_strand="+",
        ))
    await session.commit()
    out = await gene_repo.find_genomic_neighbors(
        organism_id=org, genomic_accession="NC_000962.3", center_start=300, window=1
    )
    assert [g.genomic_start for g in out] == [200, 300, 400]
```

- [ ] **Step 4: Run + Step 5: Commit**

```bash
git add backend/src/protcellar/domain/protein_catalog/repository.py backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py backend/tests/
git commit -m "feat(genes): genomic-neighbor query on gene repository"
```

---

## Phase 3 — API

### Task 6: `GeneResponse` exposes location + length_bp + annotations

**Files:**
- Modify: `backend/src/protcellar/interface/routes/genes.py`
- Test: `backend/tests/api/test_genes.py`

**Interfaces:**
- Produces: `GeneAnnotationResponse(BaseModel)` (axis, key, value, value_type, dataset, condition, evidence, source, source_url); `GeneResponse` gains `genomic_accession, genomic_start, genomic_end, genomic_strand, assembly, length_bp` and `annotations: list[GeneAnnotationResponse]`.

- [ ] **Step 1: Failing API test** — create a gene with location + an annotation (via the create/update path from Task 7, or seed the repo), GET it, assert the new fields serialize.

```python
def test_gene_response_includes_location_and_annotations(client, seeded_gene_with_locus):
    r = client.get(f"/api/v1/genes/{seeded_gene_with_locus.id}")
    body = r.json()
    assert body["genomic_accession"] == "NC_000962.3"
    assert body["length_bp"] == 3519
    assert body["annotations"][0]["axis"] == "vulnerability"
    assert body["annotations"][0]["value"] == "essential"
```

- [ ] **Step 2: Run (fail) → Step 3: Implement.** Add `GeneAnnotationResponse`, extend `GeneResponse`, and map from the domain `Gene` where `GeneResponse` is built (include `length_bp=g.length_bp` and `annotations=[GeneAnnotationResponse(...) for a in g.annotations]`).

- [ ] **Step 4: Run (pass) → Step 5: Commit**

```bash
git add backend/src/protcellar/interface/routes/genes.py backend/tests/api/test_genes.py
git commit -m "feat(genes): expose genomic location + annotations on GeneResponse"
```

---

### Task 7: Create/Update accept location + annotations (v1 enrichment path)

**Files:**
- Modify: `backend/src/protcellar/interface/routes/genes.py` + the create/update application command(s)
- Test: `backend/tests/api/test_genes.py`

**Interfaces:**
- Consumes: `Gene.update(...)` (Task 2).
- Produces: `CreateGeneBody`/`UpdateGeneBody` gain `genomic_accession, genomic_start, genomic_end, genomic_strand, assembly` and `annotations: list[GeneAnnotationBody]` (`GeneAnnotationBody` mirrors `GeneAnnotationResponse` minus computed fields). The update command forwards these to `Gene.update`.

- [ ] **Step 1: Failing test** — PATCH a gene with location + a vulnerability annotation, GET, assert persisted.

```python
def test_patch_sets_location_and_vulnerability_annotation(client, seeded_gene):
    r = client.patch(f"/api/v1/genes/{seeded_gene.id}", json={
        "genomic_accession": "NC_000962.3", "genomic_start": 2153889, "genomic_end": 2156111, "genomic_strand": "+",
        "annotations": [{"axis": "vulnerability", "key": "essentiality", "value": "essential",
                          "dataset": "DeJesus 2017", "condition": "in vitro 7H9"}],
    })
    assert r.status_code == 200
    body = client.get(f"/api/v1/genes/{seeded_gene.id}").json()
    assert body["genomic_strand"] == "+"
    assert body["annotations"][0]["dataset"] == "DeJesus 2017"
```

- [ ] **Step 2-4: Implement** the body models, map `annotations` body → `GeneAnnotation` domain objects, thread through the update command (and create command), run to green.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/interface/routes/genes.py backend/src/protcellar/application/protein_catalog/ backend/tests/api/test_genes.py
git commit -m "feat(genes): set genomic location + annotations via create/update"
```

---

### Task 8: Neighborhood endpoint

**Files:**
- Modify: `backend/src/protcellar/interface/routes/genes.py` + new query use case `backend/src/protcellar/application/protein_catalog/get_gene_neighborhood.py`
- Test: `backend/tests/api/test_genes.py`

**Interfaces:**
- Consumes: `find_genomic_neighbors` (Task 5).
- Produces: `GET /api/v1/genes/{gene_id}/neighborhood?window=8` → `GeneNeighborhoodResponse { center_id: UUID, accession: str, neighbors: list[GeneNeighborSummary] }`, where `GeneNeighborSummary = { id, primary_name, genomic_start, genomic_end, genomic_strand, essentiality: str | None }`. `essentiality` is the `value` of the gene's annotation with `key == "essentiality"` (or null). Returns `404` if the gene has no `genomic_accession`/`genomic_start`.

- [ ] **Step 1: Failing test** — seed 3 genes with coords (one essential), GET neighborhood of the middle, assert ordered neighbors + essentiality passthrough; GET neighborhood of a gene without coords → 404.

- [ ] **Step 2-4: Implement** the use case (load gene → guard location → `find_genomic_neighbors` → map to summaries, pulling `essentiality` from each neighbor's annotations) and the route.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/interface/routes/genes.py backend/src/protcellar/application/protein_catalog/get_gene_neighborhood.py backend/tests/api/test_genes.py
git commit -m "feat(genes): GET /genes/{id}/neighborhood derived endpoint"
```

---

### Task 9: Regenerate the frontend API client (chore)

**Files:** `frontend/openapi.json`, `frontend/src/shared/lib/api/**` (generated)

- [ ] **Step 1:** Export schema + regenerate: `make generate-api` (or the documented two-step: dump `app.openapi()` → `frontend/openapi.json`, then `pnpm generate:api`).
- [ ] **Step 2:** Verify new model types exist: `GeneAnnotationResponse`, `GeneNeighborhoodResponse`, `GeneNeighborSummary`, and the neighborhood query hook (e.g. `useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet`).
- [ ] **Step 3:** `./node_modules/.bin/tsc --noEmit` (from `frontend/`) → no errors.
- [ ] **Step 4: Commit**

```bash
git add frontend/openapi.json frontend/src/shared/lib/api
git commit -m "chore(frontend): regenerate API client for gene locus context"
```

---

## Phase 4 — Frontend

### Task 10: Genomic-context section (location + neighborhood map)

**Files:**
- Create: `frontend/src/features/protein-catalog/components/sections/genomic-context-section.tsx`
- Modify: `frontend/src/features/protein-catalog/hooks/use-genes.ts` (add `useGeneNeighborhood`)
- Test: `frontend/src/features/protein-catalog/components/sections/genomic-context-section.test.tsx`

**Interfaces:**
- Consumes: `Gene` type (now with location fields), the generated neighborhood hook.
- Produces: `GenomicContextSection({ gene }: { gene: Gene })` — returns `null` when `!gene.genomic_accession`. Renders a location row (accession · `start–end` · strand · `length_bp` bp) and a horizontal neighborhood track: one box per neighbor (ordered by start), the current gene highlighted, each box shaded by essentiality (essential → strong, non-essential → muted, unknown → neutral), neighbors link to `/genes/{id}`.

- [ ] **Step 1: Failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GenomicContextSection } from "./genomic-context-section";

const gene = { id: "g1", genomic_accession: "NC_000962.3", genomic_start: 759807,
  genomic_end: 763325, genomic_strand: "+", length_bp: 3519 } as any;

describe("GenomicContextSection", () => {
  it("returns null without location", () => {
    const { container } = render(<GenomicContextSection gene={{ id: "g" } as any} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("shows accession, coords and length", () => {
    render(<GenomicContextSection gene={gene} />);
    expect(screen.getByText(/NC_000962\.3/)).toBeInTheDocument();
    expect(screen.getByText(/3519 bp/)).toBeInTheDocument();
  });
});
```

(For the neighborhood track, mock the neighborhood hook to return a fixed list and assert neighbor names render + the current gene is marked current. Follow the existing hook-mocking convention in the feature's tests.)

- [ ] **Step 2-4:** Implement `useGeneNeighborhood(geneId)` (thin wrapper over the generated hook) and the section (location row always when accession present; neighborhood track when the hook returns ≥2 genes; skeleton while loading; no track on error). Match section conventions (`Card`, `text-base font-semibold` title, early null return).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/protein-catalog/components/sections/genomic-context-section.tsx frontend/src/features/protein-catalog/components/sections/genomic-context-section.test.tsx frontend/src/features/protein-catalog/hooks/use-genes.ts
git commit -m "feat(genes): genomic-context section with neighborhood map"
```

---

### Task 11: Axis annotations section (vulnerability first, generic)

**Files:**
- Create: `frontend/src/features/protein-catalog/components/sections/axis-annotations-section.tsx`
- Test: `frontend/src/features/protein-catalog/components/sections/axis-annotations-section.test.tsx`

**Interfaces:**
- Produces: `AxisAnnotationsSection({ gene, axis, title }: { gene: Gene; axis: string; title: string })` — filters `gene.annotations` by `axis`, returns `null` when none, renders chips of `value` with a tooltip/subline of `dataset · condition` and a link when `source_url` is set. A small map `AXIS_TITLES` exports `{ vulnerability: "Vulnerability", selectivity: "Selectivity", robustness: "Robustness", context: "Genomic context", expression: "Expression" }` for reuse.

- [ ] **Step 1: Failing test** — gene with a vulnerability annotation renders its value + dataset; empty → null.

```tsx
const gene = { annotations: [{ axis: "vulnerability", key: "essentiality", value: "essential",
  dataset: "DeJesus 2017", condition: "in vitro 7H9" }] } as any;
it("renders vulnerability value + dataset", () => {
  render(<AxisAnnotationsSection gene={gene} axis="vulnerability" title="Vulnerability" />);
  expect(screen.getByText("essential")).toBeInTheDocument();
  expect(screen.getByText(/DeJesus 2017/)).toBeInTheDocument();
});
it("returns null when axis empty", () => {
  const { container } = render(<AxisAnnotationsSection gene={{ annotations: [] } as any} axis="vulnerability" title="Vulnerability" />);
  expect(container).toBeEmptyDOMElement();
});
```

- [ ] **Step 2-4: Implement** + green. - [ ] **Step 5: Commit**

```bash
git add frontend/src/features/protein-catalog/components/sections/axis-annotations-section.tsx frontend/src/features/protein-catalog/components/sections/axis-annotations-section.test.tsx
git commit -m "feat(genes): generic axis annotations section (vulnerability)"
```

---

### Task 12: Wire sections into the gene detail page

**Files:**
- Modify: `frontend/src/features/protein-catalog/components/gene-detail.tsx`
- Test: `frontend/src/features/protein-catalog/components/gene-detail.test.tsx` (create or extend)

**Interfaces:**
- Consumes: `GenomicContextSection`, `AxisAnnotationsSection`, `AXIS_TITLES`.

- [ ] **Step 1: Failing test** — render `GeneDetailPage` (mock `useGene` to return a gene with location + a vulnerability annotation) and assert the location text and "essential" appear; render with a bare gene and assert neither section renders.

- [ ] **Step 2-4: Implement** — insert, between `GeneMetadataCard` and `LinkedProteinsSection`: `<GenomicContextSection gene={data} />`, then `<AxisAnnotationsSection gene={data} axis="vulnerability" title={AXIS_TITLES.vulnerability} />`. (Selectivity/robustness/expression panels are intentionally **not** wired in v1 — no data yet; they’re one line each to add later.) Keep "Encodes"/linked proteins as the bridge.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/protein-catalog/components/gene-detail.tsx frontend/src/features/protein-catalog/components/gene-detail.test.tsx
git commit -m "feat(genes): wire genomic-context + vulnerability into gene detail"
```

---

## Final verification

- [ ] `uv run --directory backend pytest tests/unit tests/api -q` → all green.
- [ ] From `frontend/`: `./node_modules/.bin/vitest run` → green; `./node_modules/.bin/tsc --noEmit` → clean; `./node_modules/.bin/biome check src/` → clean.
- [ ] `uv run --directory backend lint-imports` → architecture check passes.

## Out of scope (follow-up plan)

- **Phase 5 — bulk ingestion/enrichment adapters** (Mycobrowser GFF → location + functional-category CONTEXT annotation; DeJesus 2017 → vulnerability annotations), the `BulkEnrichGenes` match-and-append use case, and the documented import command. Gets its own plan: `docs/superpowers/plans/2026-06-22-gene-enrichment-ingestion.md`.
- Selectivity (human ortholog / OrthoDB), Robustness (conservation), Expression (RNA-seq) data — schema is ready; panels wire in when adapters land.
- `isProkaryote` organism-class gating — v1 gates the genomic-context module on **location-data presence** (only bacterial genomes carry it in v1), which achieves the same effect; an explicit helper is deferred.
