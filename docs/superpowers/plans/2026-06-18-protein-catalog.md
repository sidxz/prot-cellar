# prot-cellar Protein Catalog Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Prerequisite:** The Foundation plan (`2026-06-18-foundation.md`) and the Taxonomy plan (`2026-06-18-taxonomy-context.md`) must be fully implemented and green on branch `feat/foundation`. This plan builds on the base classes, repository, UoW, event dispatcher, identifier registry, `ProvenanceMixin`, `GLOBAL_WORKSPACE_ID` sentinel, the `Organism`/`Gene` FK targets (`organisms`/`strains` tables), and the `Organism` reference-data slice (the exemplar to mirror).

**Goal:** Implement the Protein Catalog bounded context — `Gene` (UniProt `GN`-line gene, shared reference data) and `Protein` (UniProtKB-anchored, the heart of the catalog: sequence + CRC64 + organism/strain/gene links + cross-references), each as a full domain→application→infrastructure→interface vertical slice, plus FASTA content negotiation, an ID-resolution endpoint, and an idempotent bulk-import endpoint with provenance.

**Architecture:** `Protein` and `Gene` are **shared, workspace-agnostic reference data** (exactly like `Organism`/`Proteome`): stored under `GLOBAL_WORKSPACE_ID`, mutations guard `require_admin` only (no `require_same_workspace`), reads guard `require_authenticated`, Commands carry **no** `workspace_id`. They reuse every foundation mechanism (events, audit, optimistic concurrency, base repository) unchanged. Both reference `Organism`/`Strain`/`Gene` **only by `uuid.UUID` foreign-key id** — the protein_catalog **domain never imports the taxonomy domain**, preserving bounded-context independence (the FK is an infrastructure-level constraint to `organisms.id`/`strains.id`). Neither aggregate carries a domain `source` enum, so both use `ProvenanceMixin` directly (no `source` name clash — unlike `Organism`; this mirrors `Proteome`).

**Tech Stack:** Same as Foundation/Taxonomy. No new runtime dependencies. Postgres-specific `ARRAY(String)` columns are used (the test suite runs on real PostgreSQL via testcontainers, and prod is Postgres 16).

## Global Constraints

- All Foundation + Taxonomy Global Constraints apply (workspace scoping, auth-guards-first, Railway `Result`, optimistic concurrency, UoW + post-commit event dispatch, ruff/mypy clean, commit-per-task).
- **Reference vs tenant data:** `Gene`/`Protein` set `workspace_id = GLOBAL_WORKSPACE_ID` in `__init__`; their write use cases guard `require_admin(auth)` and **do not** call `require_same_workspace`; read use cases guard `require_authenticated(auth)`. Commands/queries carry **no** `workspace_id`. (Identical to the `Organism` pattern; **not** the `Strain` pattern.)
- **Domain stays dependency-free:** accession validation uses a module-level `re` regex in the domain (mirror `Proteome._PROTEOME_ID_RE`); the `IdentifierRegistry` is used only at the interface/infrastructure edge for URL resolution. The domain must **not** import `sqlalchemy`, `fastapi`, or `protcellar.domain.taxonomy.*` (import-linter enforces both the layer and the future independence contract).
- **Provenance columns** (`source`, `source_release`, `source_record_id`, `source_record_checksum`, `imported_at`) come from `ProvenanceMixin` on both SA models. Carry the matching optional attrs on the domain aggregates (set during import, mapped by the repository) so bulk-upsert can key on `(source, source_record_id)`.
- **Mechanical CRUD (commands/queries, routes, DI wiring, response DTOs) mirrors the `Organism` reference-data slice exactly** — same `*Command`/`*Query` shapes, `Result` returns, `from_domain` DTOs, `result_to_response`, `_get_use_case` Lagom registration, `PaginatedResponse(items, next_cursor)` list envelope. Only the fields differ.
- **Gotchas (from the taxonomy build):** `export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar` before any `alembic` command; after adding a model module, append its import to `infrastructure/persistence/sqlalchemy/metadata.py` **then inspect autogenerate output for spurious `DROP`s** before applying; api-test DB is session-shared, so use distinct accessions/ids per test; list routes must return `PaginatedResponse(items, next_cursor)`, not a bare list.

---

## File Structure

```
backend/src/protcellar/
  domain/protein_catalog/
    __init__.py
    enums.py            # ProteinExistence
    value_objects.py    # ProteinNames VO
    gene.py             # Gene aggregate
    protein.py          # Protein aggregate (+ to_fasta)
    events.py           # GeneCreated/Updated, ProteinCreated/Updated
    repository.py       # GeneRepository, ProteinRepository protocols
  application/protein_catalog/
    __init__.py
    create_gene.py get_gene.py list_genes.py update_gene.py
    create_protein.py get_protein.py list_proteins.py update_protein.py
    resolve_protein_id.py
    bulk_upsert_proteins.py
  infrastructure/
    persistence/sqlalchemy/protein_catalog/
      __init__.py
      models.py            # GeneModel, ProteinModel
      gene_repository.py protein_repository.py
    di/_protein_catalog.py # register_protein_catalog(container)
  interface/
    routes/genes.py proteins.py
    dependencies/_protein_catalog.py
  (modify) infrastructure/di/container.py            # call register_protein_catalog
  (modify) interface/dependencies/__init__.py        # re-export the new *Dep aliases
  (modify) interface/app.py                          # include genes + proteins routers
  (modify) tests/api/conftest.py                     # include genes + proteins routers
  (modify) infrastructure/persistence/sqlalchemy/metadata.py  # import protein_catalog models
tests/
  unit/domain/protein_catalog/
    __init__.py test_value_objects.py test_gene.py test_protein.py
  unit/application/protein_catalog/
    __init__.py test_resolve_protein_id.py
  api/test_genes.py test_proteins.py test_protein_bulk_import.py
```

---

### Task 1: Protein Catalog shared — `ProteinExistence` enum + `ProteinNames` VO

**Files:**
- Create: `backend/src/protcellar/domain/protein_catalog/__init__.py` (empty)
- Create: `backend/src/protcellar/domain/protein_catalog/enums.py`
- Create: `backend/src/protcellar/domain/protein_catalog/value_objects.py`
- Test: `backend/tests/unit/domain/protein_catalog/__init__.py` (empty), `backend/tests/unit/domain/protein_catalog/test_value_objects.py`

**Interfaces:**
- Produces: `ProteinExistence` StrEnum (5 UniProt PE levels) with `.level: int` property and `ProteinExistence.from_level(int)` classmethod; `ProteinNames` frozen VO `{recommended: str | None, alternative: tuple[str, ...], submitted: tuple[str, ...]}` with `to_dict()`, `from_dict(dict | None)`, and `display_name` property.

- [ ] **Step 1: Write the failing test** `backend/tests/unit/domain/protein_catalog/test_value_objects.py`:

```python
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.value_objects import ProteinNames


def test_protein_existence_level_roundtrip() -> None:
    assert ProteinExistence.from_level(1) is ProteinExistence.PROTEIN_LEVEL
    assert ProteinExistence.PROTEIN_LEVEL.level == 1
    assert ProteinExistence.from_level(5).level == 5


def test_protein_names_to_from_dict_roundtrip() -> None:
    names = ProteinNames(recommended="Serum albumin", alternative=("Albumin",), submitted=())
    restored = ProteinNames.from_dict(names.to_dict())
    assert restored == names
    assert restored.display_name == "Serum albumin"


def test_protein_names_from_none_is_empty() -> None:
    empty = ProteinNames.from_dict(None)
    assert empty.recommended is None
    assert empty.alternative == ()
    assert empty.display_name is None


def test_display_name_falls_back_to_submitted_then_alternative() -> None:
    assert ProteinNames(submitted=("Sub name",)).display_name == "Sub name"
    assert ProteinNames(alternative=("Alt name",)).display_name == "Alt name"
```

- [ ] **Step 2: Run test to verify it fails** — `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_value_objects.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `domain/protein_catalog/__init__.py`** (empty file) and `domain/protein_catalog/enums.py`:

```python
"""Protein Catalog controlled vocabularies."""

from __future__ import annotations

from enum import StrEnum

# UniProt protein-existence (PE) levels 1-5.
_PE_LEVELS: dict[str, int] = {
    "evidence_at_protein_level": 1,
    "evidence_at_transcript_level": 2,
    "inferred_from_homology": 3,
    "predicted": 4,
    "uncertain": 5,
}


class ProteinExistence(StrEnum):
    PROTEIN_LEVEL = "evidence_at_protein_level"
    TRANSCRIPT_LEVEL = "evidence_at_transcript_level"
    HOMOLOGY = "inferred_from_homology"
    PREDICTED = "predicted"
    UNCERTAIN = "uncertain"

    @property
    def level(self) -> int:
        return _PE_LEVELS[self.value]

    @classmethod
    def from_level(cls, level: int) -> ProteinExistence:
        for member in cls:
            if member.level == level:
                return member
        raise ValueError(f"Unknown protein-existence level: {level}")
