# prot-cellar Taxonomy Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Prerequisite:** The Foundation plan (`2026-06-18-foundation.md`) must be fully implemented and green. This plan builds on its base classes, repository, UoW, event dispatcher, identifier registry, DI, and the `Organization` exemplar slice.

**Goal:** Implement the Taxonomy bounded context — `Organism` (NCBI-Taxonomy-aligned, adjacency-list hierarchy with multi-name support and merged/deleted handling), `Strain` (workspace-scoped, anchored to a species Organism), and a lite `Proteome` — each as a full domain→application→infrastructure→interface vertical slice, plus a bulk-import endpoint with provenance.

**Architecture:** Reference data (`Organism`, `OrganismName`, `Proteome`) is **shared and workspace-agnostic**, stored under a reserved `GLOBAL_WORKSPACE_ID` sentinel so it reuses every piece of foundation machinery (events, audit, optimistic concurrency, base repository) unchanged; mutating it requires admin/service auth, not workspace membership. `Strain` is genuinely tenant-private and carries a real `workspace_id`. The taxonomy tree is an adjacency list (`parent_id` self-FK) mirroring NCBI exactly. This plan resolves spec open-question Q1 (reference-data tenancy) via the GLOBAL sentinel.

**Tech Stack:** Same as Foundation. No new runtime dependencies (Biopython, already added, is used by the separate loader, not here).

## Global Constraints

- All Foundation Global Constraints apply (workspace scoping, auth-guards-first, Railway, optimistic concurrency, ruff/mypy, commit-per-task).
- **Reference vs tenant data:** `Organism`/`OrganismName`/`Proteome` use `workspace_id = GLOBAL_WORKSPACE_ID` (`uuid.UUID(int=0)`); their use cases guard with `require_admin(auth)` and **do not** call `require_same_workspace`. `Strain` uses a real `workspace_id` and follows the standard `require_editor` + `require_same_workspace` pattern (exactly like `Organization`).
- **Rank is a validated string, not a DB enum** (NCBI has 40+ ranks; GTDB has 7) — column `String(32)`, validated against `KNOWN_RANKS` with unknown values permitted (logged, not rejected).
- **Provenance columns** (`source`, `source_release`, `source_record_id`, `source_record_checksum`, `imported_at`) go on every reference aggregate's SA model via `ProvenanceMixin`.
- **Mechanical CRUD (use cases, routes, DI wiring) mirrors the `Organization` exemplar exactly** — same `*Command`/`*Query` shapes, `Result` returns, `from_domain` response DTOs, `result_to_response`, `_get_use_case` Lagom registration. Only the fields differ.

---

## File Structure

```
backend/src/protcellar/
  domain/
    shared/global_workspace.py                 # NEW: GLOBAL_WORKSPACE_ID sentinel
    taxonomy/
      enums.py            # TaxonomyRank consts, NameClass, OrganismSource, ProteomeType, StrainRelationship
      organism.py         # Organism aggregate + OrganismName entity
      strain.py           # Strain aggregate
      proteome.py         # Proteome aggregate
      events.py           # OrganismCreated/Updated, StrainCreated/Updated, ProteomeCreated/Updated
      repository.py       # OrganismRepository, StrainRepository, ProteomeRepository protocols
  application/
    taxonomy/
      create_organism.py update_organism.py get_organism.py list_organisms.py resolve_tax_id.py
      bulk_upsert_organisms.py
      create_strain.py update_strain.py get_strain.py list_strains.py
      create_proteome.py get_proteome.py list_proteomes.py
  infrastructure/persistence/sqlalchemy/
    provenance.py                               # NEW: ProvenanceMixin
    taxonomy/
      models.py            # OrganismModel, OrganismNameModel, StrainModel, ProteomeModel
      organism_repository.py strain_repository.py proteome_repository.py
  interface/
    routes/organisms.py strains.py proteomes.py
    dependencies/_taxonomy.py
  (modify) interface/app.py                     # include the three routers
  (modify) alembic env model aggregator         # import taxonomy models
tests/
  unit/domain/taxonomy/test_organism.py test_strain.py test_proteome.py
  api/test_organisms.py test_strains.py test_proteomes.py test_organism_bulk_import.py
```

---

### Task 1: Taxonomy shared — GLOBAL sentinel, provenance mixin, enums

**Files:**
- Create: `backend/src/protcellar/domain/shared/global_workspace.py`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/provenance.py`
- Create: `backend/src/protcellar/domain/taxonomy/enums.py`
- Test: `tests/unit/domain/taxonomy/test_enums.py`

**Interfaces:**
- Produces: `GLOBAL_WORKSPACE_ID: uuid.UUID`; `ProvenanceMixin` (SA columns `source`, `source_release`, `source_record_id`, `source_record_checksum`, `imported_at`); `KNOWN_RANKS: frozenset[str]`, `NameClass`, `OrganismSource`, `ProteomeType`, `StrainRelationship` enums.

- [ ] **Step 1: Write `domain/shared/global_workspace.py`:**

```python
"""Reserved workspace sentinel for shared, workspace-agnostic reference data."""

from __future__ import annotations

import uuid

