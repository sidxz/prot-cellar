# prot-cellar Target Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Prerequisite:** The Foundation, Taxonomy, and Protein Catalog plans must be fully implemented and green on branch `feat/foundation`. This plan builds on the base classes, repository, UoW, event dispatcher, identifier registry, the `Strain` workspace-scoped slice (the exemplar to mirror), the Organism `names` child-collection pattern, and the `Protein` aggregate (`proteins` table — `TargetComponent.protein_id` FKs to it).

**Goal:** Implement the Target bounded context — `Target` (workspace-scoped aggregate root, the pharmacological entity) + `TargetComponent` (ordered child entity referencing a `Protein`), enforcing the **single-vs-complex cardinality invariant** that is the reason the context exists — as a full domain→application→infrastructure→interface vertical slice with workspace-scoped CRUD, then re-enable the import-linter bounded-context `independence` contract now that all five contexts exist.

**Architecture:** `Target` is **tenant data** (workspace-scoped), so it mirrors `Strain` exactly — real `workspace_id`, `require_editor` + `require_same_workspace` guards, `workspace_id` sourced from `auth.workspace_id` (never body/URL), workspace-scoped uniqueness and queries. It is a versioned `AggregateRoot` with `TargetCreated`/`TargetUpdated` events (NOT a bare `EntityRepository` entity — the base-repository docstring's mention of "Target" describes chem-cellar's *old collapsed* target; prot-cellar's is the canonical aggregate of spec §5.3). `TargetComponent` is an ordered child entity in the Target aggregate, mapped exactly like the Organism `names` collection (`selectin` + `cascade="all, delete-orphan"`, replaced wholesale on update). The aggregate enforces, in pure domain code, that component cardinality agrees with `target_type`. Cross-context links (`organism_id`, `TargetComponent.protein_id`) are `uuid.UUID` FKs — the **target domain never imports another context's domain**, so the import-linter `independence` contract (re-enabled in Task 5) holds.

**Tech Stack:** Same as the prior plans. No new runtime dependencies. Postgres (real, via testcontainers in tests).

## Global Constraints

- All prior Global Constraints apply (workspace scoping, auth-guards-first, Railway `Result`, optimistic concurrency, UoW + post-commit event dispatch, ruff/mypy/lint-imports clean, commit-per-task).
- **Tenant data (security-critical):** `Target` carries a real `workspace_id`. Write use cases guard `require_editor(auth)` **then** `require_same_workspace(auth, input.workspace_id)`; read use cases guard the same (load via `find_by_id_in_workspace(workspace_id, id)` / `find_by_workspace(workspace_id, ...)`). `workspace_id` comes from `auth.workspace_id` in the route — **never** from the request body or URL. This is the `Strain` pattern, NOT the `Organism`/reference pattern.
- **Aggregate invariant (the whole point — enforce + unit-test):** component cardinality must agree with `target_type`:
  - `SINGLE_PROTEIN` ⇒ **exactly 1** component;
  - `PROTEIN_COMPLEX` / `PROTEIN_FAMILY` / `PROTEIN_PROTEIN_INTERACTION` ⇒ **≥ 2** components;
  - all other types (`NUCLEIC_ACID`, `ORGANISM`, `CELL_LINE`, `TISSUE`, `UNKNOWN`) ⇒ unconstrained.
  Violations raise `ValidationError` (→ HTTP 422). The invariant is enforced in the domain at construction and re-checked whenever components or `target_type` change.
- **Child collection:** `TargetComponent` mirrors the Organism `names` pattern — `relationship(cascade="all, delete-orphan", lazy="selectin", order_by=...)`; `_to_model`/`_update_model` replace the collection wholesale. The base-repo raw-UPDATE-vs-flush round-trip is proven safe for GLOBAL data (`test_update_organism_preserves_names`); this plan adds an **analogous workspace-scoped round-trip test** (`test_update_target_preserves_components`).
- **Bounded-context independence:** the `protcellar.domain.target` package imports only stdlib + `protcellar.domain.shared.*` + its own modules. It must NOT import `protcellar.domain.taxonomy.*` or `protcellar.domain.protein_catalog.*` (cross-context links are `uuid.UUID` FKs). Task 5 re-enables the import-linter `independence` contract listing all five contexts.
- **Mechanical CRUD (commands/queries, routes, DI, response DTOs) mirrors the `Strain` slice exactly** — same `*Command`/`*Query` shapes (carrying `workspace_id`), `result_to_response`, `from_domain` DTOs, `PaginatedResponse(items, next_cursor)`, `_get_use_case` Lagom registration, `body.model_fields_set` PATCH pattern. Only the fields differ.
- **Gotchas:** `export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar` before any `alembic` command; after adding model modules, append the import to `infrastructure/persistence/sqlalchemy/metadata.py` **then inspect autogenerate for spurious `DROP`s**; api-test DB is session-shared (use distinct workspace_ids / pref_names per test); routes call use cases, never repositories.

---

## File Structure

```
backend/src/protcellar/
  domain/target/
    __init__.py
    enums.py            # TargetType, ComponentRelationship
    target.py           # Target aggregate + TargetComponent entity + cardinality invariant
    events.py           # TargetCreated, TargetUpdated
    repository.py       # TargetRepository protocol
  application/target/
    __init__.py
    create_target.py get_target.py list_targets.py update_target.py
  infrastructure/
    persistence/sqlalchemy/target/
      __init__.py
      models.py            # TargetModel, TargetComponentModel
      target_repository.py
    di/_target.py          # register_target(container)
  interface/
    routes/targets.py
    dependencies/_target.py
  (modify) infrastructure/di/container.py            # call register_target
  (modify) interface/dependencies/__init__.py        # re-export Target *Dep aliases
  (modify) interface/app.py                          # include targets router
  (modify) tests/api/conftest.py                     # include targets router
  (modify) infrastructure/persistence/sqlalchemy/metadata.py  # import target models
  (modify) backend/pyproject.toml                    # re-enable independence contract (Task 5)
tests/
  unit/domain/target/
    __init__.py test_target.py            # the cardinality invariant — the whole point
  api/test_targets.py                     # CRUD + invariant→422 + components round-trip
```

---

### Task 1: Target domain — enums, `TargetComponent`, `Target` aggregate (cardinality invariant), events, repository protocol

**Files:**
- Create: `backend/src/protcellar/domain/target/__init__.py` (empty), `enums.py`, `events.py`, `target.py`, `repository.py`
- Test: `backend/tests/unit/domain/target/__init__.py` (empty), `test_target.py`

**Interfaces:**
- Produces:
  - `TargetType` StrEnum: `SINGLE_PROTEIN`, `PROTEIN_COMPLEX`, `PROTEIN_FAMILY`, `PROTEIN_PROTEIN_INTERACTION`, `NUCLEIC_ACID`, `ORGANISM`, `CELL_LINE`, `TISSUE`, `UNKNOWN`. `ComponentRelationship` StrEnum: `SINGLE_PROTEIN`, `PROTEIN_SUBUNIT`, `FAMILY_MEMBER`, `INTERACTING_PROTEIN`.
  - `TargetComponent` entity dataclass `{protein_id: uuid.UUID, relationship: ComponentRelationship, id: uuid.UUID}`.
  - `Target` aggregate (workspace-scoped): fields `workspace_id`, `pref_name: str`, `target_type: TargetType`, `components: list[TargetComponent]`, `organism_id: uuid.UUID | None`, `chembl_id: str | None`, `pharmacological_class: str | None`, `cross_references: list[CrossReference]`, plus base `id`/`version`/`created_at`/`updated_at`. Classmethod `Target.create(...)`, `update(**fields)`, `set_components(list)`. Enforces the cardinality invariant in `_validate_cardinality()`.
  - Events `TargetCreated(workspace_id, pref_name, target_type)`, `TargetUpdated(workspace_id)`.
  - `TargetRepository` protocol: `find_by_id_in_workspace`, `find_by_workspace(workspace_id, *, cursor_id=None, limit=None, target_type=None, chembl_id=None)`, `save`.

- [ ] **Step 1: Write the failing test** `backend/tests/unit/domain/target/test_target.py` — the cardinality invariant is the core deliverable, so cover it thoroughly:

```python
import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.events import TargetCreated, TargetUpdated
from protcellar.domain.target.target import Target, TargetComponent


def _component(rel: ComponentRelationship = ComponentRelationship.SINGLE_PROTEIN) -> TargetComponent:
    return TargetComponent(protein_id=uuid.uuid4(), relationship=rel)


def test_create_single_protein_target() -> None:
    ws = uuid.uuid4()
    target = Target.create(
        workspace_id=ws,
        pref_name="EGFR",
        target_type=TargetType.SINGLE_PROTEIN,
        components=[_component()],
    )
    assert target.workspace_id == ws
    assert target.pref_name == "EGFR"
    assert target.version == 1
    assert len(target.components) == 1
    events = target.collect_events()
    assert len(events) == 1 and isinstance(events[0], TargetCreated)


def test_create_requires_pref_name() -> None:
    with pytest.raises(ValidationError):
        Target.create(
            workspace_id=uuid.uuid4(),
            pref_name="  ",
            target_type=TargetType.UNKNOWN,
            components=[],
        )


def test_single_protein_requires_exactly_one_component() -> None:
    ws = uuid.uuid4()
    with pytest.raises(ValidationError):  # zero
        Target.create(workspace_id=ws, pref_name="X", target_type=TargetType.SINGLE_PROTEIN, components=[])
    with pytest.raises(ValidationError):  # two
        Target.create(
            workspace_id=ws, pref_name="X", target_type=TargetType.SINGLE_PROTEIN,
            components=[_component(), _component()],
        )


@pytest.mark.parametrize(
    "ttype",
    [TargetType.PROTEIN_COMPLEX, TargetType.PROTEIN_FAMILY, TargetType.PROTEIN_PROTEIN_INTERACTION],
)
def test_multi_protein_types_require_at_least_two(ttype: TargetType) -> None:
    ws = uuid.uuid4()
    with pytest.raises(ValidationError):  # one is not enough
        Target.create(workspace_id=ws, pref_name="X", target_type=ttype, components=[_component()])
    # two is fine
    target = Target.create(
        workspace_id=ws, pref_name="X", target_type=ttype, components=[_component(), _component()]
    )
    assert len(target.components) == 2


def test_non_protein_type_allows_zero_components() -> None:
    target = Target.create(
        workspace_id=uuid.uuid4(), pref_name="Liver tissue",
        target_type=TargetType.TISSUE, components=[],
    )
    assert target.components == []


def test_update_revalidates_cardinality() -> None:
    target = Target.create(
        workspace_id=uuid.uuid4(), pref_name="X", target_type=TargetType.SINGLE_PROTEIN,
        components=[_component()],
    )
    # Adding a second component while still SINGLE_PROTEIN violates the invariant
    with pytest.raises(ValidationError):
        target.set_components([_component(), _component()])
    # Promoting to a complex with two components is valid
    target.update(target_type=TargetType.PROTEIN_COMPLEX, components=[_component(), _component()])
    assert target.target_type == TargetType.PROTEIN_COMPLEX
    assert len(target.components) == 2
    assert any(isinstance(e, TargetUpdated) for e in target.collect_events())
```

- [ ] **Step 2: Run test to verify it fails** — `cd backend && uv run pytest tests/unit/domain/target/test_target.py -v` → FAIL.

- [ ] **Step 3: Write `domain/target/__init__.py`** (empty) and `enums.py`:

```python
"""Target controlled vocabularies (ChEMBL target-type subset)."""

from __future__ import annotations

from enum import StrEnum


class TargetType(StrEnum):
    SINGLE_PROTEIN = "single_protein"
    PROTEIN_COMPLEX = "protein_complex"
    PROTEIN_FAMILY = "protein_family"
    PROTEIN_PROTEIN_INTERACTION = "protein_protein_interaction"
    NUCLEIC_ACID = "nucleic_acid"
    ORGANISM = "organism"
    CELL_LINE = "cell_line"
    TISSUE = "tissue"
    UNKNOWN = "unknown"


class ComponentRelationship(StrEnum):
    SINGLE_PROTEIN = "single_protein"
    PROTEIN_SUBUNIT = "protein_subunit"
    FAMILY_MEMBER = "family_member"
    INTERACTING_PROTEIN = "interacting_protein"
```

- [ ] **Step 4: Write `domain/target/events.py`:**

```python
"""Target domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent
from protcellar.domain.target.enums import TargetType


@dataclass(frozen=True, kw_only=True)
class TargetCreated(DomainEvent):
    workspace_id: uuid.UUID
    pref_name: str
    target_type: TargetType


@dataclass(frozen=True, kw_only=True)
class TargetUpdated(DomainEvent):
    workspace_id: uuid.UUID
```

- [ ] **Step 5: Write `domain/target/target.py`** (the aggregate + invariant):

```python
"""Target aggregate — the pharmacological entity a compound acts on (workspace-scoped).

A Target references 1..n TargetComponents, each pointing at a canonical Protein.
The cardinality of that collection must agree with `target_type` (the core invariant).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.events import TargetCreated, TargetUpdated

# target_types whose component cardinality is constrained by the invariant.
_EXACTLY_ONE = {TargetType.SINGLE_PROTEIN}
_AT_LEAST_TWO = {
    TargetType.PROTEIN_COMPLEX,
    TargetType.PROTEIN_FAMILY,
    TargetType.PROTEIN_PROTEIN_INTERACTION,
}


@dataclass
class TargetComponent:
    """A protein constituent of a Target (entity within the Target aggregate)."""

    protein_id: uuid.UUID
    relationship: ComponentRelationship
    id: uuid.UUID = field(default_factory=uuid.uuid4)


class Target(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        pref_name: str,
        target_type: TargetType,
        components: list[TargetComponent] | None = None,
        organism_id: uuid.UUID | None = None,
        chembl_id: str | None = None,
        pharmacological_class: str | None = None,
        cross_references: list[CrossReference] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not pref_name or not pref_name.strip():
            raise ValidationError("Target pref_name must not be empty")
        self.workspace_id = workspace_id
        self.pref_name = pref_name.strip()
        self.target_type = target_type
        self.components: list[TargetComponent] = components if components is not None else []
        self.organism_id = organism_id
        self.chembl_id = chembl_id
        self.pharmacological_class = pharmacological_class
        self.cross_references = cross_references if cross_references is not None else []
        self._validate_cardinality(self.target_type, len(self.components))

    @staticmethod
    def _validate_cardinality(target_type: TargetType, n_components: int) -> None:
        if target_type in _EXACTLY_ONE and n_components != 1:
            raise ValidationError(
                f"{target_type.value} target requires exactly 1 component, got {n_components}"
            )
        if target_type in _AT_LEAST_TWO and n_components < 2:
            raise ValidationError(
                f"{target_type.value} target requires at least 2 components, got {n_components}"
            )

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        pref_name: str,
        target_type: TargetType,
        components: list[TargetComponent] | None = None,
        organism_id: uuid.UUID | None = None,
        chembl_id: str | None = None,
        pharmacological_class: str | None = None,
        cross_references: list[CrossReference] | None = None,
    ) -> Target:
        target = cls(
            workspace_id=workspace_id,
            pref_name=pref_name,
            target_type=target_type,
            components=components,
            organism_id=organism_id,
            chembl_id=chembl_id,
            pharmacological_class=pharmacological_class,
            cross_references=cross_references,
        )
        target.register_event(
            TargetCreated(
                aggregate_id=target.id,
                aggregate_type="Target",
                workspace_id=workspace_id,
                pref_name=target.pref_name,
                target_type=target.target_type,
            )
        )
        return target

    def set_components(self, components: list[TargetComponent]) -> None:
        """Replace the component collection, re-validating the cardinality invariant first."""
        self._validate_cardinality(self.target_type, len(components))
        self.components = list(components)
        self._touch()

    def update(self, **fields: Any) -> None:
        """Partial update. Accepted keys: pref_name, target_type, components,
        organism_id, chembl_id, pharmacological_class, cross_references.

        If target_type and/or components change, the cardinality invariant is
        re-validated against the resulting combination before it is committed.
        """
        new_type = fields["target_type"] if "target_type" in fields else self.target_type
        new_components = (
            list(fields["components"]) if "components" in fields else self.components
        )
        # Validate the prospective combination before mutating any state.
        self._validate_cardinality(new_type, len(new_components))

        if "pref_name" in fields:
            value = fields["pref_name"]
            if not value or not str(value).strip():
                raise ValidationError("Target pref_name must not be empty")
            self.pref_name = str(value).strip()
        if "target_type" in fields:
            self.target_type = new_type
        if "components" in fields:
            self.components = new_components
        if "organism_id" in fields:
            self.organism_id = fields["organism_id"]
        if "chembl_id" in fields:
            self.chembl_id = fields["chembl_id"]
        if "pharmacological_class" in fields:
            self.pharmacological_class = fields["pharmacological_class"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            TargetUpdated(
                aggregate_id=self.id,
                aggregate_type="Target",
                workspace_id=self.workspace_id,
            )
        )
```

> `update()` validates the *prospective* `(target_type, components)` combination via a throwaway instance before mutating `self`, so a rejected update leaves the aggregate unchanged. `set_components()` restores the previous list on failure. Both keep the invariant total.

- [ ] **Step 6: Write `domain/target/repository.py`:**

```python
"""Target repository protocol."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.target.enums import TargetType
from protcellar.domain.target.target import Target


@runtime_checkable
class TargetRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Target | None: ...

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        target_type: TargetType | None = None,
        chembl_id: str | None = None,
    ) -> list[Target]: ...

    async def save(self, aggregate: Target) -> None: ...
```

- [ ] **Step 7: Run test to verify it passes** — `cd backend && uv run pytest tests/unit/domain/target/test_target.py -v` → PASS. Then `cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src` → clean.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/domain/target backend/tests/unit/domain/target
git commit -m "feat(target): Target aggregate + TargetComponent with cardinality invariant, events, repo protocol"
```

---

### Task 2: Target persistence — SA models (child collection), repository, migration

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/target/__init__.py` (empty), `models.py`, `target_repository.py`
- Modify: `infrastructure/persistence/sqlalchemy/metadata.py`
- Create migration: `xxxx_target_tables.py`
- Test: covered by Task 4's api tests (repository behavior is exercised end-to-end there)

**Interfaces:**
- Consumes: `Base`, `EntityModelMixin`, `WorkspaceIdMixin`, `VersionMixin`, `SQLAlchemyRepository`, `AsyncUnitOfWork`, `Target`, `TargetComponent`, `TargetType`, `ComponentRelationship`, `CrossReference`, and the shared cross-reference JSON helpers.
- Produces: `TargetModel` (workspace-scoped), `TargetComponentModel` (child, FK→`targets.id` and FK→`proteins.id`, `position` for ordering), `SQLAlchemyTargetRepository` implementing `TargetRepository`.

- [ ] **Step 1: Write `infrastructure/persistence/sqlalchemy/target/__init__.py`** (empty) and `models.py`:

```python
"""SQLAlchemy models for the Target context."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class TargetModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "targets"

    pref_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organism_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True, index=True
    )
    chembl_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    pharmacological_class: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)

    components: Mapped[list[TargetComponentModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TargetComponentModel.position",
        foreign_keys="TargetComponentModel.target_id",
    )


class TargetComponentModel(Base, EntityModelMixin):
    __tablename__ = "target_components"

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targets.id"), nullable=False, index=True
    )
    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

> `TargetComponentModel` has no `VersionMixin`/`WorkspaceIdMixin` — it is a child entity, workspace-scoped transitively through its parent `Target` and versioned via the aggregate root (exactly like `OrganismNameModel`). `position` gives the collection deterministic order; the relationship `order_by`s on it.

- [ ] **Step 2: Write `target/target_repository.py`** (mirror `SQLAlchemyStrainRepository` for the workspace-scoped finders and `SQLAlchemyOrganismRepository` for the child-collection mapping). The cross-reference↔JSON mapping reuses the helpers created in the Protein Catalog plan (`infrastructure/persistence/sqlalchemy/protein_catalog/_xref_json.py` — `xrefs_to_json`/`xrefs_from_json`); import them directly (infrastructure→infrastructure import; the import-linter `independence` contract governs the *domain* layer only):

```python
"""SQLAlchemy Target repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.repository import TargetRepository
from protcellar.domain.target.target import Target, TargetComponent
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._xref_json import (
    xrefs_from_json,
    xrefs_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import (
    TargetComponentModel,
    TargetModel,
)


class SQLAlchemyTargetRepository(SQLAlchemyRepository[Target, TargetModel], TargetRepository):
    model_class = TargetModel

    def _to_domain(self, model: TargetModel) -> Target:
        return Target(
            id=model.id,
            workspace_id=model.workspace_id,
            pref_name=model.pref_name,
            target_type=TargetType(model.target_type),
            components=[
                TargetComponent(
                    id=c.id,
                    protein_id=c.protein_id,
                    relationship=ComponentRelationship(c.relationship),
                )
                for c in model.components
            ],
            organism_id=model.organism_id,
            chembl_id=model.chembl_id,
            pharmacological_class=model.pharmacological_class,
            cross_references=xrefs_from_json(model.cross_references),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Target) -> TargetModel:
        model = TargetModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            pref_name=aggregate.pref_name,
            target_type=aggregate.target_type.value,
            organism_id=aggregate.organism_id,
            chembl_id=aggregate.chembl_id,
            pharmacological_class=aggregate.pharmacological_class,
            cross_references=xrefs_to_json(aggregate.cross_references) or None,
            version=aggregate.version,
        )
        model.components = [
            self._component_to_model(c, i) for i, c in enumerate(aggregate.components)
        ]
        return model

    def _update_model(self, model: TargetModel, aggregate: Target) -> None:
        model.pref_name = aggregate.pref_name
        model.target_type = aggregate.target_type.value
        model.organism_id = aggregate.organism_id
        model.chembl_id = aggregate.chembl_id
        model.pharmacological_class = aggregate.pharmacological_class
        model.cross_references = xrefs_to_json(aggregate.cross_references) or None
        # Replace the components collection wholesale (delete-orphan handles removals).
        model.components = [
            self._component_to_model(c, i) for i, c in enumerate(aggregate.components)
        ]

    @staticmethod
    def _component_to_model(c: TargetComponent, position: int) -> TargetComponentModel:
        return TargetComponentModel(
            id=c.id,
            protein_id=c.protein_id,
            relationship=c.relationship.value,
            position=position,
        )

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        target_type: TargetType | None = None,
        chembl_id: str | None = None,
    ) -> list[Target]:
        stmt = select(TargetModel).where(TargetModel.workspace_id == workspace_id)
        if target_type is not None:
            stmt = stmt.where(TargetModel.target_type == target_type.value)
        if chembl_id is not None:
            stmt = stmt.where(TargetModel.chembl_id == chembl_id)
        if cursor_id is not None:
            stmt = stmt.where(TargetModel.id > cursor_id)
        stmt = stmt.order_by(TargetModel.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
```

> `find_by_id_in_workspace` and `save` (with optimistic concurrency + the workspace defence-in-depth check) come from the `SQLAlchemyRepository` base. `_to_domain_tracked`/`_session` come from the base too. The base `save()` UPDATE path replaces `model.components` and the raw-UPDATE version bump coexists with the delete-orphan flush (proven safe by `test_update_organism_preserves_names`; Task 4 adds the analogous Target test).

- [ ] **Step 3: Register the model with the alembic aggregator** — add `import protcellar.infrastructure.persistence.sqlalchemy.target.models  # noqa: F401` to `infrastructure/persistence/sqlalchemy/metadata.py`.

- [ ] **Step 4: Generate and apply the migration**

Run: `export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar`
Run: `cd backend && uv run alembic upgrade head`
Run: `uv run alembic revision --autogenerate -m "target tables"`
**Inspect** for `targets` (FK→`organisms.id`) and `target_components` (FKs→`targets.id` and `proteins.id`, plus `position`), and **no spurious `DROP`** of existing tables. Then:
Run: `uv run alembic upgrade head`

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/persistence/sqlalchemy/target \
        backend/src/protcellar/infrastructure/persistence/sqlalchemy/metadata.py \
        backend/alembic/versions
git commit -m "feat(target): SA models (target + ordered components child collection) and repository"
```

---

### Task 3: Target application use cases (workspace-scoped CRUD)

**Files:**
- Create: `backend/src/protcellar/application/target/__init__.py` (empty), `create_target.py`, `get_target.py`, `list_targets.py`, `update_target.py`
- Test: none new (covered by Task 4's api tests; the cardinality invariant is unit-tested in Task 1)

**Interfaces:**
- Consumes: `TargetRepository`, `UnitOfWork`, `EventDispatcher`, `require_editor`, `require_same_workspace`, `TargetType`, `ComponentRelationship`, `TargetComponent`, `CrossReference`.
- Produces: `CreateTarget`/`UpdateTarget` commands, `GetTarget`/`ListTargets` queries — all workspace-scoped (mirror the `Strain` use cases). Commands carry `workspace_id`.

- [ ] **Step 1: Write `create_target.py`** — mirror `create_strain.py` (`require_editor` + `require_same_workspace`), carrying the Target fields. The command carries `components` as a tuple of a small input record (so the frozen dataclass stays hashable) which the use case maps to domain `TargetComponent`s:

```python
"""CreateTarget command — register a new target in a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_editor, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.repository import TargetRepository
from protcellar.domain.target.target import Target, TargetComponent


@dataclass(frozen=True, kw_only=True)
class ComponentInput:
    protein_id: uuid.UUID
    relationship: ComponentRelationship


@dataclass(frozen=True, kw_only=True)
class CreateTargetCommand(Command):
    workspace_id: uuid.UUID
    pref_name: str
    target_type: TargetType
    components: tuple[ComponentInput, ...] = ()
    organism_id: uuid.UUID | None = None
    chembl_id: str | None = None
    pharmacological_class: str | None = None
    cross_references: tuple[CrossReference, ...] = field(default_factory=tuple)


class CreateTarget:
    def __init__(
        self, uow: UnitOfWork, repo: TargetRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateTargetCommand, auth: AuthContext | None = None
    ) -> Result[Target, DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            target = Target.create(
                workspace_id=input.workspace_id,
                pref_name=input.pref_name,
                target_type=input.target_type,
                components=[
                    TargetComponent(protein_id=c.protein_id, relationship=c.relationship)
                    for c in input.components
                ],
                organism_id=input.organism_id,
                chembl_id=input.chembl_id,
                pharmacological_class=input.pharmacological_class,
                cross_references=list(input.cross_references),
            )
            await self._repo.save(target)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(target)
```

> `Target.create` raises `ValidationError` on a cardinality violation; because the use case never wraps the constructor in try/except, the error propagates and the centralized error handler maps it to HTTP 422 (Railway: domain invariant → `ValidationError` → 422). Do NOT catch it into a `Failure`.

- [ ] **Step 2: Write `get_target.py`, `list_targets.py`, `update_target.py`** mirroring the Strain equivalents:
  - `get_target.py` — `GetTargetQuery{workspace_id, target_id}`, `require_editor` + `require_same_workspace`, `find_by_id_in_workspace(input.workspace_id, input.target_id)`, `NotFoundError("Target", str(input.target_id))`.
  - `list_targets.py` — `ListTargetsQuery{workspace_id, cursor_id, limit, target_type=None, chembl_id=None}`, `require_editor` + `require_same_workspace`, `find_by_workspace(...)` with the `+1`/`next_cursor` slicing pattern (copy `list_strains.py`), returns `Result[PageResult[Target], DomainError]`.
  - `update_target.py` — mirror `update_strain.py`: `UpdateTargetCommand{workspace_id, target_id, pref_name=None, target_type=None, components: tuple[ComponentInput,...] | None = None, organism_id=UNSET, chembl_id=UNSET, pharmacological_class=UNSET, cross_references: tuple[CrossReference,...] | None = None}`. `require_editor` + `require_same_workspace`; load via `find_by_id_in_workspace`; build the `fields` dict (include `pref_name`/`target_type`/`components`/`cross_references` only when not None; `organism_id`/`chembl_id`/`pharmacological_class` only when not `UNSET`), mapping `components` → `[TargetComponent(...) for c in input.components]`; `target.update(**fields)`; `save`; commit; dispatch. `target.update` re-validates the cardinality invariant and raises `ValidationError` (→422) on violation — do not catch it.

- [ ] **Step 3: Run lint** — `cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src` → clean. (Use cases are exercised by Task 4's api tests.)

- [ ] **Step 4: Commit**

```bash
git add backend/src/protcellar/application/target
git commit -m "feat(target): workspace-scoped Target use cases (create/get/list/update)"
```

---

### Task 4: Target API routes + DI wiring + api tests (incl. components round-trip)

**Files:**
- Create: `backend/src/protcellar/interface/routes/targets.py`, `infrastructure/di/_target.py`, `interface/dependencies/_target.py`
- Modify: `infrastructure/di/container.py`, `interface/dependencies/__init__.py`, `interface/app.py`, `tests/api/conftest.py`
- Test: `backend/tests/api/test_targets.py`

**Interfaces:**
- Consumes: the Task 3 use cases, `AuthDep`/`_get_use_case`, `IdentifierRegistry`, `PaginatedResponse`.
- Produces: `GET /api/v1/targets`, `GET /api/v1/targets/{target_id}`, `POST /api/v1/targets`, `PATCH /api/v1/targets/{target_id}`; `register_target(container)`; `*Dep` aliases.

- [ ] **Step 1: Write `interface/routes/targets.py`** mirroring `routes/strains.py` (workspace-scoped: `workspace_id` from `auth.workspace_id`, never the body). Specifics:
  - `router = APIRouter(prefix="/api/v1/targets", tags=["targets"])`.
  - `ComponentBody{protein_id: uuid.UUID, relationship: ComponentRelationship}`; `CrossReferenceBody{database, accession, properties: dict[str,str] | None = None, evidence: str | None = None}`.
  - `TargetResponse` fields: `id, workspace_id, pref_name, target_type, components (list of {id, protein_id, relationship}), organism_id, chembl_id, chembl_url, pharmacological_class, cross_references (list of {database, accession, curie, url}), version`. `from_domain` builds `chembl_url = IdentifierRegistry.default().resolve_url("chembl.target", t.chembl_id) if t.chembl_id else None` and renders `cross_references` like the Protein DTO.
  - `CreateTargetBody{pref_name, target_type, components: list[ComponentBody] = [], organism_id=None, chembl_id=None, pharmacological_class=None, cross_references: list[CrossReferenceBody] = []}`.
  - `UpdateTargetBody{pref_name=None, target_type=None, components: list[ComponentBody] | None = None, organism_id=None, chembl_id=None, pharmacological_class=None, cross_references: list[CrossReferenceBody] | None = None}` with `model_config = {"extra": "forbid"}`.
  - Routes (mirror `strains.py`): `GET ""` (list — reads `target_type`, `chembl_id`, `cursor`, `limit` query params; `target_type` parsed to the `TargetType` enum), `GET /{target_id}`, `POST ""` (201), `PATCH /{target_id}`. All set `workspace_id=auth.workspace_id`. The create/patch routes convert `components`→`ComponentInput(...)` tuples and `cross_references`→`CrossReference(...)` tuples; the PATCH route uses `body.model_fields_set` (mirror `update_strain` route: `pref_name`/`target_type`/`components`/`cross_references` passed when present else `None`; `organism_id`/`chembl_id`/`pharmacological_class` passed when present else `UNSET`).

- [ ] **Step 2: Write `infrastructure/di/_target.py`** — `register_target(container)` mirroring `_taxonomy.py`'s Strain helpers (`_target_cmd` building `AsyncUnitOfWork(c[async_sessionmaker])` + `SQLAlchemyTargetRepository(uow)` + `c[EventDispatcher]`; `_target_query` without the dispatcher). Register `CreateTarget`, `UpdateTarget` (commands) and `GetTarget`, `ListTargets` (queries).

- [ ] **Step 3: Write `interface/dependencies/_target.py`** — `CreateTargetDep`, `UpdateTargetDep`, `GetTargetDep`, `ListTargetsDep` via `Annotated[..., Depends(_get_use_case(...))]`, with `__all__`.

- [ ] **Step 4: Wire it up (4 edits):**
  1. `infrastructure/di/container.py` — import `register_target` and call `register_target(container)` after `register_protein_catalog(container)`.
  2. `interface/dependencies/__init__.py` — import + re-export the four `*TargetDep` aliases (add to `__all__`).
  3. `interface/app.py` — `from protcellar.interface.routes.targets import router as target_router` + `app.include_router(target_router)`.
  4. `tests/api/conftest.py` — add the targets router import + `app.include_router(target_router)` in `_create_test_app`. **Verify `git status` stages this file before committing.**

- [ ] **Step 5: Write `tests/api/test_targets.py`** — covers CRUD, the cardinality invariant returning 422, and the **component round-trip on PATCH** (the child-collection × raw-UPDATE concurrency check):

```python
import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    if resp.status_code == 409:
        return (await client.get("/api/v1/organisms/resolve/9606")).json()["id"]
    return resp.json()["id"]


async def _protein(client: AsyncClient, organism_id: str, accession: str) -> str:
    resp = await client.post(
        "/api/v1/proteins",
        json={"primary_accession": accession, "organism_id": organism_id,
              "sequence": "MKTAYIAKQR", "is_reviewed": True},
    )
    if resp.status_code == 409:
        return (await client.get(f"/api/v1/proteins/{accession}")).json()["id"]
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_single_protein_target_and_get(client: AsyncClient) -> None:
    organism_id = await _organism(client)
    p1 = await _protein(client, organism_id, "P11111")
    resp = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "EGFR",
            "target_type": "single_protein",
            "components": [{"protein_id": p1, "relationship": "single_protein"}],
            "chembl_id": "CHEMBL203",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["pref_name"] == "EGFR"
    assert len(body["components"]) == 1
    assert body["chembl_url"] is not None

    got = await client.get(f"/api/v1/targets/{body['id']}")
    assert got.status_code == 200
    assert got.json()["target_type"] == "single_protein"


@pytest.mark.asyncio
async def test_single_protein_with_two_components_rejected(client: AsyncClient) -> None:
    organism_id = await _organism(client)
    p1 = await _protein(client, organism_id, "P22222")
    p2 = await _protein(client, organism_id, "P33333")
    resp = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "Bad single", "target_type": "single_protein",
            "components": [
                {"protein_id": p1, "relationship": "single_protein"},
                {"protein_id": p2, "relationship": "single_protein"},
            ],
        },
    )
    assert resp.status_code == 422  # cardinality invariant violated