```

- [ ] **Step 4: Write `domain/protein_catalog/value_objects.py`:**

```python
"""Protein Catalog value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ProteinNames:
    """UniProt protein-name block: recommended / alternative / submitted names."""

    recommended: str | None = None
    alternative: tuple[str, ...] = ()
    submitted: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "recommended": self.recommended,
            "alternative": list(self.alternative),
            "submitted": list(self.submitted),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> ProteinNames:
        if not data:
            return cls()
        alt = data.get("alternative") or []
        sub = data.get("submitted") or []
        recommended = data.get("recommended")
        return cls(
            recommended=recommended if isinstance(recommended, str) else None,
            alternative=tuple(str(x) for x in alt),  # type: ignore[union-attr]
            submitted=tuple(str(x) for x in sub),  # type: ignore[union-attr]
        )

    @property
    def display_name(self) -> str | None:
        if self.recommended:
            return self.recommended
        if self.submitted:
            return self.submitted[0]
        if self.alternative:
            return self.alternative[0]
        return None
```

- [ ] **Step 5: Run test to verify it passes** — `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_value_objects.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/domain/protein_catalog/__init__.py \
        backend/src/protcellar/domain/protein_catalog/enums.py \
        backend/src/protcellar/domain/protein_catalog/value_objects.py \
        backend/tests/unit/domain/protein_catalog
git commit -m "feat(protein-catalog): ProteinExistence enum + ProteinNames value object"
```

---

### Task 2: `Gene` aggregate (domain) + events + repository protocol

**Files:**
- Create: `backend/src/protcellar/domain/protein_catalog/gene.py`, `events.py`, `repository.py`
- Test: `backend/tests/unit/domain/protein_catalog/test_gene.py`

**Interfaces:**
- Produces:
  - `Gene` aggregate (reference data, `workspace_id = GLOBAL_WORKSPACE_ID`): fields `primary_name: str`, `organism_id: uuid.UUID`, `synonyms: list[str]`, `ncbi_gene_id: str | None`, `ensembl_gene_id: str | None`, `hgnc_id: str | None`, `cross_references: list[CrossReference]`, provenance attrs (`source`, `source_release`, `source_record_id`, `source_record_checksum`, `imported_at` — all `str | None`/`datetime | None`), plus base `id`/`version`/`created_at`/`updated_at`. Classmethod `Gene.create(...)`, `update(**fields)`.
  - Events `GeneCreated(primary_name, organism_id)`, `GeneUpdated`.
  - `GeneRepository` protocol: `find_by_id_in_workspace`, `find_by_name(name, organism_id=None)`, `find_by_ncbi_gene_id(ncbi_gene_id)`, `find_all(*, cursor_id=None, limit=None, organism_id=None)`, `find_by_source_record_id(source, source_record_id)`, `save`.

- [ ] **Step 1: Write the failing test** `backend/tests/unit/domain/protein_catalog/test_gene.py`:

```python
import uuid

import pytest

from protcellar.domain.protein_catalog.events import GeneCreated
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def test_create_gene() -> None:
    organism = uuid.uuid4()
    gene = Gene.create(primary_name="TP53", organism_id=organism, synonyms=["P53", "LFS1"])
    assert gene.primary_name == "TP53"
    assert gene.organism_id == organism
    assert gene.synonyms == ["P53", "LFS1"]
    assert gene.workspace_id == GLOBAL_WORKSPACE_ID
    assert gene.version == 1
    events = gene.collect_events()
    assert len(events) == 1 and isinstance(events[0], GeneCreated)


def test_create_requires_primary_name() -> None:
    with pytest.raises(ValidationError):
        Gene.create(primary_name="   ", organism_id=uuid.uuid4())


def test_update_gene_fields() -> None:
    gene = Gene.create(primary_name="TP53", organism_id=uuid.uuid4())
    gene.update(ncbi_gene_id="7157", ensembl_gene_id="ENSG00000141510")
    assert gene.ncbi_gene_id == "7157"
    assert gene.ensembl_gene_id == "ENSG00000141510"
```

- [ ] **Step 2: Run test to verify it fails** — `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_gene.py -v` → FAIL.

- [ ] **Step 3: Write `domain/protein_catalog/events.py`:**

```python
"""Protein Catalog domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class GeneCreated(DomainEvent):
    primary_name: str
    organism_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class GeneUpdated(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ProteinCreated(DomainEvent):
    primary_accession: str
    organism_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteinUpdated(DomainEvent):
    pass
```

- [ ] **Step 4: Write `domain/protein_catalog/gene.py`:**

```python
"""Gene aggregate — a UniProt GN-line / NCBI Gene (shared reference data)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.protein_catalog.events import GeneCreated, GeneUpdated
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


class Gene(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        primary_name: str,
        organism_id: uuid.UUID,
        synonyms: list[str] | None = None,
        ncbi_gene_id: str | None = None,
        ensembl_gene_id: str | None = None,
        hgnc_id: str | None = None,
        cross_references: list[CrossReference] | None = None,
        source: str | None = None,
        source_release: str | None = None,
        source_record_id: str | None = None,
        source_record_checksum: str | None = None,
        imported_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not primary_name or not primary_name.strip():
            raise ValidationError("Gene primary_name must not be empty")
        # Reference data lives under the reserved GLOBAL workspace.
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.primary_name = primary_name.strip()
        self.organism_id = organism_id
        self.synonyms = synonyms if synonyms is not None else []
        self.ncbi_gene_id = ncbi_gene_id
        self.ensembl_gene_id = ensembl_gene_id
        self.hgnc_id = hgnc_id
        self.cross_references = cross_references if cross_references is not None else []
        self.source = source
        self.source_release = source_release
        self.source_record_id = source_record_id
        self.source_record_checksum = source_record_checksum
        self.imported_at = imported_at

    @classmethod
    def create(
        cls,
        *,
        primary_name: str,
        organism_id: uuid.UUID,
        synonyms: list[str] | None = None,
        ncbi_gene_id: str | None = None,
        ensembl_gene_id: str | None = None,
        hgnc_id: str | None = None,
        cross_references: list[CrossReference] | None = None,
    ) -> Gene:
        gene = cls(
            primary_name=primary_name,
            organism_id=organism_id,
            synonyms=synonyms,
            ncbi_gene_id=ncbi_gene_id,
            ensembl_gene_id=ensembl_gene_id,
            hgnc_id=hgnc_id,
            cross_references=cross_references,
        )
        gene.register_event(
            GeneCreated(
                aggregate_id=gene.id,
                aggregate_type="Gene",
                workspace_id=gene.workspace_id,
                primary_name=gene.primary_name,
                organism_id=gene.organism_id,
            )
        )
        return gene

    def update(self, **fields: Any) -> None:
        if "primary_name" in fields:
            value = fields["primary_name"]
            if not value or not str(value).strip():
                raise ValidationError("Gene primary_name must not be empty")
            self.primary_name = str(value).strip()
        if "synonyms" in fields:
            self.synonyms = list(fields["synonyms"] or [])
        if "ncbi_gene_id" in fields:
            self.ncbi_gene_id = fields["ncbi_gene_id"]
        if "ensembl_gene_id" in fields:
            self.ensembl_gene_id = fields["ensembl_gene_id"]
        if "hgnc_id" in fields:
            self.hgnc_id = fields["hgnc_id"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            GeneUpdated(
                aggregate_id=self.id,
                aggregate_type="Gene",
                workspace_id=self.workspace_id,
            )
        )
```

- [ ] **Step 5: Write `domain/protein_catalog/repository.py`** — **`GeneRepository` only.** Do **not** declare `ProteinRepository` here: it references `Protein` (created in Task 4), and a `TYPE_CHECKING` import of the not-yet-existing `protcellar.domain.protein_catalog.protein` module makes `mypy src` fail (mypy resolves `TYPE_CHECKING` blocks). `ProteinRepository` is appended to this file in Task 4, once `protein.py` exists.

```python
"""Protein Catalog repository protocols."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.protein_catalog.gene import Gene


@runtime_checkable
class GeneRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Gene | None: ...

    async def find_by_name(
        self, name: str, organism_id: uuid.UUID | None = None
    ) -> list[Gene]: ...

    async def find_by_ncbi_gene_id(self, ncbi_gene_id: str) -> Gene | None: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
    ) -> list[Gene]: ...

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Gene | None: ...

    async def save(self, aggregate: Gene) -> None: ...
```

- [ ] **Step 6: Run test to verify it passes** — `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_gene.py -v` → PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/protcellar/domain/protein_catalog/gene.py \
        backend/src/protcellar/domain/protein_catalog/events.py \
        backend/src/protcellar/domain/protein_catalog/repository.py \
        backend/tests/unit/domain/protein_catalog/test_gene.py
git commit -m "feat(protein-catalog): Gene aggregate, events, repository protocols"
```

---

### Task 3: `Gene` full vertical slice (persistence + use cases + routes + DI + migration)

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/__init__.py` (empty), `models.py` (GeneModel only; ProteinModel added Task 4), `gene_repository.py`
- Create: `backend/src/protcellar/application/protein_catalog/__init__.py` (empty), `create_gene.py`, `get_gene.py`, `list_genes.py`, `update_gene.py`
- Create: `backend/src/protcellar/infrastructure/di/_protein_catalog.py`, `backend/src/protcellar/interface/dependencies/_protein_catalog.py`, `backend/src/protcellar/interface/routes/genes.py`
- Modify: `infrastructure/persistence/sqlalchemy/metadata.py`, `infrastructure/di/container.py`, `interface/dependencies/__init__.py`, `interface/app.py`, `tests/api/conftest.py`
- Create migration: `xxxx_gene_tables.py`
- Test: `backend/tests/api/test_genes.py`

**Interfaces:**
- Consumes: `Base`, `EntityModelMixin`, `WorkspaceIdMixin`, `VersionMixin`, `ProvenanceMixin`, `SQLAlchemyRepository`, `AsyncUnitOfWork`, `Gene`, `CrossReference`, `require_admin`/`require_authenticated`, `EventDispatcher`, `_get_use_case`, `IdentifierRegistry`.
- Produces: `GeneModel`, `SQLAlchemyGeneRepository`; `CreateGene`/`UpdateGene` commands, `GetGene`/`ListGenes` queries; `GET/POST/PATCH /api/v1/genes...` routes; `register_protein_catalog(container)` (Gene bindings now, Protein added later); `*Dep` aliases.

- [ ] **Step 1: Write `infrastructure/persistence/sqlalchemy/protein_catalog/__init__.py`** (empty) and `models.py`:

```python
"""SQLAlchemy models for the Protein Catalog context."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)
from protcellar.infrastructure.persistence.sqlalchemy.provenance import ProvenanceMixin


class GeneModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin, ProvenanceMixin):
    __tablename__ = "genes"

    primary_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    synonyms: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    ncbi_gene_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ensembl_gene_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hgnc_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
```

> Task 4 appends `Boolean, Index, Integer, Text` to the `from sqlalchemy import ...` line when adding `ProteinModel`.

- [ ] **Step 2: Write `protein_catalog/gene_repository.py`:**

```python
"""SQLAlchemy Gene repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import GeneModel