# Reference data (organisms, proteins, proteomes) is shared across all tenants.
# It is stored under this reserved workspace id so it reuses all workspace-scoped
# machinery (events, audit, base repository) without special-casing.
GLOBAL_WORKSPACE_ID: uuid.UUID = uuid.UUID(int=0)
```

- [ ] **Step 2: Write `infrastructure/persistence/sqlalchemy/provenance.py`:**

```python
"""Provenance mixin for imported reference data (spec §7 baseline)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class ProvenanceMixin:
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_record_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Write `domain/taxonomy/enums.py`:**

```python
"""Taxonomy controlled vocabularies."""

from __future__ import annotations

from enum import StrEnum

# Common NCBI ranks — NOT exhaustive and NOT a DB enum. Unknown ranks are allowed
# (stored as-is) so GTDB's fixed 7 ranks and NCBI's long tail both fit.
KNOWN_RANKS: frozenset[str] = frozenset(
    {
        "superkingdom", "kingdom", "phylum", "class", "order", "family",
        "genus", "species", "subspecies", "strain", "varietas", "forma",
        "clade", "no rank",
    }
)


class NameClass(StrEnum):
    SCIENTIFIC_NAME = "scientific_name"
    COMMON_NAME = "common_name"
    GENBANK_COMMON_NAME = "genbank_common_name"
    SYNONYM = "synonym"
    AUTHORITY = "authority"
    EQUIVALENT_NAME = "equivalent_name"
    ACRONYM = "acronym"
    BLAST_NAME = "blast_name"
    UNIPROT_MNEMONIC = "uniprot_mnemonic"  # e.g. HUMAN, ECOLI


class OrganismSource(StrEnum):
    NCBI = "ncbi"
    GTDB = "gtdb"
    LOCAL = "local"


class ProteomeType(StrEnum):
    REFERENCE = "reference"
    REPRESENTATIVE = "representative"
    REDUNDANT = "redundant"
    EXCLUDED = "excluded"


class StrainRelationship(StrEnum):
    """How a Strain relates to its anchoring Organism nodes."""

    SPECIES_ANCHOR = "species_anchor"
```

- [ ] **Step 4: Write `tests/unit/domain/taxonomy/test_enums.py`:**

```python
from protcellar.domain.taxonomy.enums import KNOWN_RANKS, NameClass


def test_known_ranks_contains_species() -> None:
    assert "species" in KNOWN_RANKS


def test_name_class_values() -> None:
    assert NameClass.UNIPROT_MNEMONIC.value == "uniprot_mnemonic"
```

Run: `cd backend && uv run pytest tests/unit/domain/taxonomy/test_enums.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/shared/global_workspace.py \
        backend/src/protcellar/infrastructure/persistence/sqlalchemy/provenance.py \
        backend/src/protcellar/domain/taxonomy/enums.py backend/tests/unit/domain/taxonomy
git commit -m "feat(taxonomy): GLOBAL workspace sentinel, provenance mixin, taxonomy enums"
```

---

### Task 2: Organism aggregate (domain) + OrganismName + events + repository protocol

**Files:**
- Create: `backend/src/protcellar/domain/taxonomy/organism.py`, `events.py`, `repository.py`
- Test: `tests/unit/domain/taxonomy/test_organism.py`

**Interfaces:**
- Produces:
  - `OrganismName` entity `{name, name_class, unique_name?, is_preferred}`.
  - `Organism` aggregate: fields `ncbi_tax_id: int | None`, `parent_id: uuid.UUID | None`, `rank: str`, `scientific_name: str`, `division: str | None`, `is_merged: bool`, `merged_into_id: uuid.UUID | None`, `is_deleted: bool`, `source: OrganismSource`, `source_version: str | None`, `names: list[OrganismName]`, plus base `id`/`version`/`workspace_id` (= GLOBAL). Factory `Organism.create(...)`, `update(**fields)`, `add_name(...)`, `mark_merged_into(target_id)`, `mark_deleted()`.
  - Events `OrganismCreated`, `OrganismUpdated`.
  - `OrganismRepository` protocol: `find_by_id_in_workspace`, `find_by_tax_id(tax_id)`, `find_children(parent_id)`, `find_by_name(name)`, `save`, `find_all(cursor_id?, limit?)`.

- [ ] **Step 1: Write the failing test** `tests/unit/domain/taxonomy/test_organism.py`:

```python
import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.events import OrganismCreated
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def test_create_human_node() -> None:
    org = Organism.create(
        ncbi_tax_id=9606, rank="species", scientific_name="Homo sapiens",
        source=OrganismSource.NCBI,
    )
    assert org.ncbi_tax_id == 9606
    assert org.workspace_id == GLOBAL_WORKSPACE_ID
    assert org.version == 1
    # scientific name is auto-added as a name row
    assert any(n.name_class == NameClass.SCIENTIFIC_NAME and n.name == "Homo sapiens"
               for n in org.names)
    events = org.collect_events()
    assert len(events) == 1 and isinstance(events[0], OrganismCreated)


def test_create_requires_scientific_name() -> None:
    with pytest.raises(ValidationError):
        Organism.create(ncbi_tax_id=1, rank="no rank", scientific_name="  ",
                        source=OrganismSource.NCBI)


def test_add_common_name() -> None:
    org = Organism.create(ncbi_tax_id=9606, rank="species", scientific_name="Homo sapiens",
                          source=OrganismSource.NCBI)
    org.add_name("human", NameClass.COMMON_NAME)
    assert any(n.name == "human" and n.name_class == NameClass.COMMON_NAME for n in org.names)


def test_mark_merged_into_redirect() -> None:
    org = Organism.create(ncbi_tax_id=12345, rank="species", scientific_name="Old name",
                          source=OrganismSource.NCBI)
    target = uuid.uuid4()
    org.mark_merged_into(target)
    assert org.is_merged is True
    assert org.merged_into_id == target
```

- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/unit/domain/taxonomy/test_organism.py -v` → FAIL.

- [ ] **Step 3: Write `domain/taxonomy/events.py`:**

```python
"""Taxonomy domain events."""

from __future__ import annotations

from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class OrganismCreated(DomainEvent):
    scientific_name: str
    ncbi_tax_id: int | None


@dataclass(frozen=True, kw_only=True)
class OrganismUpdated(DomainEvent):
    pass
```

- [ ] **Step 4: Write `domain/taxonomy/organism.py`:**

```python
"""Organism aggregate — a mirror of an NCBI Taxonomy node (shared reference data)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.events import OrganismCreated, OrganismUpdated


