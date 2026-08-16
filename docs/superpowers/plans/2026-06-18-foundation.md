# prot-cellar Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a bootable, tested FastAPI backend skeleton for `prot-cellar` that mirrors chem-cellar's DDD + Clean Architecture + Railway foundation, with Sentinel auth, append-only audit, the cross-cutting identifier registry, and one exemplar vertical slice (`Organization`) proving the full domain→application→infrastructure→interface path.

**Architecture:** Copy chem-cellar's (`~/workspace/chem-vault2`) layered architecture verbatim, renaming the Python package `cellar` → `protcellar` and dropping all chemistry-specific dependencies (RDKit, ChEMBL pipeline, Temporal, lmfit, weasyprint, umap, etc.). Layers: `domain → application → infrastructure → interface`, enforced by import-linter. Use cases return `Result[T, DomainError]` (dry-python `returns`); persistence uses SQLAlchemy 2.0 async with optimistic concurrency; DI via Lagom; sync domain events dispatched post-commit; auth delegated to Sentinel.

**Tech Stack:** Python 3.13+, FastAPI, SQLAlchemy 2.0 async (asyncpg), PostgreSQL 16, Pydantic v2 + pydantic-settings, Alembic, Lagom, dry-python `returns`, duar-auth, structlog, Valkey (redis-py), `uv` package manager, pytest + pytest-asyncio + testcontainers, ruff, mypy (strict + returns plugin), import-linter.

## Global Constraints

- **Python:** `requires-python = ">=3.13"`. Target `py313`.
- **Package name:** `protcellar` (NOT `cellar`). Every ported file replaces `cellar.` imports with `protcellar.` and `from cellar` with `from protcellar`.
- **Reference source of truth:** chem-cellar at `/Users/sidx/workspace/chem-vault2/backend/src/cellar/`. Before porting any file, read the chem-cellar original; before writing any new use case, read chem-cellar's `docs/backend-code-guidelines.md` and `docs/patterns-and-conventions.md`.
- **Workspace scoping (security-critical):** Every Command/Query carries `workspace_id: uuid.UUID`; routes set it from `auth.workspace_id`, never from body/URL; repositories use `find_by_id_in_workspace`.
- **Auth guards** are the first lines of every use case: `require_editor(auth)` (or role needed) then `require_same_workspace(auth, input.workspace_id)`.
- **Railway:** Use cases return `Result[T, DomainError]`; expected failures → `Failure(...)`, never raised.
- **Optimistic concurrency:** every aggregate has `version: int`; updates are `WHERE id=? AND version=?` → `version+1`; 0 rows → `ConcurrencyConflictError`. Append-only `AuditOperation` is exempt.
- **Ruff:** line-length 99, double quotes, target py313, select `["E","F","W","I","UP","B","SIM","RUF"]`.
- **Mypy:** `strict = true`, plugin `returns.contrib.mypy.returns_plugin`.
- **Commit** after every task with a Conventional Commit message.

---

## File Structure

```
backend/
  pyproject.toml          ruff.toml   mypy.ini   alembic.ini   Dockerfile
  alembic/env.py  alembic/script.py.mako  alembic/versions/
  src/protcellar/
    __init__.py   version.py
    domain/
      shared/        entity.py aggregate_root.py events.py errors.py value_objects.py
      audit_compliance/   models.py enums.py repository.py
      workspace_config/   organization.py events.py repository.py enums.py
    application/
      shared/        command.py query.py use_case.py unit_of_work.py event_dispatcher.py
      auth.py
      workspace_config/   create_organization.py update_organization.py get_organization.py list_organizations.py
    infrastructure/
      persistence/   settings.py database.py unit_of_work.py
        sqlalchemy/  base.py base_repository.py
          workspace_config/  models.py organization_repository.py
          audit_compliance/  models.py audit_repository.py
      messaging/     event_dispatcher.py audit_event_handler.py
      identifiers/   registry.py            # NEW — cross-cutting identifier registry
      sentinel/      settings.py auth.py
      di/            container.py
      logging/       __init__.py settings.py config.py
    interface/
      app.py  error_handlers.py
      middleware/    request_context.py
      dependencies/  _core.py _workspace_config.py _audit.py
      routes/        organizations.py version.py
    domain/shared/cross_reference.py        # NEW — CrossReference VO
  tests/
    conftest.py
    fakes/fake_auth.py
    unit/domain/shared/   tests for AggregateRoot, CrossReference, identifier registry
    unit/domain/workspace_config/test_organization.py
    unit/application/test_auth_guards.py
    api/conftest.py  api/test_organizations.py  api/test_health.py
docker-compose.yml  docker-compose.dev.yml  Makefile  .env.example
```

---

### Task 1: Repo scaffold, tooling, and import-linter contracts

**Files:**
- Create: `backend/pyproject.toml`, `backend/ruff.toml`, `backend/mypy.ini`, `backend/src/protcellar/__init__.py`, `backend/src/protcellar/version.py`, and empty `__init__.py` for each package dir in the File Structure above.
- Create: `backend/.python-version` containing `3.13`.

**Interfaces:**
- Produces: importable package `protcellar`; `protcellar.version.build_info()` → object with `.version: str`, `.git_sha: str`, `.build_date: str`, `.environment: str`.