def _xrefs_to_json(xrefs: list[CrossReference]) -> list[dict[str, object]]:
    return [
        {
            "database": x.database,
            "accession": x.accession,
            "properties": x.properties,
            "evidence": x.evidence,
        }
        for x in xrefs
    ]


def _xrefs_from_json(data: list[dict[str, object]] | None) -> list[CrossReference]:
    if not data:
        return []
    return [
        CrossReference(
            database=str(d["database"]),
            accession=str(d["accession"]),
            properties=d.get("properties"),  # type: ignore[arg-type]
            evidence=d.get("evidence"),  # type: ignore[arg-type]
        )
        for d in data
    ]


class SQLAlchemyGeneRepository(SQLAlchemyRepository[Gene, GeneModel], GeneRepository):
    model_class = GeneModel

    def _to_domain(self, model: GeneModel) -> Gene:
        return Gene(
            id=model.id,
            primary_name=model.primary_name,
            organism_id=model.organism_id,
            synonyms=list(model.synonyms) if model.synonyms else [],
            ncbi_gene_id=model.ncbi_gene_id,
            ensembl_gene_id=model.ensembl_gene_id,
            hgnc_id=model.hgnc_id,
            cross_references=_xrefs_from_json(model.cross_references),
            source=model.source,
            source_release=model.source_release,
            source_record_id=model.source_record_id,
            source_record_checksum=model.source_record_checksum,
            imported_at=model.imported_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Gene) -> GeneModel:
        return GeneModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            primary_name=aggregate.primary_name,
            organism_id=aggregate.organism_id,
            synonyms=aggregate.synonyms or None,
            ncbi_gene_id=aggregate.ncbi_gene_id,
            ensembl_gene_id=aggregate.ensembl_gene_id,
            hgnc_id=aggregate.hgnc_id,
            cross_references=_xrefs_to_json(aggregate.cross_references) or None,
            source=aggregate.source,
            source_release=aggregate.source_release,
            source_record_id=aggregate.source_record_id,
            source_record_checksum=aggregate.source_record_checksum,
            imported_at=aggregate.imported_at,
            version=aggregate.version,
        )

    def _update_model(self, model: GeneModel, aggregate: Gene) -> None:
        model.primary_name = aggregate.primary_name
        model.organism_id = aggregate.organism_id
        model.synonyms = aggregate.synonyms or None
        model.ncbi_gene_id = aggregate.ncbi_gene_id
        model.ensembl_gene_id = aggregate.ensembl_gene_id
        model.hgnc_id = aggregate.hgnc_id
        model.cross_references = _xrefs_to_json(aggregate.cross_references) or None
        model.source = aggregate.source
        model.source_release = aggregate.source_release
        model.source_record_id = aggregate.source_record_id
        model.source_record_checksum = aggregate.source_record_checksum
        model.imported_at = aggregate.imported_at

    async def find_by_name(
        self, name: str, organism_id: uuid.UUID | None = None
    ) -> list[Gene]:
        stmt = select(GeneModel).where(GeneModel.primary_name.ilike(f"%{name}%"))
        if organism_id is not None:
            stmt = stmt.where(GeneModel.organism_id == organism_id)
        stmt = stmt.order_by(GeneModel.primary_name).limit(50)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_by_ncbi_gene_id(self, ncbi_gene_id: str) -> Gene | None:
        stmt = select(GeneModel).where(GeneModel.ncbi_gene_id == ncbi_gene_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Gene | None:
        stmt = select(GeneModel).where(
            GeneModel.source == source,
            GeneModel.source_record_id == source_record_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
    ) -> list[Gene]:
        stmt = select(GeneModel).order_by(GeneModel.id)
        if organism_id is not None:
            stmt = stmt.where(GeneModel.organism_id == organism_id)
        if cursor_id is not None:
            stmt = stmt.where(GeneModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
```

- [ ] **Step 3: Write the four Gene use cases** in `application/protein_catalog/`. Each mirrors the matching `application/taxonomy/<x>_organism.py` file **exactly**, swapping `Organism`→`Gene`, repo type→`GeneRepository`, and the fields. `create_gene.py` (full code below for the representative one); `get_gene.py`/`list_genes.py`/`update_gene.py` follow the Organism equivalents verbatim with the field changes noted.

`application/protein_catalog/create_gene.py`:

```python
"""Create a gene reference record (admin/service only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class CreateGeneCommand(Command):
    primary_name: str
    organism_id: uuid.UUID
    synonyms: list[str] = field(default_factory=list)
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    hgnc_id: str | None = None


class CreateGene:
    def __init__(
        self, uow: UnitOfWork, repo: GeneRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateGeneCommand, auth: AuthContext | None = None
    ) -> Result[Gene, DomainError]:
        require_admin(auth)
        async with self._uow:
            gene = Gene.create(
                primary_name=input.primary_name,
                organism_id=input.organism_id,
                synonyms=list(input.synonyms),
                ncbi_gene_id=input.ncbi_gene_id,
                ensembl_gene_id=input.ensembl_gene_id,
                hgnc_id=input.hgnc_id,
            )
            await self._repo.save(gene)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(gene)
```

`get_gene.py` — mirror `get_organism.py`: `GetGeneQuery{gene_id: uuid.UUID}`, `require_authenticated`, `find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, input.gene_id)`, `NotFoundError("Gene", ...)`.

`list_genes.py` — mirror `list_organisms.py`: `ListGenesQuery{cursor_id, limit, name, organism_id}`, `require_authenticated`. If `name` is set → `find_by_name(name, organism_id)` (no cursor), else `find_all(cursor_id, limit, organism_id=...)` with the same `+1`/`next_cursor` slicing. Returns `Result[PageResult[Gene], DomainError]`.

`update_gene.py` — mirror `update_organism.py` (use the `UNSET` sentinel for nullable optionals): `UpdateGeneCommand{gene_id, primary_name=None, synonyms=None, ncbi_gene_id=UNSET, ensembl_gene_id=UNSET, hgnc_id=UNSET}`, `require_admin`, load via `find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, ...)`, build the `fields` dict (include only provided), `gene.update(**fields)`, `save`, commit, dispatch.

- [ ] **Step 4: Write `interface/routes/genes.py`** mirroring `organisms.py` (CRUD only — no resolve/bulk for Gene in v1). `GeneResponse.from_domain` exposes `id, primary_name, organism_id, synonyms, ncbi_gene_id, ncbi_gene_url, ensembl_gene_id, ensembl_url, hgnc_id, cross_references, version` where:

```python
ncbi_gene_url = (
    IdentifierRegistry.default().resolve_url("ncbigene", g.ncbi_gene_id)
    if g.ncbi_gene_id is not None else None
)
ensembl_url = (
    IdentifierRegistry.default().resolve_url("ensembl", g.ensembl_gene_id)
    if g.ensembl_gene_id is not None else None
)
```

Routes (declare in this order): `GET /api/v1/genes` (list/search; reads `name`, `organism_id`, `cursor`, `limit`), `GET /api/v1/genes/{gene_id}`, `POST /api/v1/genes` (201), `PATCH /api/v1/genes/{gene_id}`. `router = APIRouter(prefix="/api/v1/genes", tags=["genes"])`. Use `result_to_response`, `PaginatedResponse[GeneResponse]`, `clamp_limit`, `parse_cursor`. The PATCH route builds the command from `body.model_fields_set` exactly like `update_organism` route does. Render `cross_references` as a list of `{database, accession, to_curie(), url}` (URL via `IdentifierRegistry.default().resolve_url(x.database, x.accession)`).

- [ ] **Step 5: Write `infrastructure/di/_protein_catalog.py`** mirroring `_taxonomy.py`'s organism command/query helpers (`_gene_cmd`/`_gene_query` building `AsyncUnitOfWork(c[async_sessionmaker])` + `SQLAlchemyGeneRepository(uow)` + `c[EventDispatcher]` for commands). Register `CreateGene`, `UpdateGene` (commands) and `GetGene`, `ListGenes` (queries). (Protein bindings appended in Tasks 5-7.)

```python
"""Protein Catalog DI bindings."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.protein_catalog.create_gene import CreateGene
from protcellar.application.protein_catalog.get_gene import GetGene
from protcellar.application.protein_catalog.list_genes import ListGenes
from protcellar.application.protein_catalog.update_gene import UpdateGene
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_protein_catalog(container: Container) -> None:
    def _gene_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyGeneRepository(uow), c[EventDispatcher])

        return _f

    def _gene_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyGeneRepository(uow))

        return _f

    container.define(CreateGene, _gene_cmd(CreateGene))
    container.define(UpdateGene, _gene_cmd(UpdateGene))
    container.define(GetGene, _gene_query(GetGene))
    container.define(ListGenes, _gene_query(ListGenes))