@dataclass
class OrganismName:
    """A name for an organism (NCBI names.dmp row)."""

    name: str
    name_class: NameClass
    unique_name: str | None = None
    is_preferred: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)


class Organism(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        ncbi_tax_id: int | None = None,
        parent_id: uuid.UUID | None = None,
        rank: str,
        scientific_name: str,
        division: str | None = None,
        is_merged: bool = False,
        merged_into_id: uuid.UUID | None = None,
        is_deleted: bool = False,
        source: OrganismSource = OrganismSource.NCBI,
        source_version: str | None = None,
        names: list[OrganismName] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not scientific_name or not scientific_name.strip():
            raise ValidationError("Organism scientific_name must not be empty")
        if not rank or not rank.strip():
            raise ValidationError("Organism rank must not be empty")
        # Reference data lives under the reserved GLOBAL workspace.
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.ncbi_tax_id = ncbi_tax_id
        self.parent_id = parent_id
        self.rank = rank.strip()
        self.scientific_name = scientific_name.strip()
        self.division = division
        self.is_merged = is_merged
        self.merged_into_id = merged_into_id
        self.is_deleted = is_deleted
        self.source = source
        self.source_version = source_version
        self.names: list[OrganismName] = names if names is not None else []

    @classmethod
    def create(
        cls,
        *,
        ncbi_tax_id: int | None,
        rank: str,
        scientific_name: str,
        source: OrganismSource = OrganismSource.NCBI,
        parent_id: uuid.UUID | None = None,
        division: str | None = None,
        source_version: str | None = None,
    ) -> Organism:
        org = cls(
            ncbi_tax_id=ncbi_tax_id,
            rank=rank,
            scientific_name=scientific_name,
            source=source,
            parent_id=parent_id,
            division=division,
            source_version=source_version,
        )
        # The scientific name is also a name row (NCBI models it this way).
        org.names.append(
            OrganismName(
                name=org.scientific_name,
                name_class=NameClass.SCIENTIFIC_NAME,
                is_preferred=True,
            )
        )
        org.register_event(
            OrganismCreated(
                aggregate_id=org.id,
                aggregate_type="Organism",
                workspace_id=org.workspace_id,
                scientific_name=org.scientific_name,
                ncbi_tax_id=org.ncbi_tax_id,
            )
        )
        return org

    def add_name(
        self, name: str, name_class: NameClass, *, unique_name: str | None = None
    ) -> None:
        if not name or not name.strip():
            raise ValidationError("Organism name must not be empty")
        self.names.append(
            OrganismName(name=name.strip(), name_class=name_class, unique_name=unique_name)
        )
        self._touch()

    def update(self, **fields: Any) -> None:
        if "scientific_name" in fields:
            value = fields["scientific_name"]
            if not value or not str(value).strip():
                raise ValidationError("Organism scientific_name must not be empty")
            self.scientific_name = str(value).strip()
        if "rank" in fields:
            self.rank = str(fields["rank"]).strip()
        if "parent_id" in fields:
            self.parent_id = fields["parent_id"]
        if "division" in fields:
            self.division = fields["division"]
        if "source_version" in fields:
            self.source_version = fields["source_version"]
        self._touch()

    def mark_merged_into(self, target_id: uuid.UUID) -> None:
        self.is_merged = True
        self.merged_into_id = target_id
        self._touch()

    def mark_deleted(self) -> None:
        self.is_deleted = True
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            OrganismUpdated(
                aggregate_id=self.id,
                aggregate_type="Organism",
                workspace_id=self.workspace_id,
            )
        )
```

- [ ] **Step 5: Write `domain/taxonomy/repository.py`** (protocols for all three aggregates; Strain/Proteome bodies filled in later tasks but declare now):

```python
"""Taxonomy repository protocols."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.taxonomy.organism import Organism


@runtime_checkable
class OrganismRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Organism | None: ...

    async def find_by_tax_id(self, tax_id: int) -> Organism | None: ...

    async def find_children(self, parent_id: uuid.UUID) -> list[Organism]: ...

    async def find_by_name(self, name: str) -> list[Organism]: ...

    async def find_all(
        self, *, cursor_id: uuid.UUID | None = None, limit: int | None = None
    ) -> list[Organism]: ...

    async def save(self, aggregate: Organism) -> None: ...
```

- [ ] **Step 6: Run test to verify it passes** — `uv run pytest tests/unit/domain/taxonomy/test_organism.py -v` → PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/protcellar/domain/taxonomy backend/tests/unit/domain/taxonomy/test_organism.py
git commit -m "feat(taxonomy): Organism aggregate with names, merged/deleted, events, repo protocol"
```

---

### Task 3: Organism persistence (SA models, repository, migration)

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/taxonomy/models.py`, `organism_repository.py`
- Modify: the alembic model aggregator to import taxonomy models
- Create: migration `xxxx_organism_tables.py`
- Test: covered by the api/integration tests in Task 5 (repository behavior is exercised end-to-end there)

**Interfaces:**
- Consumes: `Base`, `EntityModelMixin`, `VersionMixin`, `ProvenanceMixin`, `SQLAlchemyRepository`, `AsyncUnitOfWork`, `Organism`, `OrganismName`.
- Produces: `OrganismModel` (self-referential `parent_id`), `OrganismNameModel`, `SQLAlchemyOrganismRepository` implementing `OrganismRepository`.

- [ ] **Step 1: Write `taxonomy/models.py`:**

```python
"""SQLAlchemy models for the taxonomy context."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)
from protcellar.infrastructure.persistence.sqlalchemy.provenance import ProvenanceMixin


class OrganismModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin, ProvenanceMixin):
    __tablename__ = "organisms"

    ncbi_tax_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True, index=True
    )
    rank: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scientific_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    division: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_merged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    names: Mapped[list[OrganismNameModel]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", foreign_keys="OrganismNameModel.organism_id"
    )


class OrganismNameModel(Base, EntityModelMixin):
    __tablename__ = "organism_names"
    __table_args__ = (UniqueConstraint("organism_id", "name_class", "name", name="uq_orgname"),)

    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    name_class: Mapped[str] = mapped_column(String(32), nullable=False)
    unique_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

> The `merged_into_id` self-FK has no `relationship` (avoids ambiguity with `parent_id`); resolution is done by id lookup in the repository. `names` uses `selectin` eager loading so `_to_domain` can map them without a lazy-load round trip.

- [ ] **Step 2: Write `taxonomy/organism_repository.py`** implementing the mapping contract + the bespoke finders:

```python
"""SQLAlchemy Organism repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.organism import Organism, OrganismName
from protcellar.domain.taxonomy.repository import OrganismRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import (
    OrganismModel,
    OrganismNameModel,
)


class SQLAlchemyOrganismRepository(
    SQLAlchemyRepository[Organism, OrganismModel], OrganismRepository
):
    model_class = OrganismModel

    def _to_domain(self, model: OrganismModel) -> Organism:
        org = Organism(
            id=model.id,
            ncbi_tax_id=model.ncbi_tax_id,
            parent_id=model.parent_id,
            rank=model.rank,
            scientific_name=model.scientific_name,
            division=model.division,
            is_merged=model.is_merged,
            merged_into_id=model.merged_into_id,
            is_deleted=model.is_deleted,
            source=OrganismSource(model.source),
            source_version=model.source_version,
            names=[
                OrganismName(
                    id=n.id,
                    name=n.name,
                    name_class=NameClass(n.name_class),
                    unique_name=n.unique_name,
                    is_preferred=n.is_preferred,
                )
                for n in model.names
            ],
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
        return org

    def _to_model(self, aggregate: Organism) -> OrganismModel:
        model = OrganismModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            ncbi_tax_id=aggregate.ncbi_tax_id,
            parent_id=aggregate.parent_id,
            rank=aggregate.rank,
            scientific_name=aggregate.scientific_name,
            division=aggregate.division,
            is_merged=aggregate.is_merged,
            merged_into_id=aggregate.merged_into_id,
            is_deleted=aggregate.is_deleted,
            source=aggregate.source.value,
            source_version=aggregate.source_version,
            version=aggregate.version,
        )
        model.names = [self._name_to_model(n) for n in aggregate.names]
        return model

    def _update_model(self, model: OrganismModel, aggregate: Organism) -> None:
        model.ncbi_tax_id = aggregate.ncbi_tax_id
        model.parent_id = aggregate.parent_id
        model.rank = aggregate.rank
        model.scientific_name = aggregate.scientific_name
        model.division = aggregate.division
        model.is_merged = aggregate.is_merged
        model.merged_into_id = aggregate.merged_into_id
        model.is_deleted = aggregate.is_deleted
        model.source = aggregate.source.value
        model.source_version = aggregate.source_version
        # Replace the names collection wholesale (delete-orphan handles removals)
        model.names = [self._name_to_model(n) for n in aggregate.names]

    @staticmethod
    def _name_to_model(n: OrganismName) -> OrganismNameModel:
        return OrganismNameModel(
            id=n.id,
            name=n.name,
            name_class=n.name_class.value,
            unique_name=n.unique_name,
            is_preferred=n.is_preferred,
        )

    async def find_by_tax_id(self, tax_id: int) -> Organism | None:
        stmt = select(OrganismModel).where(OrganismModel.ncbi_tax_id == tax_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_children(self, parent_id: uuid.UUID) -> list[Organism]:
        stmt = select(OrganismModel).where(OrganismModel.parent_id == parent_id).order_by(
            OrganismModel.scientific_name
        )
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_by_name(self, name: str) -> list[Organism]:
        stmt = (
            select(OrganismModel)
            .join(OrganismNameModel, OrganismNameModel.organism_id == OrganismModel.id)
            .where(OrganismNameModel.name.ilike(f"%{name}%"))
            .distinct()
            .limit(50)
        )
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_all(
        self, *, cursor_id: uuid.UUID | None = None, limit: int | None = None
    ) -> list[Organism]:
        stmt = select(OrganismModel).order_by(OrganismModel.id)
        if cursor_id is not None:
            stmt = stmt.where(OrganismModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
```

> `_to_domain_tracked` and `_session` come from the `SQLAlchemyRepository` base (Foundation Task 4). If the base's `_to_model`/`save` flow doesn't yet handle a child `names` collection on INSERT/UPDATE, verify against chem-cellar's base — chem-cellar aggregates with owned collections (e.g. AuditOperation entries, protocol readouts) prove the pattern; follow whichever approach the ported base uses (the base `save()` adds the model with its `names` already attached).

- [ ] **Step 3: Register taxonomy models with the alembic aggregator** (add `import protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models  # noqa` to the metadata aggregator module from Foundation Task 8).

- [ ] **Step 4: Generate and apply the migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "organism tables"`
Run: `uv run alembic upgrade head`
Expected: `organisms` (with self-FKs `parent_id`, `merged_into_id`) and `organism_names` tables created.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/persistence/sqlalchemy/taxonomy \
        backend/alembic/versions
git commit -m "feat(taxonomy): Organism SA models (adjacency + names) and repository"
```