- [ ] **Step 1: Write `backend/pyproject.toml`** (chem-cellar's, trimmed — no chemistry/Temporal deps):

```toml
[project]
name = "protcellar"
version = "0.1.0"
description = "Protein, organism & target catalog (bio-side sibling of cellar)"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "python-multipart>=0.0.20",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "lagom>=2.7.0",
    "returns>=0.23.0",
    "duar-auth>=0.11.0",
    "pyjwt[crypto]>=2.10.0",
    "httpx>=0.28.0",
    "redis>=5.2.0",
    "structlog>=24.4.0",
    "biopython>=1.84",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "testcontainers[postgres]>=4.0.0",
    "factory-boy>=3.3.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "pre-commit>=4.0.0",
    "import-linter>=2.11",
    "respx>=0.23.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/protcellar"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.importlinter]
root_packages = ["protcellar"]

[[tool.importlinter.contracts]]
name = "Clean Architecture layers"
type = "layers"
layers = [
    "protcellar.interface",
    "protcellar.infrastructure",
    "protcellar.application",
    "protcellar.domain",
]

[[tool.importlinter.contracts]]
name = "Domain purity"
type = "forbidden"
source_modules = ["protcellar.domain"]
forbidden_modules = [
    "protcellar.application",
    "protcellar.infrastructure",
    "protcellar.interface",
    "fastapi",
    "sqlalchemy",
    "asyncpg",
    "redis",
    "lagom",
]

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

> Note: the `taxonomy`, `protein_catalog`, and `target` modules don't exist yet — import-linter ignores unmatched `independence` modules until they're created, so listing them now is safe and documents intent. If `lint-imports` errors on a missing module, comment those three lines until Plan 1 creates them.

- [ ] **Step 2: Write `backend/ruff.toml`:**

```toml
target-version = "py313"
line-length = 99
src = ["src"]

[lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends",
    "fastapi.Query",
    "fastapi.File",
    "fastapi.Body",
    "fastapi.Path",
    "fastapi.Header",
]

[format]
quote-style = "double"
```

- [ ] **Step 3: Write `backend/mypy.ini`:**

```ini
[mypy]
python_version = 3.13
strict = true
plugins = returns.contrib.mypy.returns_plugin
warn_return_any = true
warn_unused_configs = true

[mypy-asyncpg.*]
ignore_missing_imports = true

[mypy-lagom.*]
ignore_missing_imports = true

[mypy-duar_auth.*]
ignore_missing_imports = true
```

- [ ] **Step 4: Write `backend/src/protcellar/version.py`:**

```python
"""Build/version info, surfaced at GET /version."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildInfo:
    version: str
    git_sha: str
    build_date: str
    environment: str


def build_info() -> BuildInfo:
    return BuildInfo(
        version=os.getenv("APP_VERSION", "0.1.0"),
        git_sha=os.getenv("GIT_SHA", "dev"),
        build_date=os.getenv("BUILD_DATE", "unknown"),
        environment=os.getenv("APP_ENV", "development"),
    )
```

- [ ] **Step 5: Create the package tree** — `src/protcellar/__init__.py` and an empty `__init__.py` in every package directory listed in the File Structure (domain/shared, domain/audit_compliance, domain/workspace_config, application/shared, application/workspace_config, infrastructure/persistence/sqlalchemy/{workspace_config,audit_compliance}, infrastructure/{messaging,identifiers,sentinel,di,logging}, interface/{middleware,dependencies,routes}). Leave bio-context dirs (taxonomy/protein_catalog/target) for Plan 1.

- [ ] **Step 6: Install and verify**

Run: `cd backend && uv sync`
Run: `uv run python -c "import protcellar; from protcellar.version import build_info; print(build_info().version)"`
Expected: prints `0.1.0`.
Run: `uv run lint-imports`
Expected: contracts pass (no modules to check yet → "Contracts: N kept, 0 broken").

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "chore(backend): scaffold uv project, ruff/mypy/import-linter config, version module"
```

---

### Task 2: Domain shared base (Entity, AggregateRoot, DomainEvent, errors)

**Files:**
- Create: `backend/src/protcellar/domain/shared/entity.py`, `events.py`, `errors.py`
- Test: `backend/tests/unit/domain/shared/test_aggregate_root.py`

**Interfaces:**
- Produces: `Entity`, `AggregateRoot` (with `version`, `register_event`, `collect_events`, `clear_events`); `DomainEvent` base (frozen kw_only dataclass: `event_id`, `occurred_at`, `aggregate_id`, `aggregate_type`, `workspace_id`); errors `DomainError`, `NotFoundError`, `ConflictError`, `ConcurrencyConflictError`, `ValidationError`, `AuthorizationError`, `DataLockedError`, `GoneError`.

- [ ] **Step 1: Write the failing test** `tests/unit/domain/shared/test_aggregate_root.py`:

```python
import uuid

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.events import DomainEvent


def test_register_and_collect_events_then_clear() -> None:
    agg = AggregateRoot()
    assert agg.version == 1
    ev = DomainEvent(aggregate_id=agg.id, aggregate_type="X", workspace_id=uuid.uuid4())
    agg.register_event(ev)
    collected = agg.collect_events()
    assert collected == [ev]
    agg.clear_events()
    assert agg.collect_events() == []
```

- [ ] **Step 2: Run test to verify it fails** — `cd backend && uv run pytest tests/unit/domain/shared/test_aggregate_root.py -v` → FAIL (module not found).

- [ ] **Step 3: Port the three files from chem-cellar** with the `cellar`→`protcellar` rename. They are nearly identical; transcribe:

`domain/shared/events.py`:

```python
"""Domain event base class."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events (immutable, frozen)."""

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: uuid.UUID
    aggregate_type: str
    workspace_id: uuid.UUID
```

`domain/shared/entity.py` — `Entity` + `AggregateRoot` exactly as chem-cellar (`/Users/sidx/workspace/chem-vault2/backend/src/cellar/domain/shared/entity.py`), adding the event methods to `AggregateRoot`:

```python
"""Entity and AggregateRoot base classes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from protcellar.domain.shared.events import DomainEvent


class Entity:
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid.uuid4()
        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id})"


class AggregateRoot(Entity):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at)
        self.version = version
        self._domain_events: list[DomainEvent] = []

    def register_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        return list(self._domain_events)

    def clear_events(self) -> None:
        self._domain_events.clear()
```

`domain/shared/errors.py` — copy chem-cellar's verbatim (it has no `cellar.` imports), keeping `DomainError`, `NotFoundError`, `ConflictError`, `ConcurrencyConflictError`, `ValidationError`, `AuthorizationError`, `DataLockedError`, `CollectionFrozenError`, `ServiceUnavailableError`, `GoneError`. Source: `/Users/sidx/workspace/chem-vault2/backend/src/cellar/domain/shared/errors.py`.

- [ ] **Step 4: Run test to verify it passes** — `uv run pytest tests/unit/domain/shared/test_aggregate_root.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/shared backend/tests/unit/domain/shared
git commit -m "feat(domain): shared Entity/AggregateRoot/DomainEvent/errors base"
```

---

### Task 3: Application shared base + auth guards

**Files:**
- Create: `backend/src/protcellar/application/shared/command.py`, `query.py`, `use_case.py`, `unit_of_work.py`
- Create: `backend/src/protcellar/application/auth.py`
- Test: `backend/tests/unit/application/test_auth_guards.py`

**Interfaces:**
- Produces: `Command`, `Query` (frozen kw_only dataclass bases); `UseCase` protocol; `UnitOfWork` protocol (`session` property, `track(aggregate)`, async `commit() -> list[DomainEvent]`, used as async context manager); `AuthContext` protocol (`user_id`, `workspace_id`, `workspace_role`, `is_admin`, `has_role`); guards `require_workspace_role`, `require_editor`, `require_admin`, `require_authenticated`, `require_same_workspace`, `require_same_user`.

- [ ] **Step 1: Write the failing test** `tests/unit/application/test_auth_guards.py`:

```python
import uuid

import pytest

from protcellar.application.auth import require_editor, require_same_workspace
from protcellar.domain.shared.errors import AuthorizationError, NotFoundError


class _Auth:
    def __init__(self, role: str, ws: uuid.UUID) -> None:
        self._role, self._ws = role, ws

    @property
    def user_id(self) -> uuid.UUID: return uuid.uuid4()
    @property
    def workspace_id(self) -> uuid.UUID: return self._ws
    @property
    def workspace_role(self) -> str: return self._role
    @property
    def is_admin(self) -> bool: return self._role == "admin"
    def has_role(self, minimum_role: str) -> bool:
        order = {"viewer": 0, "editor": 1, "admin": 2}
        return order[self._role] >= order[minimum_role]


def test_require_editor_blocks_viewer() -> None:
    with pytest.raises(AuthorizationError):
        require_editor(_Auth("viewer", uuid.uuid4()))


def test_require_editor_allows_none_for_workers() -> None:
    require_editor(None)  # system calls bypass


def test_require_same_workspace_raises_notfound_on_mismatch() -> None:
    with pytest.raises(NotFoundError):
        require_same_workspace(_Auth("admin", uuid.uuid4()), uuid.uuid4())
```

- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/unit/application/test_auth_guards.py -v` → FAIL.

- [ ] **Step 3: Port the shared bases.** `command.py`, `query.py`, `use_case.py` are copied verbatim from chem-cellar (rename `cellar`→`protcellar` in `use_case.py`'s import). `unit_of_work.py` is the protocol — port chem-cellar's `application/shared/unit_of_work.py` (read it first). Write `application/auth.py` as chem-cellar's **minus** the project-role machinery (prot-cellar has no `research_organization` context in v1):

```python
"""Application-layer auth context protocol and guards."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.shared.errors import AuthorizationError, NotFoundError


@runtime_checkable
class AuthContext(Protocol):
    """Auth context available to use cases. Satisfied by Sentinel's RequestAuth."""

    @property
    def user_id(self) -> uuid.UUID: ...
    @property
    def workspace_id(self) -> uuid.UUID: ...
    @property
    def workspace_role(self) -> str: ...
    @property
    def is_admin(self) -> bool: ...
    def has_role(self, minimum_role: str) -> bool: ...


def require_workspace_role(auth: AuthContext | None, minimum_role: str) -> None:
    if auth is None:
        return
    if not auth.has_role(minimum_role):
        raise AuthorizationError(
            f"Requires at least '{minimum_role}' role",
            detail=f"Current role: '{auth.workspace_role}'",
        )


def require_editor(auth: AuthContext | None) -> None:
    require_workspace_role(auth, "editor")


def require_admin(auth: AuthContext | None) -> None:
    require_workspace_role(auth, "admin")


def require_authenticated(auth: AuthContext | None) -> None:
    if auth is None:
        raise AuthorizationError("Authentication required")


def require_same_workspace(auth: AuthContext | None, workspace_id: uuid.UUID | None) -> None:
    if auth is None:
        return
    if workspace_id is None:
        raise AuthorizationError("workspace_id must not be None")
    if auth.workspace_id != workspace_id:
        raise NotFoundError("Entity")


def require_same_user(auth: AuthContext | None, user_id: uuid.UUID) -> None:
    if auth is None:
        return
    if auth.user_id != user_id:
        raise AuthorizationError("Cannot act on another user's personal data")
```

- [ ] **Step 4: Run test to verify it passes** — `uv run pytest tests/unit/application/test_auth_guards.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/application backend/tests/unit/application
git commit -m "feat(application): shared Command/Query/UseCase/UnitOfWork bases and auth guards"
```

---

### Task 4: Persistence base (settings, engine, mixins, base repository, UoW)

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/settings.py`, `database.py`, `unit_of_work.py`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/base.py`, `base_repository.py`
- Test: `backend/tests/unit/infrastructure/test_base_models.py` (light unit test of mixin column presence; full repository behavior is integration-tested in Task 10's api tests)

**Interfaces:**
- Produces: `DatabaseSettings` (reads `DATABASE_URL`, `POOL_SIZE`, …); `create_engine_and_sessionmaker(settings) -> tuple[AsyncEngine, async_sessionmaker]`; SA `Base`, `EntityModelMixin` (id/created_at/updated_at), `WorkspaceIdMixin` (workspace_id indexed), `VersionMixin` (version); `AsyncUnitOfWork` (implements the `UnitOfWork` protocol — `session`, `track`, `commit() -> list[DomainEvent]`, async context manager, rollback on error); `SQLAlchemyRepository[T, ModelType]` abstract base with `find_by_id_in_workspace`, `save` (optimistic concurrency), and the `_to_domain`/`_to_model`/`_update_model` contract.

- [ ] **Step 1: Port `persistence/settings.py`** verbatim (chem-cellar's `DatabaseSettings` — already independent; just keep it). See `/Users/sidx/workspace/chem-vault2/backend/src/cellar/infrastructure/persistence/settings.py`.

- [ ] **Step 2: Write `persistence/database.py`** (engine + sessionmaker factory; port chem-cellar's equivalent — read `infrastructure/persistence/database.py`):

```python
"""Async engine + sessionmaker factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from protcellar.infrastructure.persistence.settings import DatabaseSettings


def create_engine_and_sessionmaker(
    settings: DatabaseSettings | None = None,
) -> tuple[AsyncEngine, async_sessionmaker]:
    settings = settings or DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=settings.pool_pre_ping,
        echo=settings.echo,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 3: Port `sqlalchemy/base.py`** — the `Base(DeclarativeBase)` + `EntityModelMixin` + `WorkspaceIdMixin` + `VersionMixin` exactly as chem-cellar (`infrastructure/persistence/sqlalchemy/base.py`):

```python
"""SQLAlchemy declarative base and composable mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EntityModelMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WorkspaceIdMixin:
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
```

- [ ] **Step 4: Port `persistence/unit_of_work.py`** (`AsyncUnitOfWork`) and `sqlalchemy/base_repository.py` (`SQLAlchemyRepository`) verbatim from chem-cellar with the rename. These are non-trivial; read the chem-cellar originals (`infrastructure/persistence/unit_of_work.py` and `infrastructure/persistence/sqlalchemy/base_repository.py`) and transcribe exactly — they implement aggregate tracking, post-commit event collection, the `WHERE id=? AND version=?` optimistic-concurrency UPDATE raising `ConcurrencyConflictError` on zero rows, and the defence-in-depth workspace check on `save()`.

- [ ] **Step 5: Write a light unit test** `tests/unit/infrastructure/test_base_models.py`:

```python
from protcellar.infrastructure.persistence.sqlalchemy.base import (
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


def test_mixins_declare_expected_columns() -> None:
    assert hasattr(EntityModelMixin, "id")
    assert hasattr(WorkspaceIdMixin, "workspace_id")
    assert hasattr(VersionMixin, "version")
```

Run: `uv run pytest tests/unit/infrastructure/test_base_models.py -v` → PASS.

- [ ] **Step 6: Type-check and commit**

Run: `uv run mypy src/protcellar/infrastructure/persistence` → no errors.
```bash
git add backend/src/protcellar/infrastructure/persistence backend/tests/unit/infrastructure
git commit -m "feat(infra): persistence settings, engine, SA mixins, base repository, async UoW"
```

---

### Task 5: Event dispatcher, CrossReference VO, and identifier registry (NEW cross-cutting code)

**Files:**
- Create: `backend/src/protcellar/application/shared/event_dispatcher.py` (protocol), `backend/src/protcellar/infrastructure/messaging/event_dispatcher.py` (impl)
- Create: `backend/src/protcellar/domain/shared/cross_reference.py`
- Create: `backend/src/protcellar/infrastructure/identifiers/registry.py`
- Test: `tests/unit/domain/shared/test_cross_reference.py`, `tests/unit/infrastructure/test_identifier_registry.py`, `tests/unit/infrastructure/test_event_dispatcher.py`

**Interfaces:**
- Produces: `EventDispatcherProtocol` (`register(type, handler)`, async `dispatch_all(events)`); `EventDispatcher` impl (sync, in-process, exact-match + `DomainEvent` catch-all); `CrossReference` VO `{database: str, accession: str, properties: dict | None, evidence: str | None}` with a `to_curie()` method; `IdentifierRegistry` with `validate(prefix, accession) -> bool`, `resolve_url(prefix, accession) -> str | None`, and a seeded prefix table.

- [ ] **Step 1: Write `domain/shared/cross_reference.py`** (NEW — pure domain VO):

```python
"""Generic cross-reference value object (UniProt DR-line shape)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CrossReference:
    """A reference to a record in an external database.

    `database` is a registry prefix (e.g. "uniprot", "pdb", "go").
    `accession` is the external id (e.g. "P0DTC2").
    `properties` holds secondary ids / qualifiers (e.g. PDB method+resolution).
    """

    database: str
    accession: str
    properties: dict[str, str] | None = None
    evidence: str | None = None

    def to_curie(self) -> str:
        return f"{self.database}:{self.accession}"
```

- [ ] **Step 2: Write its test** `tests/unit/domain/shared/test_cross_reference.py`:

```python
from protcellar.domain.shared.cross_reference import CrossReference


def test_curie() -> None:
    xref = CrossReference(database="uniprot", accession="P0DTC2")
    assert xref.to_curie() == "uniprot:P0DTC2"
```

Run: `uv run pytest tests/unit/domain/shared/test_cross_reference.py -v` → PASS.

- [ ] **Step 3: Write the identifier registry test** `tests/unit/infrastructure/test_identifier_registry.py`:

```python
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry


def test_validates_uniprot_accession() -> None:
    reg = IdentifierRegistry.default()
    assert reg.validate("uniprot", "P0DTC2") is True
    assert reg.validate("uniprot", "not-an-accession") is False


def test_resolves_url() -> None:
    reg = IdentifierRegistry.default()
    assert reg.resolve_url("uniprot", "P0DTC2") == "https://identifiers.org/uniprot:P0DTC2"


def test_unknown_prefix_is_invalid() -> None:
    reg = IdentifierRegistry.default()
    assert reg.validate("bogusdb", "x") is False
    assert reg.resolve_url("bogusdb", "x") is None
```

Run: `uv run pytest tests/unit/infrastructure/test_identifier_registry.py -v` → FAIL.

- [ ] **Step 4: Write `infrastructure/identifiers/registry.py`** (NEW — the Bioregistry-style prefix table; regexes verified during the domain review):

```python
"""Embedded Bioregistry-style identifier registry: validation + URL resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _Prefix:
    pattern: re.Pattern[str]
    uri_template: str  # {curie} or {acc} substitution


_DEFAULT_PREFIXES: dict[str, tuple[str, str]] = {
    # prefix: (regex, uri_template using {curie})
    "uniprot": (
        r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$",
        "https://identifiers.org/uniprot:{acc}",
    ),
    "ncbitaxon": (r"^\d+$", "https://identifiers.org/taxonomy:{acc}"),
    "ncbigene": (r"^\d+$", "https://identifiers.org/ncbigene:{acc}"),
    "refseq": (
        r"^(((AC|AP|NC|NG|NM|NP|NR|NT|NW|WP|XM|XP|XR|YP|ZP)_\d+)|(NZ_[A-Z]{2,4}\d+))(\.\d+)?$",
        "https://identifiers.org/refseq:{acc}",
    ),
    "ensembl": (r"^ENS[FPTG]\d{11}(\.\d+)?$", "https://identifiers.org/ensembl:{acc}"),
    "pdb": (r"^([0-9][A-Za-z0-9]{3}|pdb_[a-z0-9]{8})$", "https://identifiers.org/pdb:{acc}"),
    "interpro": (r"^IPR\d{6}$", "https://identifiers.org/interpro:{acc}"),
    "pfam": (r"^PF\d{5}$", "https://identifiers.org/pfam:{acc}"),
    "go": (r"^GO:\d{7}$", "https://identifiers.org/go:{acc}"),
    "ec": (r"^\d+\.(\d+|-)\.(\d+|-)\.(n?\d+|-)$", "https://identifiers.org/ec-code:{acc}"),
    "chembl.target": (r"^CHEMBL\d+$", "https://identifiers.org/chembl.target:{acc}"),
    "proteome": (r"^UP\d{9}$", "https://www.uniprot.org/proteomes/{acc}"),
}


class IdentifierRegistry:
    def __init__(self, prefixes: dict[str, _Prefix]) -> None:
        self._prefixes = prefixes

    @classmethod
    def default(cls) -> IdentifierRegistry:
        return cls(
            {
                prefix: _Prefix(re.compile(rx), uri)
                for prefix, (rx, uri) in _DEFAULT_PREFIXES.items()
            }
        )

    def validate(self, prefix: str, accession: str) -> bool:
        entry = self._prefixes.get(prefix)
        return bool(entry and entry.pattern.match(accession))

    def resolve_url(self, prefix: str, accession: str) -> str | None:
        entry = self._prefixes.get(prefix)
        if entry is None or not entry.pattern.match(accession):
            return None
        return entry.uri_template.format(acc=accession)
```

Run: `uv run pytest tests/unit/infrastructure/test_identifier_registry.py -v` → PASS.

- [ ] **Step 5: Port the event dispatcher.** Write `application/shared/event_dispatcher.py` (the `EventDispatcherProtocol` — read chem-cellar's) and `infrastructure/messaging/event_dispatcher.py` (the sync `EventDispatcher` with exact-match + `DomainEvent` catch-all dispatch). Port from `/Users/sidx/workspace/chem-vault2/backend/src/cellar/infrastructure/messaging/event_dispatcher.py`. Add `tests/unit/infrastructure/test_event_dispatcher.py`:

```python
import uuid

import pytest

from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher


@pytest.mark.asyncio
async def test_dispatch_calls_exact_and_catchall_handlers() -> None:
    seen: list[str] = []
    disp = EventDispatcher()

    async def catchall(ev: DomainEvent) -> None:
        seen.append("catchall")

    disp.register(DomainEvent, catchall)
    ev = DomainEvent(aggregate_id=uuid.uuid4(), aggregate_type="X", workspace_id=uuid.uuid4())
    await disp.dispatch_all([ev])
    assert seen == ["catchall"]
```

Run: `uv run pytest tests/unit/infrastructure/test_event_dispatcher.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/domain/shared/cross_reference.py \
        backend/src/protcellar/infrastructure/identifiers \
        backend/src/protcellar/infrastructure/messaging \
        backend/src/protcellar/application/shared/event_dispatcher.py \
        backend/tests/unit
git commit -m "feat(shared): CrossReference VO, identifier registry, sync event dispatcher"
```

---

### Task 6: Sentinel auth integration + DI container scaffold

**Files:**
- Create: `backend/src/protcellar/infrastructure/duar/settings.py`, `auth.py`
- Create: `backend/src/protcellar/infrastructure/di/container.py`
- Create: `backend/src/protcellar/infrastructure/logging/{__init__.py,settings.py,config.py}`

**Interfaces:**
- Consumes: `DatabaseSettings`, `create_engine_and_sessionmaker`, `EventDispatcher`.
- Produces: `DuarSettings`; `get_duar() -> Sentinel` (authz mode, registers `SERVICE_ACTIONS`); `create_container() -> lagom.Container` binding `DatabaseSettings`, `AsyncEngine`, `async_sessionmaker`, `EventDispatcher` (singleton), `IdentifierRegistry` (singleton); `configure_logging()`.

- [ ] **Step 1: Port `sentinel/settings.py`** verbatim with `service_name = "protcellar"`:

```python
"""Sentinel auth configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DuarSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DUAR_", env_file=".env")

    url: str = "http://localhost:9003"
    service_name: str = "protcellar"
    service_key: str = ""
    idp_jwks_url: str = "https://www.googleapis.com/oauth2/v3/certs"
    idp_audience: str = ""
    idp_issuer: str = "https://accounts.google.com"
    cache_ttl: float = 120
```

- [ ] **Step 2: Write `sentinel/auth.py`** — port chem-cellar's pattern (`create_duar` + a module-level `get_duar()` singleton accessor + `SERVICE_ACTIONS`), with bio-appropriate actions. Read `/Users/sidx/workspace/chem-vault2/backend/src/cellar/infrastructure/duar/auth.py` for the exact `Sentinel(...)` constructor call and `get_duar` shape. Define:

```python
SERVICE_ACTIONS = [
    {"action": "protcellar:read", "description": "Read catalog entities"},
    {"action": "protcellar:write", "description": "Create/update catalog entities"},
    {"action": "protcellar:bulk_import", "description": "Bulk-import reference data"},
    {"action": "protcellar:admin_config", "description": "Modify workspace settings"},
]
```

- [ ] **Step 3: Port the logging package** (`logging/{__init__.py exposing configure_logging, settings.py, config.py}`) from chem-cellar's `infrastructure/logging/` with the rename. This provides `configure_logging()` and `bind_user_context(...)` used by the request-context middleware.

- [ ] **Step 4: Write `di/container.py`** — port chem-cellar's `create_container` shape but bind only the foundation singletons (no chemistry services). Read `/Users/sidx/workspace/chem-vault2/backend/src/cellar/infrastructure/di/container.py`. The container must bind: `DatabaseSettings`, `AsyncEngine` + `async_sessionmaker` (from `create_engine_and_sessionmaker`), `EventDispatcher` (Singleton), `IdentifierRegistry` (Singleton). Context-specific use cases are registered by the `interface/dependencies/_*.py` modules (Task 10).

- [ ] **Step 5: Verify import + type-check**

Run: `uv run python -c "from protcellar.infrastructure.di.container import create_container"` (will require env or defaults — if it constructs the engine eagerly, guard construction so import alone doesn't need `DATABASE_URL`; bind via factory lambdas as chem-cellar does).
Run: `uv run mypy src/protcellar/infrastructure/duar src/protcellar/infrastructure/di` → no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/infrastructure/duar \
        backend/src/protcellar/infrastructure/di \
        backend/src/protcellar/infrastructure/logging
git commit -m "feat(infra): Sentinel auth integration, logging, Lagom DI container scaffold"
```

---

### Task 7: FastAPI app bootstrap (trimmed) + error handlers + middleware + health/version

**Files:**
- Create: `backend/src/protcellar/interface/error_handlers.py`, `backend/src/protcellar/interface/middleware/request_context.py`, `backend/src/protcellar/interface/routes/version.py`, `backend/src/protcellar/interface/app.py`
- Test: `backend/tests/api/test_health.py`

**Interfaces:**
- Consumes: `create_container`, `get_duar`, `configure_logging`, `EventDispatcher`, `AuditEventHandler` (added in Task 9 — bootstrap wires it conditionally/after Task 9), `register_error_handlers`, `build_info`.
- Produces: `create_app() -> FastAPI` and module-level `app`; `register_error_handlers(app)`; `result_to_response(result)`; `GET /health`, `GET /version`.

- [ ] **Step 1: Port `interface/error_handlers.py`** verbatim with rename (the `register_error_handlers` + `result_to_response` + `result_value_or_error` shown in chem-cellar's `interface/error_handlers.py`). Drop nothing — all error types map cleanly.

- [ ] **Step 2: Port `interface/middleware/request_context.py`** from chem-cellar (`RequestContextMiddleware` — binds a request_id and clears logging context per request).

- [ ] **Step 3: Write `interface/routes/version.py`:**

```python
"""Unauthenticated version endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.version import build_info

router = APIRouter(tags=["meta"])


class VersionResponse(BaseModel):
    version: str
    git_sha: str
    build_date: str
    environment: str


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    info = build_info()
    return VersionResponse(
        version=info.version,
        git_sha=info.git_sha,
        build_date=info.build_date,
        environment=info.environment,
    )
```

- [ ] **Step 4: Write `interface/app.py`** — the **trimmed** version of chem-cellar's bootstrap (NO Temporal, NO chemistry routers). This is the canonical pattern; the router includes for bio contexts are appended in Plan 1:

```python
"""FastAPI application factory: Sentinel auth, DI container, error handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.di.container import create_container
from protcellar.infrastructure.logging import configure_logging
from protcellar.infrastructure.messaging.audit_event_handler import AuditEventHandler
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.duar.auth import get_duar
from protcellar.interface.error_handlers import register_error_handlers
from protcellar.interface.middleware.request_context import RequestContextMiddleware
from protcellar.version import build_info


def create_app() -> FastAPI:
    sentinel = get_duar()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        container = create_container()
        app.state.container = container

        # Wire append-only audit as a catch-all domain-event handler
        dispatcher = container[EventDispatcher]
        session_factory = container[async_sessionmaker]
        dispatcher.register(DomainEvent, AuditEventHandler(session_factory))

        async with sentinel.lifespan(app):
            yield

        engine = container[AsyncEngine]
        await engine.dispose()

    app = FastAPI(
        title="prot-cellar",
        version=build_info().version,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    sentinel.protect(app, exclude_paths=["/health", "/version", "/docs", "/openapi.json"])

    import os

    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    from protcellar.interface.routes.version import router as version_router

    app.include_router(version_router)

    # Bio-context routers are included here by later plans, e.g.:
    #   from protcellar.interface.routes.organizations import router as org_router
    #   app.include_router(org_router)

    return app


app = create_app()
```

> This step depends on Task 9's `AuditEventHandler`. If executing strictly in order, stub `AuditEventHandler` as a no-op for this task and replace it in Task 9, OR reorder so Task 9 precedes the `app.py` audit wiring. Recommended: implement Task 9 before running the app for the first time. The health test below uses a test app that does not require the lifespan (see api/conftest in Task 11).

- [ ] **Step 5: Write `tests/api/test_health.py`** (uses the `client` fixture built in Task 11):

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version(client: AsyncClient) -> None:
    resp = await client.get("/version")
    assert resp.status_code == 200
    assert "version" in resp.json()
```

(This test is run green at the end of Task 11 once the test client exists.)

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/interface backend/tests/api/test_health.py
git commit -m "feat(interface): trimmed FastAPI bootstrap, error handlers, request-context mw, health/version"
```

---

### Task 8: Alembic async migrations setup

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (empty dir with `.gitkeep`)

**Interfaces:**
- Produces: `alembic upgrade head` works against the dev DB; `env.py` targets `Base.metadata` and imports all SA model modules so autogenerate sees them.

- [ ] **Step 1: Port `alembic.ini` and `alembic/env.py`** from chem-cellar (`/Users/sidx/workspace/chem-vault2/backend/alembic/env.py` and `alembic.ini`) with the rename. The `env.py` must: read `DATABASE_URL` from env, use the async engine, set `target_metadata = Base.metadata`, and **import every module that defines SA models** so `--autogenerate` discovers them. For now that's the audit + workspace_config models (Tasks 9–10); add a central `protcellar.infrastructure.persistence.sqlalchemy.metadata` import aggregator module that imports all model modules, and import it in `env.py`.

- [ ] **Step 2: Create `script.py.mako`** — copy chem-cellar's verbatim.

- [ ] **Step 3: Commit** (migrations are generated in Tasks 9–10):

```bash
git add backend/alembic backend/alembic.ini
git commit -m "build(db): alembic async migration environment"
```

---

### Task 9: Audit & Compliance context (append-only) + audit event handler

**Files:**
- Create: `backend/src/protcellar/domain/audit_compliance/{models.py,enums.py,repository.py}`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/audit_compliance/{models.py,audit_repository.py}`
- Create: `backend/src/protcellar/infrastructure/messaging/audit_event_handler.py`
- Create: migration `backend/alembic/versions/xxxx_audit_tables.py`
- Test: `tests/unit/domain/audit_compliance/test_audit_operation.py`

**Interfaces:**
- Consumes: `DomainEvent`, `async_sessionmaker`.
- Produces: `AuditOperation`/`AuditEntry`/`ElectronicSignature` dataclasses + enums; `AuditRepository` (append-only `save`); `AuditEventHandler(session_factory)` — an async callable `(DomainEvent) -> None` that records an `AuditOperation` per event.

- [ ] **Step 1: Port `domain/audit_compliance/models.py` and `enums.py`** from chem-cellar, **trimming `OperationType`** to bio-relevant + generic values:

```python
class OperationType(StrEnum):
    DATA_ENTRY = "data_entry"
    PROPERTY_EDIT = "property_edit"
    BULK_IMPORT = "bulk_import"
    ACCESS_CHANGE = "access_change"
    REFERENCE_SYNC = "reference_sync"   # NEW — UniProt/NCBI/ChEMBL refresh
    ADMIN_HARD_DELETE = "admin_hard_delete"
```

Keep `ActorType`, `AuditStatus`, `AuditAction`, `AuthMethod` verbatim. Keep `models.py` (`AuditOperation`, `AuditEntry`, `ElectronicSignature`) verbatim with rename.

- [ ] **Step 2: Write the domain unit test** `tests/unit/domain/audit_compliance/test_audit_operation.py`:

```python
import uuid

from protcellar.domain.audit_compliance.enums import AuditAction
from protcellar.domain.audit_compliance.models import AuditEntry, AuditOperation


def test_add_entry_sets_operation_id() -> None:
    op = AuditOperation(workspace_id=uuid.uuid4(), entity_type="Organism")
    entry = AuditEntry(entity_type="Organism", field_name="name", action=AuditAction.CREATE)
    op.add_entry(entry)
    assert op.entries[0].operation_id == op.id
```

Run: `uv run pytest tests/unit/domain/audit_compliance/test_audit_operation.py -v` → PASS.

- [ ] **Step 3: Port the SA models + repository + audit_event_handler** from chem-cellar (`infrastructure/persistence/sqlalchemy/audit/` and `infrastructure/messaging/audit_event_handler.py` — read them). The handler maps a `DomainEvent` → an `AuditOperation` row (workspace_id, entity_type=`event.aggregate_type`, entity_id=`event.aggregate_id`, operation_type=`DATA_ENTRY`, actor_type=`SYSTEM`) and persists it append-only in its own session.

- [ ] **Step 4: Generate and apply the migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "audit tables"`
Run: `uv run alembic upgrade head`
Expected: `audit_operations`, `audit_entries`, `electronic_signatures` tables created.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/audit_compliance \
        backend/src/protcellar/infrastructure/persistence/sqlalchemy/audit_compliance \
        backend/src/protcellar/infrastructure/messaging/audit_event_handler.py \
        backend/alembic/versions backend/tests/unit/domain/audit_compliance
git commit -m "feat(audit): append-only audit context + domain-event audit handler"
```

---

### Task 10: Organization exemplar vertical slice (the pattern to copy)

**Files:**
- Create: `backend/src/protcellar/domain/workspace_config/{organization.py,events.py,repository.py,enums.py}`
- Create: `backend/src/protcellar/application/workspace_config/{create_organization.py,update_organization.py,get_organization.py,list_organizations.py}`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_config/{models.py,organization_repository.py}`
- Create: `backend/src/protcellar/interface/routes/organizations.py`
- Create: `backend/src/protcellar/interface/dependencies/{_core.py,_workspace_config.py}`
- Modify: `backend/src/protcellar/interface/app.py` (include `org_router`)
- Create: migration for `organizations` table
- Test: `tests/unit/domain/workspace_config/test_organization.py`, `tests/api/test_organizations.py`

**Interfaces:**
- Consumes: everything from Tasks 2–9.
- Produces: the canonical CRUD pattern (`*Command` dataclasses, use cases returning `Result`, `OrganizationModel`, `SQLAlchemyOrganizationRepository`, FastAPI routes with `AuthDep`/`*Dep`, DI registration) that Plan 1 copies for every bio aggregate.

- [ ] **Step 1: Port the entire Organization slice from chem-cellar** with the rename. Read each source file and transcribe: `domain/workspace_config/organization.py` (+ `events.py`, `repository.py` Protocol, `enums.py` with `OrganizationType`), `application/workspace_config/{create_organization,update_organization,get_organization,list_organizations}.py`, `infrastructure/persistence/sqlalchemy/workspace_config/{models.py,organization_repository.py}`, `interface/routes/organizations.py`, and the DI wiring `interface/dependencies/_core.py` (the `get_auth`/`AuthDep`/`get_container`/`_get_use_case` helpers) + `interface/dependencies/_workspace_config.py` (registers the four Organization use cases into Lagom). These are shown in detail in chem-cellar's `docs/patterns-and-conventions.md` and the source files.

- [ ] **Step 2: Write the domain unit test** `tests/unit/domain/workspace_config/test_organization.py`:

```python
import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.workspace_config.enums import OrganizationType
from protcellar.domain.workspace_config.events import OrganizationCreated
from protcellar.domain.workspace_config.organization import Organization


def test_create_sets_fields_and_emits_event() -> None:
    ws = uuid.uuid4()
    org = Organization.create(workspace_id=ws, name="EBI", org_type=OrganizationType.ACADEMIC)
    assert org.name == "EBI"
    assert org.version == 1
    events = org.collect_events()
    assert len(events) == 1 and isinstance(events[0], OrganizationCreated)


def test_empty_name_raises() -> None:
    with pytest.raises(ValidationError):
        Organization.create(workspace_id=uuid.uuid4(), name="", org_type=OrganizationType.ACADEMIC)
```

Run: `uv run pytest tests/unit/domain/workspace_config -v` → PASS.

- [ ] **Step 3: Include the router** in `interface/app.py` (uncomment/add the two org lines from Task 7's template).

- [ ] **Step 4: Generate and apply the migration**

Run: `uv run alembic revision --autogenerate -m "organizations table"`
Run: `uv run alembic upgrade head`

- [ ] **Step 5: Write the API test** `tests/api/test_organizations.py` (mirrors chem-cellar's):

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_organization(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/organizations", json={"name": "Eurofins", "org_type": "cro"}
    )
    assert resp.status_code == 201
    org_id = resp.json()["id"]
    assert resp.json()["version"] == 1

    got = await client.get(f"/api/v1/organizations/{org_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "Eurofins"


@pytest.mark.asyncio
async def test_duplicate_name_conflicts(client: AsyncClient) -> None:
    await client.post("/api/v1/organizations", json={"name": "Dup", "org_type": "academic"})
    resp = await client.post("/api/v1/organizations", json={"name": "Dup", "org_type": "vendor"})
    assert resp.status_code == 409
```

(Run green at end of Task 11.)

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/domain/workspace_config \
        backend/src/protcellar/application/workspace_config \
        backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_config \
        backend/src/protcellar/interface backend/alembic/versions \
        backend/tests
git commit -m "feat(workspace-config): Organization exemplar vertical slice (domain→api)"
```

---

### Task 11: Test scaffolding, docker-compose, Makefile, .env.example — make it boot & test green

**Files:**
- Create: `backend/tests/conftest.py`, `backend/tests/api/conftest.py`, `backend/tests/fakes/fake_auth.py`
- Create: `docker-compose.yml`, `docker-compose.dev.yml`, `Makefile`, `.env.example`, `backend/Dockerfile`

**Interfaces:**
- Consumes: `create_app` building blocks, `FakeAuth`.
- Produces: a `client` pytest fixture (ASGI transport over a test app with `FakeAuth` admin override + a migrated testcontainers Postgres); `make up`, `make migrate`, `make test`, `make test-api`, `make lint` targets.

- [ ] **Step 1: Port `tests/fakes/fake_auth.py`** verbatim from chem-cellar (the `FakeAuth` class with `role`/`workspace_id`/`user_id` and `has_role`).

- [ ] **Step 2: Port `tests/api/conftest.py`** from chem-cellar (read it), adapting imports. It must: spin a testcontainers Postgres, run `alembic upgrade head` against it, build a test app via `create_app()` (or a `_create_test_app` that skips the Sentinel lifespan), override the `get_auth` dependency with `FakeAuth(role="admin", workspace_id=…)`, and yield an `httpx.AsyncClient` on an `ASGITransport`. Provide both an admin `client` and an `editor_client` fixture.

- [ ] **Step 3: Write `docker-compose.yml`** (Postgres 16 + Valkey — no RDKit cartridge, no Temporal):

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: protcellar
      POSTGRES_PASSWORD: protcellar
      POSTGRES_DB: protcellar
    ports:
      - "5433:5432"
    volumes:
      - protcellar_pg:/var/lib/postgresql/data
  valkey:
    image: valkey/valkey:8-alpine
    ports:
      - "6380:6379"
volumes:
  protcellar_pg:
```

> Ports are offset (5433/6380) so prot-cellar can run alongside chem-cellar locally without collisions.

- [ ] **Step 4: Write `.env.example`:**

```bash
DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar
CORS_ORIGINS=http://localhost:3000
APP_ENV=development
# Sentinel (point at the same identity-service as chem-cellar)
DUAR_URL=http://localhost:9003
DUAR_SERVICE_NAME=protcellar
DUAR_SERVICE_KEY=
DUAR_IDP_AUDIENCE=
```

- [ ] **Step 5: Write the `Makefile`** (trimmed from chem-cellar):

```makefile
.PHONY: up stop migrate dev test test-api test-all lint nuke

up:
	docker compose up -d postgres valkey
	cd backend && uv run alembic upgrade head

stop:
	docker compose stop

migrate:
	cd backend && uv run alembic upgrade head

dev:
	cd backend && uv run uvicorn protcellar.interface.app:app --reload --port 8001

test:
	cd backend && uv run pytest tests/unit -v && uv run lint-imports

test-api:
	cd backend && uv run pytest tests/api -v

test-all:
	cd backend && uv run pytest -v && uv run lint-imports

lint:
	cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src

nuke:
	docker compose down -v
```

> Dev server uses port 8001 (chem-cellar uses 8000) to coexist locally.

- [ ] **Step 6: Write `backend/Dockerfile`** — port chem-cellar's (uv-based multi-stage build), dropping any RDKit/system chem libs.

- [ ] **Step 7: Bring it up and run the full suite**

Run: `make up`
Run: `make test` → unit tests + import-linter all green.
Run: `make test-api` → `test_health`, `test_version`, `test_organizations` all green.
Run: `make lint` → ruff + mypy clean.

- [ ] **Step 8: Final commit**

```bash
git add backend/tests docker-compose.yml docker-compose.dev.yml Makefile .env.example backend/Dockerfile
git commit -m "build: test scaffolding (FakeAuth, api conftest), docker-compose, Makefile, env example"
```

---

## Self-Review (run after implementing)

- **Spec coverage:** Foundation tasks cover spec §3 (architecture mirror), §5.4 (Workspace Config — Organization; remaining WC aggregates deferred to where needed), §5.5 (CrossReference + identifier registry), §7 (provenance baseline — columns added per-aggregate starting in Plan 1), and the Audit context. Taxonomy/Protein/Target (spec §5.1–5.3) are Plan 1+.
- **Deferred from foundation (intentional):** `ExternalApiKey`, `DataSource`, `ControlledVocabulary` (ported when the loader/lookup tasks need them); provenance columns are introduced on the first imported aggregate (Plan 1 Organism).
- **Placeholder scan:** none — every step has concrete code or an exact source path + transform.
- **Open dependency note:** Task 7's `app.py` references `AuditEventHandler` from Task 9 — implement Task 9 before first boot (called out inline).