```

- [ ] **Step 6: Write `interface/dependencies/_protein_catalog.py`** mirroring `_taxonomy.py` dependency aliases — `CreateGeneDep`, `UpdateGeneDep`, `GetGeneDep`, `ListGenesDep` via `Annotated[..., Depends(_get_use_case(...))]`, with the matching `__all__`.

- [ ] **Step 7: Wire it up (5 edits):**
  1. `infrastructure/persistence/sqlalchemy/metadata.py` — add `import protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models  # noqa: F401`.
  2. `infrastructure/di/container.py` — `from protcellar.infrastructure.di._protein_catalog import register_protein_catalog` and call `register_protein_catalog(container)` after `register_taxonomy(container)`.
  3. `interface/dependencies/__init__.py` — import + re-export the four `*GeneDep` aliases (add to the `from ._protein_catalog import (...)` block and `__all__`).
  4. `interface/app.py` — `from protcellar.interface.routes.genes import router as gene_router` and `app.include_router(gene_router)`.
  5. `tests/api/conftest.py` — add the genes router import + `app.include_router(gene_router)` in `_create_test_app`.

- [ ] **Step 8: Generate and apply the migration**

Run: `export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar`
Run: `cd backend && uv run alembic revision --autogenerate -m "gene tables"`
**Inspect the generated migration** — it must `create_table("genes")` with the FK to `organisms.id` and **no spurious `DROP`** of existing tables. Then:
Run: `uv run alembic upgrade head`

- [ ] **Step 9: Write `tests/api/test_genes.py`:**

```python
import pytest
from httpx import AsyncClient


async def _make_organism(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_get_and_search_gene(client: AsyncClient) -> None:
    organism_id = await _make_organism(client)

    created = await client.post(
        "/api/v1/genes",
        json={
            "primary_name": "TP53",
            "organism_id": organism_id,
            "synonyms": ["P53"],
            "ncbi_gene_id": "7157",
            "ensembl_gene_id": "ENSG00000141510",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["primary_name"] == "TP53"
    assert body["ncbi_gene_url"] is not None
    gene_id = body["id"]

    fetched = await client.get(f"/api/v1/genes/{gene_id}")
    assert fetched.status_code == 200
    assert fetched.json()["ensembl_gene_id"] == "ENSG00000141510"

    found = await client.get("/api/v1/genes", params={"name": "TP5"})
    assert found.status_code == 200
    assert any(g["primary_name"] == "TP53" for g in found.json()["items"])


@pytest.mark.asyncio
async def test_update_gene_increments_version(client: AsyncClient) -> None:
    organism_id = await _make_organism(client)
    created = await client.post(
        "/api/v1/genes", json={"primary_name": "BRCA1", "organism_id": organism_id}
    )
    gene_id = created.json()["id"]
    assert created.json()["version"] == 1

    patched = await client.patch(f"/api/v1/genes/{gene_id}", json={"hgnc_id": "HGNC:1100"})
    assert patched.status_code == 200
    assert patched.json()["hgnc_id"] == "HGNC:1100"
    assert patched.json()["version"] == 2
```

Run: `cd backend && uv run pytest tests/api/test_genes.py -v` → PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/src/protcellar backend/alembic/versions backend/tests
git commit -m "feat(protein-catalog): Gene reference-data vertical slice (CRUD + search + DI)"
```

---

### Task 4: `Protein` aggregate (domain) + persistence (SA model, repository, migration)

**Files:**
- Create: `backend/src/protcellar/domain/protein_catalog/protein.py`
- Modify: `infrastructure/persistence/sqlalchemy/protein_catalog/models.py` (add `ProteinModel`)
- Create: `infrastructure/persistence/sqlalchemy/protein_catalog/protein_repository.py`
- Create migration: `xxxx_protein_tables.py`
- Test: `backend/tests/unit/domain/protein_catalog/test_protein.py`

**Interfaces:**
- Produces:
  - `Protein` aggregate (reference data, `workspace_id = GLOBAL_WORKSPACE_ID`): `primary_accession: str` (validated via `_UNIPROT_ACCESSION_RE`), `secondary_accessions: list[str]`, `entry_name: str | None`, `is_reviewed: bool`, `protein_names: ProteinNames`, `organism_id: uuid.UUID` (required), `strain_id: uuid.UUID | None`, `gene_id: uuid.UUID | None`, `sequence: str`, `seq_length: int` (derived = `len(sequence)`), `seq_mass: int | None`, `seq_crc64: str | None`, `protein_existence: ProteinExistence | None`, `keywords: list[str]`, `entry_version: int | None`, `sequence_version: int | None`, `cross_references: list[CrossReference]`, provenance attrs. `Protein.create(...)`, `update(**fields)`, `to_fasta() -> str`.
  - The `ProteinRepository` protocol (appended to `domain/protein_catalog/repository.py` in this task, now that `Protein` exists), `ProteinModel`, and `SQLAlchemyProteinRepository` implementing it.

- [ ] **Step 1: Write the failing test** `backend/tests/unit/domain/protein_catalog/test_protein.py`:

```python
import uuid

import pytest

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.events import ProteinCreated
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def test_create_protein_derives_length_and_workspace() -> None:
    organism = uuid.uuid4()
    p = Protein.create(
        primary_accession="P0DTC2",
        organism_id=organism,
        sequence="MFVFLVLLPLVSSQ",
        is_reviewed=True,
        protein_names=ProteinNames(recommended="Spike glycoprotein"),
        protein_existence=ProteinExistence.PROTEIN_LEVEL,
    )
    assert p.primary_accession == "P0DTC2"
    assert p.seq_length == len("MFVFLVLLPLVSSQ")
    assert p.workspace_id == GLOBAL_WORKSPACE_ID
    assert p.version == 1
    events = p.collect_events()
    assert len(events) == 1 and isinstance(events[0], ProteinCreated)


def test_create_rejects_invalid_accession() -> None:
    with pytest.raises(ValidationError):
        Protein.create(
            primary_accession="NOT-AN-ACCESSION",
            organism_id=uuid.uuid4(),
            sequence="MKT",
            is_reviewed=False,
        )


def test_create_rejects_empty_sequence() -> None:
    with pytest.raises(ValidationError):
        Protein.create(
            primary_accession="P12345",
            organism_id=uuid.uuid4(),
            sequence="   ",
            is_reviewed=True,
        )


def test_to_fasta_header_and_wrapping() -> None:
    p = Protein.create(
        primary_accession="P12345",
        organism_id=uuid.uuid4(),
        sequence="M" * 130,
        is_reviewed=True,
        entry_name="TEST_HUMAN",
        protein_names=ProteinNames(recommended="Test protein"),
        sequence_version=2,
        protein_existence=ProteinExistence.PROTEIN_LEVEL,
    )
    fasta = p.to_fasta()
    lines = fasta.splitlines()
    assert lines[0].startswith(">sp|P12345|TEST_HUMAN Test protein")
    assert "PE=1" in lines[0] and "SV=2" in lines[0]
    # sequence wrapped at 60 chars
    assert len(lines[1]) == 60
    assert "".join(lines[1:]) == "M" * 130


def test_unreviewed_protein_uses_tr_prefix() -> None:
    p = Protein.create(
        primary_accession="A0A0A0",
        organism_id=uuid.uuid4(),
        sequence="MKT",
        is_reviewed=False,
    )
    assert p.to_fasta().startswith(">tr|A0A0A0|")