---

### Task 4: Organism application use cases

**Files:**
- Create: `backend/src/protcellar/application/taxonomy/{create_organism.py,update_organism.py,get_organism.py,list_organisms.py,resolve_tax_id.py}`
- Test: `tests/unit/application/taxonomy/test_resolve_tax_id.py` (the one with non-trivial logic; CRUD use cases are covered by api tests)

**Interfaces:**
- Consumes: `OrganismRepository`, `UnitOfWork`, `EventDispatcher`, `require_admin`, `GLOBAL_WORKSPACE_ID`.
- Produces: `CreateOrganism`/`UpdateOrganism` (commands), `GetOrganism`/`ListOrganisms` (queries), `ResolveTaxId` (query that follows `merged_into_id` redirects and surfaces deleted tombstones). All return `Result[..., DomainError]`.

- [ ] **Step 1: Write `create_organism.py`** — mirror the `CreateOrganization` use case, but guard with `require_admin(auth)` only (reference data; no `require_same_workspace`). Command carries the organism fields (no `workspace_id` — it's GLOBAL). On conflict (existing `ncbi_tax_id`), return `Failure(ConflictError(...))`:

```python
"""Create an organism reference node (admin/service only)."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import ConflictError, DomainError
from protcellar.domain.taxonomy.enums import OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class CreateOrganismCommand(Command):
    ncbi_tax_id: int | None
    rank: str
    scientific_name: str
    source: OrganismSource = OrganismSource.NCBI
    division: str | None = None
    source_version: str | None = None


class CreateOrganism:
    def __init__(
        self, uow: UnitOfWork, repo: OrganismRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateOrganismCommand, auth: AuthContext | None = None
    ) -> Result[Organism, DomainError]:
        require_admin(auth)
        async with self._uow:
            if input.ncbi_tax_id is not None:
                existing = await self._repo.find_by_tax_id(input.ncbi_tax_id)
                if existing is not None:
                    return Failure(
                        ConflictError(f"Organism with tax_id {input.ncbi_tax_id} already exists")
                    )
            org = Organism.create(
                ncbi_tax_id=input.ncbi_tax_id,
                rank=input.rank,
                scientific_name=input.scientific_name,
                source=input.source,
                division=input.division,
                source_version=input.source_version,
            )
            await self._repo.save(org)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(org)
```

- [ ] **Step 2: Write `update_organism.py`, `get_organism.py`, `list_organisms.py`** mirroring the Organization equivalents (admin guard for update; queries take no auth requirement beyond `require_authenticated` — reads of reference data are allowed for any authenticated user, so pass `auth` through and call nothing, or `require_authenticated(auth)`). `GetOrganism` loads via `find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, id)`; `ListOrganisms` calls `find_all(cursor_id, limit)`.

- [ ] **Step 3: Write `resolve_tax_id.py`** (the novel one) — resolves an NCBI tax id to the live organism, following one merge redirect:

```python
"""Resolve an NCBI tax id to its live organism, following merge redirects."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, GoneError, NotFoundError
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class ResolveTaxIdQuery(Query):
    tax_id: int


class ResolveTaxId:
    def __init__(self, uow: UnitOfWork, repo: OrganismRepository) -> None:
        self._uow, self._repo = uow, repo

    async def __call__(
        self, input: ResolveTaxIdQuery, auth: AuthContext | None = None
    ) -> Result[Organism, DomainError]:
        async with self._uow:
            org = await self._repo.find_by_tax_id(input.tax_id)
            if org is None:
                return Failure(NotFoundError("Organism", str(input.tax_id)))
            if org.is_deleted:
                return Failure(GoneError(f"tax_id {input.tax_id} was deleted from NCBI Taxonomy"))
            if org.is_merged and org.merged_into_id is not None:
                target = await self._repo.find_by_id_in_workspace(
                    org.workspace_id, org.merged_into_id
                )
                if target is not None:
                    return Success(target)
            return Success(org)
```

- [ ] **Step 4: Write the resolve test** `tests/unit/application/taxonomy/test_resolve_tax_id.py` using an in-memory fake repository (mirror chem-cellar's `tests/fakes` repo style — a dict-backed fake implementing `OrganismRepository`). Cover: live hit, deleted → `GoneError`, merged → returns target.

Run: `uv run pytest tests/unit/application/taxonomy/test_resolve_tax_id.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/application/taxonomy backend/tests/unit/application/taxonomy
git commit -m "feat(taxonomy): Organism use cases incl. merge-aware tax-id resolution"
```

---

### Task 5: Organism API routes + DI wiring + search

**Files:**
- Create: `backend/src/protcellar/interface/routes/organisms.py`
- Create: `backend/src/protcellar/interface/dependencies/_taxonomy.py`
- Modify: `backend/src/protcellar/interface/app.py` (include `organisms` router)
- Test: `tests/api/test_organisms.py`

**Interfaces:**
- Consumes: the use cases from Task 4, `AuthDep`/`get_container`/`_get_use_case` from Foundation `_core.py`, `IdentifierRegistry`.
- Produces: `GET /api/v1/organisms/{id}`, `GET /api/v1/organisms?cursor=&limit=&name=&rank=`, `GET /api/v1/organisms/resolve/{tax_id}`, `POST /api/v1/organisms`, `PATCH /api/v1/organisms/{id}`. Response DTO `OrganismResponse.from_domain(...)` including `names` and a resolvable `ncbi_url`.

- [ ] **Step 1: Write `interface/routes/organisms.py`** mirroring `organizations.py`. Response model carries `id, ncbi_tax_id, parent_id, rank, scientific_name, division, is_merged, merged_into_id, is_deleted, source, version, names[]`. The create/patch routes build the `CreateOrganismCommand`/`UpdateOrganismCommand` and call the use case via `result_to_response`. The list route reads `name`/`rank` query params and filters (call `find_by_name` when `name` present, else `find_all`). The resolve route calls `ResolveTaxId`.

- [ ] **Step 2: Write `_taxonomy.py`** DI wiring — register `CreateOrganism`, `UpdateOrganism`, `GetOrganism`, `ListOrganisms`, `ResolveTaxId` into Lagom exactly like `_workspace_config.py` registers the Organization use cases (fresh `AsyncUnitOfWork` per request + `SQLAlchemyOrganismRepository(uow)` + `EventDispatcher` for commands; uow + repo only for queries). Define the `*Dep` type aliases.

- [ ] **Step 3: Include the router** in `app.py`.

- [ ] **Step 4: Write `tests/api/test_organisms.py`:**

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_resolve_organism(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["scientific_name"] == "Homo sapiens"
    assert any(n["name_class"] == "scientific_name" for n in body["names"])

    resolved = await client.get("/api/v1/organisms/resolve/9606")
    assert resolved.status_code == 200
    assert resolved.json()["ncbi_tax_id"] == 9606


@pytest.mark.asyncio
async def test_search_by_name(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 562, "rank": "species", "scientific_name": "Escherichia coli"},
    )
    resp = await client.get("/api/v1/organisms", params={"name": "coli"})
    assert resp.status_code == 200
    assert any(o["scientific_name"] == "Escherichia coli" for o in resp.json())
```

Run: `make test-api` (or `uv run pytest tests/api/test_organisms.py -v`) → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/interface backend/tests/api/test_organisms.py
git commit -m "feat(taxonomy): Organism API (CRUD, search, tax-id resolution) + DI wiring"
```

---

### Task 6: Strain aggregate (workspace-scoped) — full vertical slice

**Files:**
- Create: `backend/src/protcellar/domain/taxonomy/strain.py` (+ events in `events.py`, protocol in `repository.py`)
- Create: `backend/src/protcellar/application/taxonomy/{create_strain.py,update_strain.py,get_strain.py,list_strains.py}`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/taxonomy/strain_repository.py` (+ `StrainModel` in `models.py`)
- Create: `backend/src/protcellar/interface/routes/strains.py`; modify `_taxonomy.py`, `app.py`, migration
- Test: `tests/unit/domain/taxonomy/test_strain.py`, `tests/api/test_strains.py`

**Interfaces:**
- Produces: `Strain` aggregate (workspace-scoped) — fields `species_organism_id: uuid.UUID` (required), `strain_organism_id: uuid.UUID | None`, `name: str`, `isolate: str | None`, `biosample_acc: str | None`, `assembly_acc: str | None`, `culture_collection: str | None`, `host_organism_id: uuid.UUID | None`, `metadata: dict | None`. Standard `create`/`update`. `StrainRepository`. Full CRUD use cases (standard `require_editor` + `require_same_workspace` pattern — copy Organization's).

- [ ] **Step 1: Write the failing domain test** `tests/unit/domain/taxonomy/test_strain.py`:

```python
import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.strain import Strain


def test_create_requires_species_anchor_and_name() -> None:
    ws, species = uuid.uuid4(), uuid.uuid4()
    strain = Strain.create(workspace_id=ws, species_organism_id=species, name="K-12 MG1655")
    assert strain.species_organism_id == species
    assert strain.workspace_id == ws
    assert strain.version == 1
    with pytest.raises(ValidationError):
        Strain.create(workspace_id=ws, species_organism_id=species, name="  ")
```

Run → FAIL.

- [ ] **Step 2: Write `domain/taxonomy/strain.py`** — standard workspace-scoped aggregate (model on `Organization`): constructor validates non-empty `name`, stores all fields, `create()` registers `StrainCreated`, `update(**fields)` registers `StrainUpdated`. Add `StrainCreated`/`StrainUpdated` to `events.py` and `StrainRepository` to `repository.py` (`find_by_id_in_workspace`, `find_by_workspace(cursor,limit)`, `find_by_species(workspace_id, species_organism_id)`, `save`).

- [ ] **Step 3: Run domain test** → PASS.

- [ ] **Step 4: Add `StrainModel` to `taxonomy/models.py`:**

```python
class StrainModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "strains"

    species_organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    strain_organism_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    isolate: Mapped[str | None] = mapped_column(String(256), nullable=True)
    biosample_acc: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    assembly_acc: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    culture_collection: Mapped[str | None] = mapped_column(String(128), nullable=True)
    host_organism_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True
    )
    strain_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

(Import `JSON` from `sqlalchemy`. Column is `strain_metadata` to avoid SQLAlchemy's reserved `metadata`.)

- [ ] **Step 5: Write `strain_repository.py`** with `_to_domain`/`_to_model`/`_update_model` + `find_by_workspace`/`find_by_species` (workspace-scoped — copy the `OrganizationRepository` pattern).

- [ ] **Step 6: Write the use cases** — copy `create/update/get/list_organization.py` exactly, swapping `Organization`→`Strain` and fields. Keep the `require_editor` + `require_same_workspace(auth, input.workspace_id)` guards (workspace_id comes from `auth.workspace_id` in the route).

- [ ] **Step 7: Write `routes/strains.py`** (copy `organizations.py`), register in `_taxonomy.py` + `app.py`, generate migration (`uv run alembic revision --autogenerate -m "strain tables"` + `upgrade head`).

- [ ] **Step 8: Write `tests/api/test_strains.py`** — create a strain referencing an organism, get it, list it; assert 201/200 and version increments on patch.

Run: `make test-api` → PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/protcellar backend/alembic/versions backend/tests
git commit -m "feat(taxonomy): Strain aggregate (workspace-scoped) full vertical slice"
```

---

### Task 7: Proteome aggregate (lite) — full vertical slice

**Files:**
- Create: `domain/taxonomy/proteome.py` (+ events, protocol), `application/taxonomy/{create_proteome,get_proteome,list_proteomes}.py`, `infrastructure/.../taxonomy/proteome_repository.py` (+ `ProteomeModel`), `interface/routes/proteomes.py`; modify `_taxonomy.py`, `app.py`, migration
- Test: `tests/unit/domain/taxonomy/test_proteome.py`, `tests/api/test_proteomes.py`

**Interfaces:**
- Produces: `Proteome` aggregate (reference data, GLOBAL workspace like Organism) — fields `uniprot_proteome_id: str` (unique, validated `^UP\d{9}$` via `IdentifierRegistry` prefix `proteome`), `organism_id: uuid.UUID`, `strain_id: uuid.UUID | None`, `proteome_type: ProteomeType`, `is_reference: bool`, `assembly_acc: str | None`, `source_version: str | None`. `create`/`update`; `ProteomeRepository` (`find_by_id_in_workspace`, `find_by_proteome_id`, `find_by_organism`, `find_all`, `save`).

- [ ] **Step 1: Write the failing domain test** `tests/unit/domain/taxonomy/test_proteome.py`:

```python
import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def test_create_reference_proteome() -> None:
    org = uuid.uuid4()
    p = Proteome.create(
        uniprot_proteome_id="UP000005640", organism_id=org,
        proteome_type=ProteomeType.REFERENCE, is_reference=True,
    )
    assert p.workspace_id == GLOBAL_WORKSPACE_ID
    assert p.uniprot_proteome_id == "UP000005640"


def test_invalid_proteome_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Proteome.create(
            uniprot_proteome_id="NOTAPROTEOME", organism_id=uuid.uuid4(),
            proteome_type=ProteomeType.REFERENCE, is_reference=True,
        )
```

Run → FAIL.

- [ ] **Step 2: Write `domain/taxonomy/proteome.py`** — reference aggregate (sets `workspace_id = GLOBAL_WORKSPACE_ID` like `Organism`). Validate the proteome id format with a module-level regex `re.compile(r"^UP\d{9}$")` (domain stays dependency-free; the `IdentifierRegistry` is used at the API/infra edge for URL resolution). Register `ProteomeCreated`/`ProteomeUpdated`. Add events + `ProteomeRepository` protocol.

- [ ] **Step 3: Run domain test** → PASS.

- [ ] **Step 4: `ProteomeModel`** in `taxonomy/models.py` (reference data: `EntityModelMixin + WorkspaceIdMixin + VersionMixin + ProvenanceMixin`), columns per the field list, `uniprot_proteome_id` unique-indexed, FKs to `organisms.id`/`strains.id`. Write `proteome_repository.py`. Use cases mirror the Organism reference pattern (`require_admin` for create; reads open to authenticated). Routes copy `organisms.py` shape. Wire `_taxonomy.py` + `app.py`. Migration `proteome tables`.

- [ ] **Step 5: Write `tests/api/test_proteomes.py`** — create an organism, then a proteome referencing it; get/list; assert the `UP…` id round-trips and an invalid id returns 422.

Run: `make test-api` → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar backend/alembic/versions backend/tests
git commit -m "feat(taxonomy): Proteome aggregate (lite) full vertical slice"
```

---

### Task 8: Bulk import endpoint for organisms (provenance + idempotent upsert)

**Files:**
- Create: `backend/src/protcellar/application/taxonomy/bulk_upsert_organisms.py`
- Modify: `backend/src/protcellar/interface/routes/organisms.py` (add `POST /api/v1/organisms/bulk`), `_taxonomy.py`
- Add repository method: `SQLAlchemyOrganismRepository.find_by_source_record_id(source, source_record_id)`
- Test: `tests/api/test_organism_bulk_import.py`

**Interfaces:**
- Consumes: `OrganismRepository`, `UnitOfWork`, `EventDispatcher`, `require_workspace_role`/service auth.
- Produces: `BulkUpsertOrganisms` use case — accepts a list of organism records each with provenance (`source`, `source_release`, `source_record_id`, `source_record_checksum`); **upserts keyed on `(source, source_record_id)`**, skipping rows whose checksum is unchanged; returns a per-item result summary `{index, status: created|updated|skipped|failed, id?, error?}`. `dry_run` flag validates without persisting. (v1 is synchronous — the `202 + jobId` async path is deferred to the loader plan.)

- [ ] **Step 1: Add the finder** to `OrganismRepository` protocol + `SQLAlchemyOrganismRepository`:

```python
async def find_by_source_record_id(
    self, source: str, source_record_id: str
) -> Organism | None:
    stmt = select(OrganismModel).where(
        OrganismModel.source == source,
        OrganismModel.source_record_id == source_record_id,
    )
    model = (await self._session.execute(stmt)).scalar_one_or_none()
    return self._to_domain_tracked(model) if model else None
```

> This requires `source_record_id`/`source_record_checksum` to be set on the `Organism` aggregate when imported. Extend `Organism` with optional `source_record_id`/`source_record_checksum` attributes (carried through `_to_model`/`_to_domain`/`ProvenanceMixin`) — add them as constructor kwargs defaulting to `None` and map them in the repository. Make this change in this task and re-run Task 3's migration check (autogenerate will already have created the provenance columns via `ProvenanceMixin`).

- [ ] **Step 2: Write `bulk_upsert_organisms.py`:**

```python
"""Idempotent bulk upsert of organism reference records, keyed on (source, source_record_id)."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.taxonomy.enums import OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class OrganismImportRecord:
    ncbi_tax_id: int | None
    rank: str
    scientific_name: str
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    division: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertOrganismsCommand(Command):
    records: tuple[OrganismImportRecord, ...]
    dry_run: bool = False


@dataclass(frozen=True, kw_only=True)
class ItemResult:
    index: int
    status: str  # created | updated | skipped | failed
    id: str | None = None
    error: str | None = None


class BulkUpsertOrganisms:
    def __init__(
        self, uow: UnitOfWork, repo: OrganismRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: BulkUpsertOrganismsCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            for i, rec in enumerate(input.records):
                try:
                    existing = await self._repo.find_by_source_record_id(
                        rec.source, rec.source_record_id
                    )
                    if existing is not None:
                        if existing.source_record_checksum == rec.source_record_checksum:
                            results.append(ItemResult(index=i, status="skipped", id=str(existing.id)))
                            continue
                        existing.update(
                            scientific_name=rec.scientific_name, rank=rec.rank,
                            division=rec.division, source_version=rec.source_release,
                        )
                        existing.source_record_checksum = rec.source_record_checksum
                        if not input.dry_run:
                            await self._repo.save(existing)
                        results.append(ItemResult(index=i, status="updated", id=str(existing.id)))
                    else:
                        org = Organism.create(
                            ncbi_tax_id=rec.ncbi_tax_id, rank=rec.rank,
                            scientific_name=rec.scientific_name,
                            source=OrganismSource(rec.source) if rec.source in OrganismSource._value2member_map_ else OrganismSource.LOCAL,
                            division=rec.division, source_version=rec.source_release,
                        )
                        org.source_record_id = rec.source_record_id
                        org.source_record_checksum = rec.source_record_checksum
                        if not input.dry_run:
                            await self._repo.save(org)
                        results.append(ItemResult(index=i, status="created", id=str(org.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                # no commit on dry run
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
```

> Note: `org.source = ...` mapping for the `OrganismSource` lookup — if `rec.source` is e.g. `"ncbi"` it maps to `OrganismSource.NCBI`; arbitrary loader source tags fall back to `LOCAL` while `source_record_id` still records the true origin. Keep the `source` enum column distinct from the provenance `source` string if loader source tags don't match the enum — simplest: store the enum on `Organism.source` and the raw loader tag in the provenance `source_record_id` prefix. Resolve this naming overlap during implementation (the `ProvenanceMixin.source` column vs the `OrganismModel.source` enum column have the same name — rename the provenance one to `provenance_source` to avoid the clash).

- [ ] **Step 3: Add `POST /api/v1/organisms/bulk`** to `routes/organisms.py` — request body `{records: [...], dry_run: bool}`, returns `200` with `{results: [...], summary: {created, updated, skipped, failed}}`. Register `BulkUpsertOrganisms` in `_taxonomy.py`.

- [ ] **Step 4: Write `tests/api/test_organism_bulk_import.py`:**

```python
import pytest
from httpx import AsyncClient

_REC = {
    "ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens",
    "source": "ncbi", "source_release": "2026_02", "source_record_id": "9606",
    "source_record_checksum": "abc123",
}


@pytest.mark.asyncio
async def test_bulk_upsert_is_idempotent(client: AsyncClient) -> None:
    first = await client.post("/api/v1/organisms/bulk", json={"records": [_REC]})
    assert first.status_code == 200
    assert first.json()["summary"]["created"] == 1

    # same checksum → skipped
    second = await client.post("/api/v1/organisms/bulk", json={"records": [_REC]})
    assert second.json()["summary"]["skipped"] == 1


@pytest.mark.asyncio
async def test_dry_run_does_not_persist(client: AsyncClient) -> None:
    rec = {**_REC, "ncbi_tax_id": 562, "source_record_id": "562", "scientific_name": "Escherichia coli"}
    dry = await client.post("/api/v1/organisms/bulk", json={"records": [rec], "dry_run": True})
    assert dry.json()["summary"]["created"] == 1
    # not actually persisted
    resolved = await client.get("/api/v1/organisms/resolve/562")
    assert resolved.status_code == 404
```

Run: `make test-api` → PASS.

- [ ] **Step 5: Final commit + full suite**

Run: `make test-all` → all unit + api + import-linter green.
Run: `make lint` → ruff + mypy clean.
```bash
git add backend/src/protcellar backend/tests
git commit -m "feat(taxonomy): idempotent bulk-upsert endpoint for organisms with provenance"
```

---

## Self-Review (run after implementing)

- **Spec coverage:** Implements spec §5.1 (Organism adjacency + names + merged/deleted + source-tagging; Strain anchored to species; lite Proteome), §6 (per-aggregate CRUD, search by tax_id/name, ID-resolution endpoint, bulk import with `(source, source_record_id)` upsert + dry-run), §7 (provenance columns + idempotent reload via checksum skip), and resolves §10 Q1 (reference-data tenancy → GLOBAL sentinel).
- **Deferred (per spec "later"):** materialized-path/`ltree` accelerator (adjacency list only for v1), GTDB second source (enum value reserved), pan-proteomes, async `202+jobId` bulk path (synchronous for v1).
- **Type/name consistency to verify during implementation:** the `source` name clash flagged in Task 8 Step 2 (rename `ProvenanceMixin.source` → `provenance_source`); `strain_metadata` column name (not `metadata`); `_to_domain_tracked`/`_session` come from the ported base repository.
- **Open follow-ups:** Protein Catalog plan (Plan 2) will add `protein.organism_id`/`strain_id` FKs into these tables; Target plan (Plan 3) depends on Protein.