@pytest.mark.asyncio
async def test_update_target_preserves_components(client: AsyncClient) -> None:
    """Child-collection round-trip: a PATCH that swaps components persists correctly
    despite the base repo's raw-UPDATE version bump + delete-orphan flush."""
    organism_id = await _organism(client)
    p1 = await _protein(client, organism_id, "P44444")
    p2 = await _protein(client, organism_id, "P55555")
    p3 = await _protein(client, organism_id, "P66666")

    created = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "GABA-A", "target_type": "protein_complex",
            "components": [
                {"protein_id": p1, "relationship": "protein_subunit"},
                {"protein_id": p2, "relationship": "protein_subunit"},
            ],
        },
    )
    assert created.status_code == 201
    target_id = created.json()["id"]
    assert created.json()["version"] == 1

    patched = await client.patch(
        f"/api/v1/targets/{target_id}",
        json={"components": [
            {"protein_id": p2, "relationship": "protein_subunit"},
            {"protein_id": p3, "relationship": "protein_subunit"},
        ]},
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2
    returned = {c["protein_id"] for c in patched.json()["components"]}
    assert returned == {p2, p3}

    # Re-fetch confirms the swap persisted (delete-orphan removed p1, added p3)
    refetched = await client.get(f"/api/v1/targets/{target_id}")
    assert {c["protein_id"] for c in refetched.json()["components"]} == {p2, p3}
    assert len(refetched.json()["components"]) == 2
```

Run: `cd backend && uv run pytest tests/api/test_targets.py -v` → PASS.

- [ ] **Step 6: Run the suites + commit**

Run: `make test` (unit + import-linter), `make test-api`, `make lint` — all green. Confirm `git status` is clean (all wiring staged).

```bash
git add backend/src/protcellar backend/tests/api/test_targets.py
git commit -m "feat(target): Target API (workspace-scoped CRUD) + DI wiring + component round-trip test"
```

---

### Task 5: Re-enable the import-linter bounded-context `independence` contract + final verification

**Files:**
- Modify: `backend/pyproject.toml` (uncomment + complete the `independence` contract)

**Interfaces:**
- Produces: an active import-linter `independence` contract proving the five bounded contexts (`taxonomy`, `protein_catalog`, `target`, `workspace_config`, `audit_compliance`) do not import each other's domain.

- [ ] **Step 1: Re-enable the contract.** In `backend/pyproject.toml`, replace the commented-out block (the `# Re-enable when bounded-context modules exist ...` stanza) with the active contract:

```toml
[[tool.importlinter.contracts]]
name = "Bounded context independence"
type = "independence"
modules = [
    "protcellar.domain.taxonomy",
    "protcellar.domain.protein_catalog",
    "protcellar.domain.target",
    "protcellar.domain.workspace_config",
    "protcellar.domain.audit_compliance",
]
```

- [ ] **Step 2: Verify the contract holds** — Run: `cd backend && uv run lint-imports`. Expected: **3 contracts kept, 0 broken** (Clean Architecture layers, Domain purity, Bounded context independence).

> If `independence` reports a broken contract, a domain module is importing another context's domain (e.g. `target` importing `protein_catalog`). Fix by replacing the cross-context import with a `uuid.UUID` FK reference — do NOT weaken the contract. (The plans were written to avoid this; a failure here means an implementation drifted.)

- [ ] **Step 3: Full suite + commit**

Run: `make test-all` (all unit + api + the 3 import-linter contracts) → green.
Run: `make lint` (ruff + ruff-format + mypy) → clean.

```bash
git add backend/pyproject.toml
git commit -m "chore(target): re-enable bounded-context independence import-linter contract"
```

---

## Self-Review (run after implementing)

- **Spec coverage:** Implements spec §5.3 (`Target` aggregate root + `TargetComponent` ordered child → `Protein`; `target_type` ChEMBL subset; `organism_id`, `chembl_id`, `pharmacological_class`, `cross_references`; the **single-vs-complex cardinality invariant**, enforced and unit-tested) and §2 (interop seam: prot-cellar owns Target+Protein; `chembl_id` retained for chem-cellar reconciliation; no chem-cellar changes — the seam is kept clean by referencing Protein only by id). Re-enables the §3 bounded-context independence guarantee (§10 Q-context-independence).
- **Tenancy:** `Target` is workspace-scoped (the `Strain` pattern) — `require_editor` + `require_same_workspace`, `workspace_id` from `auth`, never the body. Verified in every use case.
- **Deferred (per spec "later" / out of v1 scope):** `target/bulk` import endpoint (Target is workspace-scoped tenant data, not snapshot reference data — ChEMBL target loading is a `prot-cellar-loader` concern; protein/organism bulk already cover the reference-import path); Pharos TDL facet, Open Targets tractability buckets, ChEMBL `target_relations`, variant/mutant sequences (spec §5.3 "Deferred"); relationship-vs-target_type cross-validation (only cardinality is enforced in v1); pre-verifying `protein_id`/`organism_id` existence in the use case (the DB FK enforces referential integrity, consistent with how `Strain` references `organism_id` — a bad id surfaces as a DB error; clean pre-validation is a later enhancement).
- **Type/name consistency to verify during implementation:** `Target` is a versioned `AggregateRoot` using `SQLAlchemyRepository` (NOT `EntityRepository` — the base-repo docstring's "Target" example refers to chem-cellar's old collapsed entity); `TargetComponentModel` has no version/workspace mixins (child entity, like `OrganismNameModel`); `_update_model` replaces `model.components` wholesale (delete-orphan); `update()`/`set_components()` re-validate cardinality before mutating; cardinality `ValidationError` propagates to a 422 (never caught into a `Failure`); the cross-reference JSON helpers are imported from `protein_catalog._xref_json` (infra→infra, contract-legal — a future cleanup could lift them to a context-neutral shared infra module).
- **Branch status after this plan:** Plans 0–3 complete on `feat/foundation`. Run a final whole-branch review of the Target work, then `superpowers:finishing-a-development-branch` — the branch (Foundation + Taxonomy + Protein Catalog + Target) is now feature-complete for v1 backend per spec §9, modulo the documented deferrals and the `prot-cellar-loader` (its own project).
```