```

- [ ] **Step 2: Run test to verify it fails** — `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_protein.py -v` → FAIL.

- [ ] **Step 3: Write `domain/protein_catalog/protein.py`:**

```python
"""Protein aggregate — a UniProtKB entry (shared reference data; heart of the catalog)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.events import ProteinCreated, ProteinUpdated
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID

# UniProtKB accession syntax (6 or 10 alphanumerics, two layouts). Mirrors the
# registry `uniprot` prefix but kept here so the domain stays dependency-free.
_UNIPROT_ACCESSION_RE: re.Pattern[str] = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

_FASTA_WIDTH = 60


class Protein(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        primary_accession: str,
        organism_id: uuid.UUID,
        sequence: str,
        is_reviewed: bool,
        secondary_accessions: list[str] | None = None,
        entry_name: str | None = None,
        protein_names: ProteinNames | None = None,
        strain_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        seq_mass: int | None = None,
        seq_crc64: str | None = None,
        protein_existence: ProteinExistence | None = None,
        keywords: list[str] | None = None,
        entry_version: int | None = None,
        sequence_version: int | None = None,
        cross_references: list[CrossReference] | None = None,
        source: str | None = None,
        source_release: str | None = None,
        source_record_id: str | None = None,
        source_record_checksum: str | None = None,
        imported_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        accession = (primary_accession or "").strip()
        if not _UNIPROT_ACCESSION_RE.match(accession):
            raise ValidationError(
                f"Invalid UniProt primary_accession '{primary_accession}'"
            )
        if not sequence or not sequence.strip():
            raise ValidationError("Protein sequence must not be empty")
        # Reference data lives under the reserved GLOBAL workspace.
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.primary_accession = accession
        self.organism_id = organism_id
        self.sequence = sequence.strip()
        self.seq_length = len(self.sequence)
        self.is_reviewed = is_reviewed
        self.secondary_accessions = secondary_accessions if secondary_accessions is not None else []
        self.entry_name = entry_name
        self.protein_names = protein_names if protein_names is not None else ProteinNames()
        self.strain_id = strain_id
        self.gene_id = gene_id
        self.seq_mass = seq_mass
        self.seq_crc64 = seq_crc64
        self.protein_existence = protein_existence
        self.keywords = keywords if keywords is not None else []
        self.entry_version = entry_version
        self.sequence_version = sequence_version
        self.cross_references = cross_references if cross_references is not None else []
        self.source = source
        self.source_release = source_release
        self.source_record_id = source_record_id
        self.source_record_checksum = source_record_checksum
        self.imported_at = imported_at

    @classmethod
    def create(
        cls,
        *,
        primary_accession: str,
        organism_id: uuid.UUID,
        sequence: str,
        is_reviewed: bool,
        secondary_accessions: list[str] | None = None,
        entry_name: str | None = None,
        protein_names: ProteinNames | None = None,
        strain_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        seq_mass: int | None = None,
        seq_crc64: str | None = None,
        protein_existence: ProteinExistence | None = None,
        keywords: list[str] | None = None,
        entry_version: int | None = None,
        sequence_version: int | None = None,
        cross_references: list[CrossReference] | None = None,
    ) -> Protein:
        protein = cls(
            primary_accession=primary_accession,
            organism_id=organism_id,
            sequence=sequence,
            is_reviewed=is_reviewed,
            secondary_accessions=secondary_accessions,
            entry_name=entry_name,
            protein_names=protein_names,
            strain_id=strain_id,
            gene_id=gene_id,
            seq_mass=seq_mass,
            seq_crc64=seq_crc64,
            protein_existence=protein_existence,
            keywords=keywords,
            entry_version=entry_version,
            sequence_version=sequence_version,
            cross_references=cross_references,
        )
        protein.register_event(
            ProteinCreated(
                aggregate_id=protein.id,
                aggregate_type="Protein",
                workspace_id=protein.workspace_id,
                primary_accession=protein.primary_accession,
                organism_id=protein.organism_id,
            )
        )
        return protein

    def update(self, **fields: Any) -> None:
        if "sequence" in fields:
            value = str(fields["sequence"] or "").strip()
            if not value:
                raise ValidationError("Protein sequence must not be empty")
            self.sequence = value
            self.seq_length = len(value)
        if "is_reviewed" in fields:
            self.is_reviewed = bool(fields["is_reviewed"])
        if "entry_name" in fields:
            self.entry_name = fields["entry_name"]
        if "protein_names" in fields:
            self.protein_names = fields["protein_names"] or ProteinNames()
        if "secondary_accessions" in fields:
            self.secondary_accessions = list(fields["secondary_accessions"] or [])
        if "strain_id" in fields:
            self.strain_id = fields["strain_id"]
        if "gene_id" in fields:
            self.gene_id = fields["gene_id"]
        if "seq_mass" in fields:
            self.seq_mass = fields["seq_mass"]
        if "seq_crc64" in fields:
            self.seq_crc64 = fields["seq_crc64"]
        if "protein_existence" in fields:
            self.protein_existence = fields["protein_existence"]
        if "keywords" in fields:
            self.keywords = list(fields["keywords"] or [])
        if "entry_version" in fields:
            self.entry_version = fields["entry_version"]
        if "sequence_version" in fields:
            self.sequence_version = fields["sequence_version"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
        self._touch()

    def to_fasta(self) -> str:
        """Render a (simplified) UniProt-style FASTA record from local fields."""
        db = "sp" if self.is_reviewed else "tr"
        header = f">{db}|{self.primary_accession}|{self.entry_name or self.primary_accession}"
        display = self.protein_names.display_name
        if display:
            header += f" {display}"
        if self.protein_existence is not None:
            header += f" PE={self.protein_existence.level}"
        if self.sequence_version is not None:
            header += f" SV={self.sequence_version}"
        wrapped = [self.sequence[i : i + _FASTA_WIDTH] for i in range(0, len(self.sequence), _FASTA_WIDTH)]
        return "\n".join([header, *wrapped])

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            ProteinUpdated(
                aggregate_id=self.id,
                aggregate_type="Protein",
                workspace_id=self.workspace_id,
            )
        )
```

- [ ] **Step 4: Run test to verify it passes** — `cd backend && uv run pytest tests/unit/domain/protein_catalog/test_protein.py -v` → PASS.

- [ ] **Step 5: Add `ProteinModel` to `protein_catalog/models.py`** (append; ensure `JSON`, `Integer`, `Text`, `Boolean`, `Index` are imported from `sqlalchemy` and `ARRAY` from `sqlalchemy.dialects.postgresql`):

```python
class ProteinModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin, ProvenanceMixin):
    __tablename__ = "proteins"
    __table_args__ = (
        Index("ix_proteins_primary_accession", "primary_accession", unique=True),
        Index(
            "ix_proteins_secondary_accessions",
            "secondary_accessions",
            postgresql_using="gin",
        ),
    )

    primary_accession: Mapped[str] = mapped_column(String(10), nullable=False)
    secondary_accessions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    entry_name: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    protein_names: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    strain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strains.id"), nullable=True, index=True
    )
    gene_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("genes.id"), nullable=True, index=True
    )
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    seq_length: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    seq_mass: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seq_crc64: Mapped[str | None] = mapped_column(String(16), nullable=True)
    protein_existence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    entry_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
```

> `primary_accession` uniqueness is a plain unique index (not workspace-scoped) — reference data is global. The `secondary_accessions` GIN index accelerates `acc = ANY(secondary_accessions)` resolution.

- [ ] **Step 6a: Append the `ProteinRepository` protocol to `domain/protein_catalog/repository.py`** (now that `Protein` exists — no `TYPE_CHECKING` forward ref needed). Add a direct import `from protcellar.domain.protein_catalog.protein import Protein` and this protocol below `GeneRepository`:

```python
@runtime_checkable
class ProteinRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Protein | None: ...

    async def find_by_accession(self, accession: str) -> Protein | None: ...

    async def find_by_entry_name(self, entry_name: str) -> Protein | None: ...

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Protein | None: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        is_reviewed: bool | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> list[Protein]: ...

    async def save(self, aggregate: Protein) -> None: ...
```

- [ ] **Step 6b: Write `protein_catalog/protein_repository.py`** (reuse the `_xrefs_to_json`/`_xrefs_from_json` helpers — lift both helpers into a small `protein_catalog/_xref_json.py` module and import from both repositories, to avoid a repo→repo import):

```python
"""SQLAlchemy Protein repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._xref_json import (
    xrefs_from_json,
    xrefs_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import ProteinModel


class SQLAlchemyProteinRepository(
    SQLAlchemyRepository[Protein, ProteinModel], ProteinRepository
):
    model_class = ProteinModel

    def _to_domain(self, model: ProteinModel) -> Protein:
        return Protein(
            id=model.id,
            primary_accession=model.primary_accession,
            organism_id=model.organism_id,
            sequence=model.sequence,
            is_reviewed=model.is_reviewed,
            secondary_accessions=list(model.secondary_accessions) if model.secondary_accessions else [],
            entry_name=model.entry_name,
            protein_names=ProteinNames.from_dict(model.protein_names),
            strain_id=model.strain_id,
            gene_id=model.gene_id,
            seq_mass=model.seq_mass,
            seq_crc64=model.seq_crc64,
            protein_existence=(
                ProteinExistence(model.protein_existence)
                if model.protein_existence is not None
                else None
            ),
            keywords=list(model.keywords) if model.keywords else [],
            entry_version=model.entry_version,
            sequence_version=model.sequence_version,
            cross_references=xrefs_from_json(model.cross_references),
            source=model.source,
            source_release=model.source_release,
            source_record_id=model.source_record_id,
            source_record_checksum=model.source_record_checksum,
            imported_at=model.imported_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Protein) -> ProteinModel:
        return ProteinModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            primary_accession=aggregate.primary_accession,
            secondary_accessions=aggregate.secondary_accessions or None,
            entry_name=aggregate.entry_name,
            is_reviewed=aggregate.is_reviewed,
            protein_names=aggregate.protein_names.to_dict(),
            organism_id=aggregate.organism_id,
            strain_id=aggregate.strain_id,
            gene_id=aggregate.gene_id,
            sequence=aggregate.sequence,
            seq_length=aggregate.seq_length,
            seq_mass=aggregate.seq_mass,
            seq_crc64=aggregate.seq_crc64,
            protein_existence=(
                aggregate.protein_existence.value
                if aggregate.protein_existence is not None
                else None
            ),
            keywords=aggregate.keywords or None,
            entry_version=aggregate.entry_version,
            sequence_version=aggregate.sequence_version,
            cross_references=xrefs_to_json(aggregate.cross_references) or None,
            source=aggregate.source,
            source_release=aggregate.source_release,
            source_record_id=aggregate.source_record_id,
            source_record_checksum=aggregate.source_record_checksum,
            imported_at=aggregate.imported_at,
            version=aggregate.version,
        )

    def _update_model(self, model: ProteinModel, aggregate: Protein) -> None:
        model.primary_accession = aggregate.primary_accession
        model.secondary_accessions = aggregate.secondary_accessions or None
        model.entry_name = aggregate.entry_name
        model.is_reviewed = aggregate.is_reviewed
        model.protein_names = aggregate.protein_names.to_dict()
        model.organism_id = aggregate.organism_id
        model.strain_id = aggregate.strain_id
        model.gene_id = aggregate.gene_id
        model.sequence = aggregate.sequence
        model.seq_length = aggregate.seq_length
        model.seq_mass = aggregate.seq_mass
        model.seq_crc64 = aggregate.seq_crc64
        model.protein_existence = (
            aggregate.protein_existence.value if aggregate.protein_existence is not None else None
        )
        model.keywords = aggregate.keywords or None
        model.entry_version = aggregate.entry_version
        model.sequence_version = aggregate.sequence_version
        model.cross_references = xrefs_to_json(aggregate.cross_references) or None
        model.source = aggregate.source
        model.source_release = aggregate.source_release
        model.source_record_id = aggregate.source_record_id
        model.source_record_checksum = aggregate.source_record_checksum
        model.imported_at = aggregate.imported_at

    async def find_by_accession(self, accession: str) -> Protein | None:
        # Primary first, then secondary (resolves merged/demerged accessions).
        stmt = select(ProteinModel).where(ProteinModel.primary_accession == accession)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            # `@>` array-containment so the GIN index on secondary_accessions is usable.
            stmt = select(ProteinModel).where(
                ProteinModel.secondary_accessions.contains([accession])
            )
            model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_entry_name(self, entry_name: str) -> Protein | None:
        stmt = select(ProteinModel).where(ProteinModel.entry_name == entry_name)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Protein | None:
        stmt = select(ProteinModel).where(
            ProteinModel.source == source,
            ProteinModel.source_record_id == source_record_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        is_reviewed: bool | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> list[Protein]:
        stmt = select(ProteinModel).order_by(ProteinModel.id)
        if organism_id is not None:
            stmt = stmt.where(ProteinModel.organism_id == organism_id)
        if gene_id is not None:
            stmt = stmt.where(ProteinModel.gene_id == gene_id)
        if is_reviewed is not None:
            stmt = stmt.where(ProteinModel.is_reviewed == is_reviewed)
        if min_length is not None:
            stmt = stmt.where(ProteinModel.seq_length >= min_length)
        if max_length is not None:
            stmt = stmt.where(ProteinModel.seq_length <= max_length)
        if cursor_id is not None:
            stmt = stmt.where(ProteinModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
```

> **Create `protein_catalog/_xref_json.py`** with `xrefs_to_json`/`xrefs_from_json` (the exact functions written inline in Task 3 Step 2, renamed without leading underscore) and import them from BOTH `gene_repository.py` and `protein_repository.py` (replacing the private copies in `gene_repository.py`). This keeps the CrossReference↔JSON mapping DRY.

- [ ] **Step 7: Register the model with alembic + migrate**

`ProteinModel` is already covered by the `protein_catalog.models` import added to `metadata.py` in Task 3. Then:
Run: `export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar`
Run: `cd backend && uv run alembic revision --autogenerate -m "protein tables"`
**Inspect** for the `proteins` table with FKs to `organisms.id`/`strains.id`/`genes.id`, the unique `primary_accession` index, the GIN `secondary_accessions` index, and **no spurious `DROP`**. Then:
Run: `uv run alembic upgrade head`

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar backend/alembic/versions backend/tests/unit/domain/protein_catalog/test_protein.py
git commit -m "feat(protein-catalog): Protein aggregate (sequence/CRC64/xrefs/FASTA) + SA model + repository"
```

---

### Task 5: `Protein` application use cases (CRUD + ID-resolution)

**Files:**
- Create: `application/protein_catalog/{create_protein.py,get_protein.py,list_proteins.py,update_protein.py,resolve_protein_id.py}`
- Test: `backend/tests/unit/application/protein_catalog/__init__.py` (empty), `test_resolve_protein_id.py`

**Interfaces:**
- Consumes: `ProteinRepository`, `UnitOfWork`, `EventDispatcher`, `require_admin`/`require_authenticated`, `GLOBAL_WORKSPACE_ID`, `ProteinNames`, `ProteinExistence`, `CrossReference`.
- Produces: `CreateProtein`/`UpdateProtein` commands, `GetProtein`/`ListProteins` queries, `ResolveProteinId` query (pivots accession→primary, then entry_name; honors deleted via `NotFoundError`). All return `Result[..., DomainError]`.

- [ ] **Step 1: Write `create_protein.py`** — mirror `create_organism.py`, with a duplicate-accession guard via `find_by_accession`:

```python
"""Create a protein reference record (admin/service only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import ConflictError, DomainError


@dataclass(frozen=True, kw_only=True)
class CreateProteinCommand(Command):
    primary_accession: str
    organism_id: uuid.UUID
    sequence: str
    is_reviewed: bool = False
    secondary_accessions: list[str] = field(default_factory=list)
    entry_name: str | None = None
    protein_names: ProteinNames | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: list[str] = field(default_factory=list)
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: list[CrossReference] = field(default_factory=list)


class CreateProtein:
    def __init__(
        self, uow: UnitOfWork, repo: ProteinRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateProteinCommand, auth: AuthContext | None = None
    ) -> Result[Protein, DomainError]:
        require_admin(auth)
        async with self._uow:
            existing = await self._repo.find_by_accession(input.primary_accession)
            if existing is not None:
                return Failure(
                    ConflictError(f"Protein '{input.primary_accession}' already exists")
                )
            protein = Protein.create(
                primary_accession=input.primary_accession,
                organism_id=input.organism_id,
                sequence=input.sequence,
                is_reviewed=input.is_reviewed,
                secondary_accessions=list(input.secondary_accessions),
                entry_name=input.entry_name,
                protein_names=input.protein_names,
                strain_id=input.strain_id,
                gene_id=input.gene_id,
                seq_mass=input.seq_mass,
                seq_crc64=input.seq_crc64,
                protein_existence=input.protein_existence,
                keywords=list(input.keywords),
                entry_version=input.entry_version,
                sequence_version=input.sequence_version,
                cross_references=list(input.cross_references),
            )
            await self._repo.save(protein)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(protein)
```

- [ ] **Step 2: Write `get_protein.py`, `list_proteins.py`, `update_protein.py`** mirroring the Organism equivalents:
  - `get_protein.py` — `GetProteinQuery{accession: str}`, `require_authenticated`, `find_by_accession(input.accession)`, `NotFoundError("Protein", input.accession)`. (By accession, not UUID — accession is the UniProt natural key.)
  - `list_proteins.py` — `ListProteinsQuery{cursor_id, limit, organism_id, gene_id, is_reviewed, min_length, max_length}`, `require_authenticated`, `find_all(...)` with the `+1`/`next_cursor` slicing pattern from `list_organisms.py`; returns `Result[PageResult[Protein], DomainError]`.
  - `update_protein.py` — `UpdateProteinCommand{accession: str, ...optional fields with UNSET for nullables...}`, `require_admin`, load via `find_by_accession(input.accession)` → `NotFoundError` if missing, build `fields` dict, `protein.update(**fields)`, `save`, commit, dispatch.

- [ ] **Step 3: Write `resolve_protein_id.py`:**

```python
"""Resolve an input identifier to the canonical protein (accession or entry name)."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.shared.errors import DomainError, NotFoundError


@dataclass(frozen=True, kw_only=True)
class ResolveProteinIdQuery(Query):
    identifier: str


class ResolveProteinId:
    def __init__(self, uow: UnitOfWork, repo: ProteinRepository) -> None:
        self._uow, self._repo = uow, repo

    async def __call__(
        self, input: ResolveProteinIdQuery, auth: AuthContext | None = None
    ) -> Result[Protein, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            # Pivot through accession (primary, then secondary), then entry name.
            protein = await self._repo.find_by_accession(input.identifier)
            if protein is None:
                protein = await self._repo.find_by_entry_name(input.identifier)
            if protein is None:
                return Failure(NotFoundError("Protein", input.identifier))
            return Success(protein)
```

> **Deferred (note, not v1):** gene-name / Ensembl / RefSeq / ChEMBL-target resolution via cross-references — these resolve to *multiple* proteins and belong to the search endpoint, not single-canonical resolution.

- [ ] **Step 4: Write `tests/unit/application/protein_catalog/test_resolve_protein_id.py`** using an in-memory fake repository + the `FakeUnitOfWork`/`FakeAuth` pattern from `tests/unit/application/taxonomy/test_resolve_tax_id.py`. The fake implements `ProteinRepository`: keep a `dict[uuid, Protein]`; `find_by_accession` matches `primary_accession` then scans `secondary_accessions`; `find_by_entry_name` matches `entry_name`. Cover: resolve by primary accession (Success), resolve by secondary accession returns the owning primary protein, resolve by entry_name (Success), unknown identifier → `NotFoundError`.

```python
import uuid
from types import TracebackType
from typing import Self

import pytest
from returns.result import Failure, Success

from protcellar.application.protein_catalog.resolve_protein_id import (
    ResolveProteinId,
    ResolveProteinIdQuery,
)
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.errors import NotFoundError
from tests.fakes.fake_auth import FakeAuth

_AUTH = FakeAuth()


class FakeUnitOfWork:
    @property
    def is_active(self) -> bool:
        return False

    async def commit(self) -> list:
        return []

    async def rollback(self) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass


class FakeProteinRepository:
    def __init__(self, proteins: list[Protein]) -> None:
        self._by_id = {p.id: p for p in proteins}

    async def find_by_accession(self, accession: str) -> Protein | None:
        for p in self._by_id.values():
            if p.primary_accession == accession:
                return p
        for p in self._by_id.values():
            if accession in p.secondary_accessions:
                return p
        return None

    async def find_by_entry_name(self, entry_name: str) -> Protein | None:
        return next((p for p in self._by_id.values() if p.entry_name == entry_name), None)


def _protein(accession: str, **kw: object) -> Protein:
    return Protein.create(
        primary_accession=accession,
        organism_id=uuid.uuid4(),
        sequence="MKTAYIAKQR",
        is_reviewed=True,
        **kw,  # type: ignore[arg-type]
    )


def _uc(proteins: list[Protein]) -> ResolveProteinId:
    return ResolveProteinId(uow=FakeUnitOfWork(), repo=FakeProteinRepository(proteins))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_resolve_by_primary_accession() -> None:
    p = _protein("P0DTC2")
    result = await _uc([p])(ResolveProteinIdQuery(identifier="P0DTC2"), auth=_AUTH)
    assert isinstance(result, Success)
    assert result.unwrap().primary_accession == "P0DTC2"


@pytest.mark.asyncio
async def test_resolve_by_secondary_accession_returns_primary() -> None:
    p = _protein("P0DTC2", secondary_accessions=["P59594"])
    result = await _uc([p])(ResolveProteinIdQuery(identifier="P59594"), auth=_AUTH)
    assert isinstance(result, Success)
    assert result.unwrap().primary_accession == "P0DTC2"


@pytest.mark.asyncio
async def test_resolve_by_entry_name() -> None:
    p = _protein("P12345", entry_name="TEST_HUMAN")
    result = await _uc([p])(ResolveProteinIdQuery(identifier="TEST_HUMAN"), auth=_AUTH)
    assert isinstance(result, Success)
    assert result.unwrap().entry_name == "TEST_HUMAN"


@pytest.mark.asyncio
async def test_resolve_unknown_returns_not_found() -> None:
    result = await _uc([])(ResolveProteinIdQuery(identifier="Q99999"), auth=_AUTH)
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), NotFoundError)
```

Run: `cd backend && uv run pytest tests/unit/application/protein_catalog/test_resolve_protein_id.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/application/protein_catalog backend/tests/unit/application/protein_catalog
git commit -m "feat(protein-catalog): Protein use cases incl. accession/entry-name resolution"
```

---

### Task 6: `Protein` API routes (CRUD + search + FASTA + resolve) + DI wiring

**Files:**
- Create: `backend/src/protcellar/interface/routes/proteins.py`
- Modify: `infrastructure/di/_protein_catalog.py` (register the 5 Protein use cases), `interface/dependencies/_protein_catalog.py` (+ `*Dep` aliases), `interface/dependencies/__init__.py` (re-export), `interface/app.py` + `tests/api/conftest.py` (include the proteins router)
- Test: `backend/tests/api/test_proteins.py`

**Interfaces:**
- Consumes: the Task 5 use cases, `AuthDep`/`_get_use_case`, `IdentifierRegistry`, `PaginatedResponse`.
- Produces: `GET /api/v1/proteins/resolve/{identifier}`, `GET /api/v1/proteins`, `GET /api/v1/proteins/{accession}` (content-negotiated `?format=json|fasta`), `POST /api/v1/proteins`, `PATCH /api/v1/proteins/{accession}`. `ProteinResponse.from_domain(...)` with `uniprot_url` + structured `protein_names`, `cross_references`.

- [ ] **Step 1: Write `interface/routes/proteins.py`.** Mirror `organisms.py` structure. Key specifics:
  - `router = APIRouter(prefix="/api/v1/proteins", tags=["proteins"])`.
  - **Declare routes in this order** to avoid path-param shadowing: `resolve/{identifier}` (GET), `""` (GET list), `""` (POST create), `/{accession}` (GET), `/{accession}` (PATCH). (Like organisms.py, where `/resolve/{tax_id}` precedes `/{organism_id}`.)
  - `ProteinResponse` fields: `id, primary_accession, uniprot_url, secondary_accessions, entry_name, is_reviewed, protein_names (dict), organism_id, strain_id, gene_id, seq_length, seq_mass, seq_crc64, protein_existence, keywords, entry_version, sequence_version, cross_references (list), version`. `from_domain` builds `uniprot_url = IdentifierRegistry.default().resolve_url("uniprot", p.primary_accession)`, `protein_names = p.protein_names.to_dict()`, and `cross_references = [{"database": x.database, "accession": x.accession, "curie": x.to_curie(), "url": IdentifierRegistry.default().resolve_url(x.database, x.accession)} for x in p.cross_references]`.
  - **Request bodies:** `ProteinNamesBody{recommended: str | None = None, alternative: list[str] = [], submitted: list[str] = []}`; `CrossReferenceBody{database: str, accession: str, properties: dict[str,str] | None = None, evidence: str | None = None}`; `CreateProteinBody` (all the create fields, `protein_existence: ProteinExistence | None = None`); `UpdateProteinBody` (optional fields, `model_config = {"extra": "forbid"}`). The create/patch routes translate `protein_names`/`cross_references` bodies into the domain VOs (`ProteinNames(...)`, `CrossReference(...)`) when building the command.
  - **FASTA negotiation** on the get-by-accession route:

```python
from fastapi import Response
from fastapi.responses import PlainTextResponse

@router.get("/{accession}")
async def get_protein(
    accession: str,
    auth: AuthDep,
    use_case: GetProteinDep,
    format: str | None = None,
) -> Response:
    query = GetProteinQuery(accession=accession)
    protein = result_to_response(await use_case(query, auth=auth))
    if format == "fasta":
        return PlainTextResponse(protein.to_fasta(), media_type="text/x-fasta")
    return JSONResponse(content=ProteinResponse.from_domain(protein).model_dump(mode="json"))
```

  > Because this route returns either JSON or FASTA, return a bare `Response`/`JSONResponse` (no `response_model=`); use `.model_dump(mode="json")` so UUIDs/enums serialize. The other routes keep `response_model=ProteinResponse` as usual.

  - The PATCH route builds `UpdateProteinCommand` from `body.model_fields_set` (mirror `update_organism` route), converting `protein_names`/`cross_references`/`protein_existence` to domain types when present.

- [ ] **Step 2: Register the Protein use cases in `infrastructure/di/_protein_catalog.py`** — add `_protein_cmd`/`_protein_query` helpers (building `SQLAlchemyProteinRepository(uow)`) and `container.define(...)` for `CreateProtein`, `UpdateProtein` (commands) and `GetProtein`, `ListProteins`, `ResolveProteinId` (queries).

- [ ] **Step 3: Add the `*Dep` aliases** to `interface/dependencies/_protein_catalog.py` (`CreateProteinDep`, `UpdateProteinDep`, `GetProteinDep`, `ListProteinsDep`, `ResolveProteinIdDep`) and re-export them from `interface/dependencies/__init__.py`.

- [ ] **Step 4: Include the proteins router** in `interface/app.py` and `tests/api/conftest.py` (`_create_test_app`).

- [ ] **Step 5: Write `tests/api/test_proteins.py`:**

```python
import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient, tax_id: int, name: str) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": tax_id, "rank": "species", "scientific_name": name},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_get_fasta_and_resolve_protein(client: AsyncClient) -> None:
    organism_id = await _organism(client, 9606, "Homo sapiens")
    created = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P12345",
            "organism_id": organism_id,
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ",
            "is_reviewed": True,
            "entry_name": "TEST_HUMAN",
            "protein_names": {"recommended": "Test protein"},
            "secondary_accessions": ["Q99998"],
            "protein_existence": "evidence_at_protein_level",
            "sequence_version": 1,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["primary_accession"] == "P12345"
    assert body["uniprot_url"] is not None
    assert body["seq_length"] == len("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ")

    # JSON fetch by accession
    got = await client.get("/api/v1/proteins/P12345")
    assert got.status_code == 200
    assert got.json()["entry_name"] == "TEST_HUMAN"

    # FASTA negotiation
    fasta = await client.get("/api/v1/proteins/P12345", params={"format": "fasta"})
    assert fasta.status_code == 200
    assert fasta.text.startswith(">sp|P12345|TEST_HUMAN")

    # Resolve via secondary accession → canonical primary
    resolved = await client.get("/api/v1/proteins/resolve/Q99998")
    assert resolved.status_code == 200
    assert resolved.json()["primary_accession"] == "P12345"


@pytest.mark.asyncio
async def test_invalid_accession_rejected_and_search_filters(client: AsyncClient) -> None:
    organism_id = await _organism(client, 562, "Escherichia coli")

    bad = await client.post(
        "/api/v1/proteins",
        json={"primary_accession": "nope", "organism_id": organism_id,
              "sequence": "MKT", "is_reviewed": False},
    )
    assert bad.status_code == 422  # domain ValidationError → 422

    await client.post(
        "/api/v1/proteins",
        json={"primary_accession": "P0AEX9", "organism_id": organism_id,
              "sequence": "M" * 400, "is_reviewed": True},
    )
    listed = await client.get(
        "/api/v1/proteins", params={"organism_id": organism_id, "reviewed": "true",
                                    "min_length": 100}
    )
    assert listed.status_code == 200
    accs = [p["primary_accession"] for p in listed.json()["items"]]
    assert "P0AEX9" in accs
```

Run: `cd backend && uv run pytest tests/api/test_proteins.py -v` → PASS.

> The list route exposes query params `organism_id`, `gene_id`, `reviewed` (→ `is_reviewed`), `min_length`, `max_length`, `cursor`, `limit`, building `ListProteinsQuery`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar backend/tests/api/test_proteins.py
git commit -m "feat(protein-catalog): Protein API (CRUD, search, FASTA, ID-resolution) + DI wiring"
```

---

### Task 7: `Protein` bulk-import endpoint (provenance + idempotent upsert)

**Files:**
- Create: `application/protein_catalog/bulk_upsert_proteins.py`
- Modify: `interface/routes/proteins.py` (add `POST /api/v1/proteins/bulk`), `infrastructure/di/_protein_catalog.py`, `interface/dependencies/_protein_catalog.py` + `__init__.py`
- Test: `backend/tests/api/test_protein_bulk_import.py`

**Interfaces:**
- Consumes: `ProteinRepository`, `UnitOfWork`, `EventDispatcher`, `require_admin`.
- Produces: `BulkUpsertProteins` — accepts records each with provenance (`source`, `source_release`, `source_record_id`, `source_record_checksum`); **upserts keyed on `(source, source_record_id)`**, checksum-skip on unchanged; `dry_run` validates without persisting; returns `list[ItemResult]` (`{index, status: created|updated|skipped|failed, id?, error?}`). v1 is synchronous (the `202 + jobId` async path is deferred to the loader plan).

- [ ] **Step 1: Write `bulk_upsert_proteins.py`** — mirror `bulk_upsert_organisms.py` exactly, swapping the record fields and the create/update calls. The `ProteinImportRecord` carries the protein core fields **plus** `organism_id: uuid.UUID` (the loader resolves tax_id→organism_id via the organisms API before posting) and the four provenance fields. On the update branch, set `existing.update(sequence=..., is_reviewed=..., entry_name=..., protein_names=..., ...)`, then `existing.source_record_checksum/source_release/imported_at`. On create, `Protein.create(...)`, then set `protein.source = rec.source`, `protein.source_record_id`, `protein.source_record_checksum`, `protein.source_release`, `protein.imported_at = datetime.now(UTC)`. Catch `DomainError` per item → `failed`. `dry_run` returns before commit. Structure (header + control flow identical to `bulk_upsert_organisms.py`):

```python
@dataclass(frozen=True, kw_only=True)
class ProteinImportRecord:
    primary_accession: str
    organism_id: uuid.UUID
    sequence: str
    is_reviewed: bool
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    secondary_accessions: tuple[str, ...] = ()
    entry_name: str | None = None
    protein_names: ProteinNames | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: tuple[str, ...] = ()
    entry_version: int | None = None
    sequence_version: int | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertProteinsCommand(Command):
    records: tuple[ProteinImportRecord, ...]
    dry_run: bool = False


@dataclass(frozen=True, kw_only=True)
class ItemResult:
    index: int
    status: str  # created | updated | skipped | failed
    id: str | None = None
    error: str | None = None
```

The `BulkUpsertProteins.__call__` body is the same shape as `BulkUpsertOrganisms.__call__`:
- `require_admin(auth)`; iterate `enumerate(input.records)` inside `async with self._uow:`;
- `existing = await self._repo.find_by_source_record_id(rec.source, rec.source_record_id)`;
- if existing & `existing.source_record_checksum == rec.source_record_checksum` → `skipped`;
- elif existing → `existing.update(...)` with the mutable fields, set checksum/release/imported_at, `save` unless dry_run → `updated`;
- else → `Protein.create(...)`, set provenance attrs, `save` unless dry_run → `created`;
- `except DomainError as e: ... status="failed", error=e.message`;
- `if input.dry_run: return Success(results)`; else `events = await self._uow.commit()`, `await self._dispatcher.dispatch_all(events)`, `return Success(results)`.

- [ ] **Step 2: Add `POST /api/v1/proteins/bulk`** to `routes/proteins.py` — mirror the organisms bulk route: `BulkRecordBody` (protein fields + `organism_id: uuid.UUID` + provenance, with `protein_names`/`cross_references` optional), `BulkUpsertBody{records: list[...], dry_run: bool = False}`, builds `BulkUpsertProteinsCommand`, returns `BulkUpsertResponse{results, summary{created,updated,skipped,failed}}`. Declare the POST `/bulk` route (POST does not collide with the GET `/{accession}`, but declare it before `create` for clarity).

- [ ] **Step 3: Register `BulkUpsertProteins`** in `_protein_catalog.py` (command helper) + add `BulkUpsertProteinsDep` to `_protein_catalog.py` deps + re-export from `__init__.py`.

- [ ] **Step 4: Write `tests/api/test_protein_bulk_import.py`:**

```python
import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_bulk_upsert_is_idempotent(client: AsyncClient) -> None:
    organism_id = await _organism(client)
    rec = {
        "primary_accession": "P0DP23", "organism_id": organism_id,
        "sequence": "MADQLTEEQIAEFKEAFSLF", "is_reviewed": True,
        "source": "uniprot", "source_release": "2026_02",
        "source_record_id": "P0DP23", "source_record_checksum": "crc1",
    }
    first = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert first.status_code == 200
    assert first.json()["summary"]["created"] == 1

    # Same checksum → skipped
    second = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert second.json()["summary"]["skipped"] == 1

    # Changed checksum → updated
    rec2 = {**rec, "source_record_checksum": "crc2", "sequence": "MADQLTEEQIAEFKEAFSLFD"}
    third = await client.post("/api/v1/proteins/bulk", json={"records": [rec2]})
    assert third.json()["summary"]["updated"] == 1
    got = await client.get("/api/v1/proteins/P0DP23")
    assert got.json()["seq_length"] == len("MADQLTEEQIAEFKEAFSLFD")


@pytest.mark.asyncio
async def test_bulk_dry_run_does_not_persist(client: AsyncClient) -> None:
    organism_id = await _organism(client)
    rec = {
        "primary_accession": "Q8N158", "organism_id": organism_id,
        "sequence": "MKTAYIAKQR", "is_reviewed": False,
        "source": "uniprot", "source_release": "2026_02",
        "source_record_id": "Q8N158", "source_record_checksum": "crc1",
    }
    dry = await client.post("/api/v1/proteins/bulk", json={"records": [rec], "dry_run": True})
    assert dry.json()["summary"]["created"] == 1
    # Not persisted
    missing = await client.get("/api/v1/proteins/Q8N158")
    assert missing.status_code == 404
```

Run: `cd backend && uv run pytest tests/api/test_protein_bulk_import.py -v` → PASS.

- [ ] **Step 5: Final commit + full suite**

Run: `make test-all` → all unit + api + import-linter green.
Run: `make lint` → ruff + ruff format + mypy clean.

```bash
git add backend/src/protcellar backend/tests
git commit -m "feat(protein-catalog): idempotent bulk-upsert endpoint for proteins with provenance"
```

---

## Self-Review (run after implementing)

- **Spec coverage:** Implements spec §5.2 (Protein: UniProt core + sequence/CRC64/mass + organism/strain/gene links + secondary accessions + protein_names VO + PE + keywords + entry/sequence versions + cross_references; Gene: primary_name/synonyms/organism + ncbi/ensembl/hgnc ids + cross_references), §5.5 (generic `CrossReference` VO reused; identifier registry renders resolvable URLs in DTOs), §6 (per-aggregate CRUD; search by accession/gene/organism/reviewed/length; `GET /proteins/{accession}` content-negotiated json/fasta; ID-resolution endpoint pivoting through accession + secondary + entry_name; bulk import with `(source, source_record_id)` upsert + checksum-skip + dry_run), §7 (provenance columns via `ProvenanceMixin` + idempotent reload), and the §4 tenancy nuance (Protein/Gene = shared reference under GLOBAL).
- **Deferred (per spec "later" / scoped out of v1):** organism-search *including descendants* (exact organism_id match only — descendant expansion needs the taxonomy tree/ltree accelerator, a documented later concern); fuzzy protein-name search over the JSON names block (a dedicated search index is a later concern); gene-name / Ensembl / RefSeq / ChEMBL-target ID-resolution (multi-protein → search, not single-canonical resolve); async `202 + jobId` bulk path + `Idempotency-Key`/429 backoff (loader-plan concern; v1 bulk is synchronous); Gene bulk-import endpoint (genes are created explicitly or as a future side-effect of Swiss-Prot import); CRC64 computation (the loader/UniProt supplies `seq_crc64`; the domain stores it).
- **Type/name consistency to verify during implementation:** `Protein`/`Gene` use `ProvenanceMixin` cleanly (no `source` enum, unlike `Organism` — confirm no name clash); `find_by_source_record_id` queries `ProteinModel.source`/`GeneModel.source` (the `ProvenanceMixin.source` column); the get-by-accession route returns a bare `Response` (no `response_model`) so JSON/FASTA negotiation works; route-declaration order puts `/resolve/{identifier}` before `/{accession}`; the `_xref_json.py` helper module is imported by both repositories (no repo→repo import); `ProteinNames.from_dict(None)` returns an empty VO (defensive against null JSON columns); the test DB is real Postgres so `ARRAY` + GIN index are valid.
- **Bounded-context independence:** the protein_catalog **domain** imports only `domain.shared.*` (entity, errors, events, cross_reference, global_workspace) and its own modules — **never** `domain.taxonomy.*` (all cross-context links are `uuid.UUID` FKs). The import-linter `independence` contract stays commented out until Plan 3 (Target) lands and re-enables it listing all five contexts.
- **Open follow-ups for Plan 3 (Target):** `Target` + `TargetComponent` will reference `Protein` by id (FK→`proteins.id`); the single-vs-complex cardinality invariant; re-enable the `independence` import-linter contract; keep `chembl_id` on Target for chem-cellar reconciliation (interop seam §2).
```
