# Import Hub — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the three existing CLI importers (proteome / gene-enrichment / GO-ontology) behind one tracked `ImportRun` aggregate that is started over HTTP, executed on an **arq** background worker, reports live progress, and supports **file upload** for the DeJesus essentiality table — so the frontend (separate plan) can trigger and monitor imports.

**Architecture:** A new `imports` bounded context mirroring the existing `domain / application / infrastructure / interface` layering. `ImportRun` (domain aggregate) is persisted `QUEUED`, an arq job is enqueued, and a worker resolves an **infrastructure adapter** (per import type) that wires the existing runner with a `ProgressReporter` writing phase/progress/summary back to the run row. The three runners gain an **optional** reporter (default no-op) so the CLI scripts stay byte-for-byte behavior-identical. Application owns lightweight **param schemas + target-key**; infrastructure owns the runner-wiring adapters (they import other contexts' use cases, which the application layer must not).

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 async / Postgres / Alembic / **arq** (new) over Valkey (already in compose) / **openpyxl** (new, server-side XLSX parse) / pytest. Result type: `returns` library (`Success`/`Failure`). DI: Lagom.

## Global Constraints

- **Layering / import-linter:** `domain.imports` imports only `domain.shared`. `application.imports` imports `domain.imports`, `application.shared`, `application.auth` — **never** infrastructure or another context. Cross-context runner wiring lives ONLY in `infrastructure/ingestion/import_adapters.py` and the worker (like today's `scripts/`). Run `uv run --directory backend lint-imports` after each task.
- **CLI scripts unchanged:** the reporter parameter on every runner defaults to a no-op; `scripts/import_proteome.py`, `scripts/enrich_genes.py`, `scripts/import_go_ontology.py` keep working identically. Their existing tests must stay green.
- **Idempotency preserved:** underlying imports remain idempotent on `(source, source_record_id)` + checksum and version-gated. This plan adds tracking only — it does not touch the upsert use cases.
- **Reference data:** `ImportRun` and `ImportUpload` are global reference data → `workspace_id = GLOBAL_WORKSPACE_ID` (mirror `Gene`).
- **Admin-gated:** every mutating use case calls `require_admin(auth)`; reads call `require_authenticated(auth)`. The worker runs under the existing `_ServiceAuth` (admin) from `scripts/import_proteome.py`.
- **Audit = lifecycle only:** emit domain events for `queue / start / succeed / fail` (caught by `AuditEventHandler`). Progress/summary updates mutate + save but emit **no** event (high-frequency; would flood the audit trail).
- **Alembic:** current head is `c8a0f2e4d6b8`. New migration's `down_revision` = `c8a0f2e4d6b8`.
- **Tests:** `uv run --directory backend pytest <path> -q`. Full gates: `make test` (unit + import-linter), `make test-api`, `make lint` (ruff + ruff-format + mypy). Commit per task with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `domain/imports/__init__.py` | package marker | Create |
| `domain/imports/enums.py` | `ImportType`, `ImportStatus` | Create |
| `domain/imports/events.py` | `ImportRunQueued/Started/Succeeded/Failed` | Create |
| `domain/imports/import_run.py` | `ImportRun` aggregate (state machine) | Create |
| `domain/imports/upload.py` | `ImportUpload` aggregate (stored file) | Create |
| `domain/imports/repository.py` | `ImportRunRepository`, `ImportUploadRepository` protocols | Create |
| `infrastructure/persistence/sqlalchemy/imports/models.py` | `ImportRunModel`, `ImportUploadModel` | Create |
| `infrastructure/persistence/sqlalchemy/imports/import_run_repository.py` | repo impl | Create |
| `infrastructure/persistence/sqlalchemy/imports/import_upload_repository.py` | repo impl | Create |
| `infrastructure/persistence/sqlalchemy/metadata.py` | register new models for Alembic/Base.metadata | Modify |
| `alembic/versions/<rev>_import_runs_and_uploads.py` | `import_runs` + `import_uploads` tables | Create |
| `application/imports/progress_reporter.py` | `ProgressReporter` protocol + `NoopProgressReporter` | Create |
| `infrastructure/persistence/.../imports/db_progress_reporter.py` | `ImportRunProgressReporter` (writes to DB) | Create |
| `infrastructure/ingestion/import_runner.py` | thread reporter into `ProteomeImportRunner` | Modify |
| `infrastructure/ingestion/gene_enrichment_runner.py` | thread reporter | Modify |
| `infrastructure/ingestion/go_import_runner.py` | thread reporter | Modify |
| `application/imports/params.py` | per-type Pydantic param models + `validate_params` + `target_key` + `needs_upload` | Create |
| `application/imports/job_enqueuer.py` | `JobEnqueuer` protocol | Create |
| `application/imports/start_import.py` | `StartImportCommand` + `StartImport` use case | Create |
| `application/imports/list_import_runs.py` | `ListImportRunsQuery` + `ListImportRuns` | Create |
| `application/imports/get_import_run.py` | `GetImportRunQuery` + `GetImportRun` | Create |
| `application/imports/store_upload.py` | `StoreUpload` + `GetUpload` use cases | Create |
| `infrastructure/ingestion/dejesus_xlsx.py` | `essentiality_upload_to_tsv(filename, data) -> str` (openpyxl) | Create |
| `infrastructure/ingestion/import_adapters.py` | `ImportRuntime`, `ImportAdapter`, 3 adapters, `IMPORT_ADAPTERS` | Create |
| `infrastructure/ingestion/worker.py` | arq `WorkerSettings` + `run_import` | Create |
| `infrastructure/ingestion/arq_enqueuer.py` | `ArqJobEnqueuer` + `RedisSettings`/`REDIS_URL` | Create |
| `infrastructure/di/imports.py` | `register_imports(container)` | Create |
| `infrastructure/di/container.py` | call `register_imports` | Modify |
| `interface/routes/imports.py` | `/api/v1/imports` + `/uploads` routes | Create |
| `interface/dependencies/_imports.py` | `*Dep` aliases | Create |
| `interface/dependencies/__init__.py` | export imports deps | Modify |
| `interface/app.py` | `include_router` + dispose arq pool on shutdown | Modify |
| `pyproject.toml` | add `arq`, `openpyxl` | Modify |
| `docker-compose.yml` | `worker` service | Modify |
| `.env.example` | `REDIS_URL` | Modify |
| `tests/...` | unit + api tests per task | Create |

---

### Task 1: `ImportRun` domain aggregate, enums, events

**Files:**
- Create: `src/protcellar/domain/imports/__init__.py` (empty), `enums.py`, `events.py`, `import_run.py`
- Test: `tests/unit/domain/imports/test_import_run.py`

**Interfaces:**
- Produces `ImportType(StrEnum)`: `PROTEOME="proteome"`, `GENE_ENRICHMENT="gene_enrichment"`, `GO_ONTOLOGY="go_ontology"`.
- Produces `ImportStatus(StrEnum)`: `QUEUED="queued"`, `RUNNING="running"`, `SUCCEEDED="succeeded"`, `FAILED="failed"`, `CANCELLED="cancelled"`.
- Produces `ImportRun(AggregateRoot)` with fields: `import_type: ImportType`, `params: dict`, `target_key: str`, `status: ImportStatus`, `phase: str | None`, `processed: int | None`, `total: int | None`, `summary: dict`, `source_version: str | None`, `error: str | None`, `requested_by: uuid.UUID`, `upload_ref: uuid.UUID | None`, `started_at: datetime | None`, `finished_at: datetime | None`, plus inherited `id/created_at/updated_at/version` and `workspace_id = GLOBAL_WORKSPACE_ID`.
- Methods: `create(*, import_type, params, target_key, requested_by, upload_ref=None) -> ImportRun` (status `QUEUED`, emits `ImportRunQueued`); `start()` (QUEUED→RUNNING, sets `started_at`, emits `ImportRunStarted`); `record_progress(*, phase=None, processed=None, total=None)` (no event); `set_source_version(v)` (no event); `record_summary(summary: dict)` (no event); `succeed(summary: dict)` (RUNNING→SUCCEEDED, sets `finished_at`+`summary`, emits `ImportRunSucceeded`); `fail(error: str)` (→FAILED, sets `finished_at`+`error`, emits `ImportRunFailed`).

- [ ] **Step 1: Write the failing test** — `tests/unit/domain/imports/test_import_run.py`:

```python
from __future__ import annotations

import uuid

import pytest

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.events import (
    ImportRunFailed,
    ImportRunQueued,
    ImportRunStarted,
    ImportRunSucceeded,
)
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.shared.errors import ConflictError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def _run() -> ImportRun:
    return ImportRun.create(
        import_type=ImportType.PROTEOME,
        params={"proteome_id": "UP000001584"},
        target_key="UP000001584",
        requested_by=uuid.uuid4(),
    )


def test_create_is_queued_and_global_and_emits_queued() -> None:
    run = _run()
    assert run.status is ImportStatus.QUEUED
    assert run.workspace_id == GLOBAL_WORKSPACE_ID
    assert run.target_key == "UP000001584"
    events = run.collect_events()
    assert any(isinstance(e, ImportRunQueued) for e in events)
    assert events[0].aggregate_type == "ImportRun"


def test_lifecycle_start_progress_succeed() -> None:
    run = _run()
    run.clear_events()
    run.start()
    assert run.status is ImportStatus.RUNNING
    assert run.started_at is not None
    run.record_progress(phase="streaming entries", processed=500, total=4000)
    assert run.processed == 500 and run.total == 4000 and run.phase == "streaming entries"
    run.set_source_version("2026_02")
    run.succeed({"created": 10, "updated": 0, "skipped": 0, "failed": 0})
    assert run.status is ImportStatus.SUCCEEDED
    assert run.finished_at is not None
    assert run.summary["created"] == 10
    assert run.source_version == "2026_02"
    kinds = [type(e) for e in run.collect_events()]
    assert ImportRunStarted in kinds and ImportRunSucceeded in kinds


def test_progress_update_emits_no_event() -> None:
    run = _run()
    run.start()
    run.clear_events()
    run.record_progress(phase="x", processed=1, total=2)
    assert run.collect_events() == []


def test_fail_from_running_sets_error_and_event() -> None:
    run = _run()
    run.start()
    run.clear_events()
    run.fail("boom")
    assert run.status is ImportStatus.FAILED
    assert run.error == "boom"
    assert any(isinstance(e, ImportRunFailed) for e in run.collect_events())


def test_illegal_transition_start_when_not_queued() -> None:
    run = _run()
    run.start()
    with pytest.raises(ConflictError):
        run.start()


def test_succeed_requires_running() -> None:
    run = _run()  # still QUEUED
    with pytest.raises(ConflictError):
        run.succeed({})
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/unit/domain/imports/test_import_run.py -q`
Expected: FAIL (`ModuleNotFoundError: protcellar.domain.imports`).

- [ ] **Step 3: Implement** — `enums.py`:

```python
from __future__ import annotations

from enum import StrEnum


class ImportType(StrEnum):
    PROTEOME = "proteome"
    GENE_ENRICHMENT = "gene_enrichment"
    GO_ONTOLOGY = "go_ontology"


class ImportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

`events.py` (mirror `domain/protein_catalog/events.py` — frozen `DomainEvent` subclasses):

```python
from __future__ import annotations

from dataclasses import dataclass

from protcellar.domain.imports.enums import ImportType
from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ImportRunQueued(DomainEvent):
    import_type: ImportType


@dataclass(frozen=True, kw_only=True)
class ImportRunStarted(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportRunSucceeded(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportRunFailed(DomainEvent):
    error: str
```

`import_run.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.events import (
    ImportRunFailed,
    ImportRunQueued,
    ImportRunStarted,
    ImportRunSucceeded,
)
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ConflictError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID

_AGG = "ImportRun"


class ImportRun(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        import_type: ImportType,
        params: dict | None = None,
        target_key: str,
        requested_by: uuid.UUID,
        status: ImportStatus = ImportStatus.QUEUED,
        phase: str | None = None,
        processed: int | None = None,
        total: int | None = None,
        summary: dict | None = None,
        source_version: str | None = None,
        error: str | None = None,
        upload_ref: uuid.UUID | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.import_type = import_type
        self.params = params or {}
        self.target_key = target_key
        self.requested_by = requested_by
        self.status = status
        self.phase = phase
        self.processed = processed
        self.total = total
        self.summary = summary or {}
        self.source_version = source_version
        self.error = error
        self.upload_ref = upload_ref
        self.started_at = started_at
        self.finished_at = finished_at

    @classmethod
    def create(
        cls,
        *,
        import_type: ImportType,
        params: dict,
        target_key: str,
        requested_by: uuid.UUID,
        upload_ref: uuid.UUID | None = None,
    ) -> ImportRun:
        run = cls(
            import_type=import_type,
            params=params,
            target_key=target_key,
            requested_by=requested_by,
            upload_ref=upload_ref,
        )
        run.register_event(
            ImportRunQueued(
                aggregate_id=run.id,
                aggregate_type=_AGG,
                workspace_id=run.workspace_id,
                import_type=import_type,
            )
        )
        return run

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def start(self) -> None:
        if self.status is not ImportStatus.QUEUED:
            raise ConflictError(f"Cannot start import in status '{self.status}'")
        self.status = ImportStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self._touch()
        self.register_event(
            ImportRunStarted(aggregate_id=self.id, aggregate_type=_AGG, workspace_id=self.workspace_id)
        )

    def record_progress(
        self, *, phase: str | None = None, processed: int | None = None, total: int | None = None
    ) -> None:
        if phase is not None:
            self.phase = phase
        if processed is not None:
            self.processed = processed
        if total is not None:
            self.total = total
        self._touch()

    def set_source_version(self, version: str | None) -> None:
        self.source_version = version
        self._touch()

    def record_summary(self, summary: dict) -> None:
        self.summary = dict(summary)
        self._touch()

    def succeed(self, summary: dict) -> None:
        if self.status is not ImportStatus.RUNNING:
            raise ConflictError(f"Cannot succeed import in status '{self.status}'")
        self.status = ImportStatus.SUCCEEDED
        self.summary = dict(summary)
        self.finished_at = datetime.now(UTC)
        self._touch()
        self.register_event(
            ImportRunSucceeded(aggregate_id=self.id, aggregate_type=_AGG, workspace_id=self.workspace_id)
        )

    def fail(self, error: str) -> None:
        if self.status in (ImportStatus.SUCCEEDED, ImportStatus.FAILED, ImportStatus.CANCELLED):
            raise ConflictError(f"Cannot fail import in terminal status '{self.status}'")
        self.status = ImportStatus.FAILED
        self.error = error
        self.finished_at = datetime.now(UTC)
        self._touch()
        self.register_event(
            ImportRunFailed(
                aggregate_id=self.id, aggregate_type=_AGG, workspace_id=self.workspace_id, error=error
            )
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/unit/domain/imports/test_import_run.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/imports backend/tests/unit/domain/imports
git commit -m "feat(imports): ImportRun aggregate + enums + lifecycle events"
```

---

### Task 2: Persistence — models, repositories, migration

**Files:**
- Create: `domain/imports/upload.py`, `domain/imports/repository.py`
- Create: `infrastructure/persistence/sqlalchemy/imports/__init__.py`, `models.py`, `import_run_repository.py`, `import_upload_repository.py`
- Modify: `infrastructure/persistence/sqlalchemy/metadata.py` (import new models)
- Create: `alembic/versions/<rev>_import_runs_and_uploads.py`
- Test: `tests/api/test_import_repository.py` (DB round-trip)

**Interfaces:**
- `ImportUpload(AggregateRoot)`: `filename: str`, `content_type: str | None`, `data: bytes`, `workspace_id = GLOBAL_WORKSPACE_ID`. `create(*, filename, content_type, data) -> ImportUpload` (no event needed — transient blob).
- `ImportRunRepository(Protocol)`: `async save(run)`, `async get(id) -> ImportRun | None`, `async list(*, cursor=None, limit=50) -> list[ImportRun]` (newest first by `created_at desc, id desc`), `async find_active(import_type, target_key) -> ImportRun | None` (status in QUEUED/RUNNING).
- `ImportUploadRepository(Protocol)`: `async save(upload)`, `async get(id) -> ImportUpload | None`.

- [ ] **Step 1: Write the failing test** — `tests/api/test_import_repository.py` (uses the DB fixtures from `tests/api/conftest.py` — `database_url`, `_run_migrations`):

```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_import_run_round_trip_and_active_guard(database_url: str, _run_migrations: None) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with AsyncUnitOfWork(factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            run = ImportRun.create(
                import_type=ImportType.PROTEOME,
                params={"proteome_id": "UP000001584", "force": False},
                target_key="UP000001584",
                requested_by=uuid.uuid4(),
            )
            await repo.save(run)
            await uow.commit()

        async with AsyncUnitOfWork(factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            loaded = await repo.get(run.id)
            assert loaded is not None
            assert loaded.import_type is ImportType.PROTEOME
            assert loaded.params["proteome_id"] == "UP000001584"
            assert loaded.status is ImportStatus.QUEUED
            active = await repo.find_active(ImportType.PROTEOME, "UP000001584")
            assert active is not None and active.id == run.id
            page = await repo.list(limit=10)
            assert any(r.id == run.id for r in page)
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/api/test_import_repository.py -q`
Expected: FAIL (missing module / missing table).

- [ ] **Step 3: Implement.**

`domain/imports/upload.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


class ImportUpload(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        filename: str,
        content_type: str | None,
        data: bytes,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.filename = filename
        self.content_type = content_type
        self.data = data

    @classmethod
    def create(cls, *, filename: str, content_type: str | None, data: bytes) -> ImportUpload:
        return cls(filename=filename, content_type=content_type, data=data)
```

`domain/imports/repository.py` — two `Protocol`s with the signatures in **Interfaces** above (mirror `domain/protein_catalog/repository.py` style: `@runtime_checkable`, all `async`).

`infrastructure/persistence/sqlalchemy/imports/models.py` (mirror `GeneModel` mixins; `params`/`summary` as `JSON`, `data` as `LargeBinary`):

```python
from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class ImportRunModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "import_runs"

    import_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    upload_ref: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportUploadModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "import_uploads"

    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
```

`import_run_repository.py` — subclass `SQLAlchemyRepository[ImportRun, ImportRunModel]` (implement `_to_domain` / `_to_model` / `_update_model` mapping every field; cast `import_type`→`ImportType(...)`, `status`→`ImportStatus(...)`). Add:

```python
    async def get(self, id: uuid.UUID) -> ImportRun | None:
        return await self.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, id)

    async def list(self, *, cursor=None, limit: int = 50) -> list[ImportRun]:
        stmt = select(ImportRunModel).order_by(
            ImportRunModel.created_at.desc(), ImportRunModel.id.desc()
        )
        if cursor is not None:  # cursor = (created_at, id) from parse_ts_cursor
            ts, cid = cursor
            stmt = stmt.where(
                tuple_(ImportRunModel.created_at, ImportRunModel.id) < (ts, cid)
            )
        stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_active(self, import_type, target_key: str) -> ImportRun | None:
        stmt = select(ImportRunModel).where(
            ImportRunModel.import_type == import_type.value,
            ImportRunModel.target_key == target_key,
            ImportRunModel.status.in_([ImportStatus.QUEUED.value, ImportStatus.RUNNING.value]),
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return self._to_domain_tracked(m) if m is not None else None
```

(`from sqlalchemy import select, tuple_`.) `import_upload_repository.py` — analogous `SQLAlchemyRepository[ImportUpload, ImportUploadModel]` with a `get(id)` helper.

Register models for metadata: in `infrastructure/persistence/sqlalchemy/metadata.py`, add imports of `ImportRunModel` and `ImportUploadModel` following the existing per-context import block so `Base.metadata` (and Alembic autogenerate / `_run_migrations`) sees the tables.

Scaffold the migration: `uv run --directory backend alembic revision -m "import runs and uploads"` (gives a real `<rev>` with `down_revision = "c8a0f2e4d6b8"`). Fill `upgrade()` / `downgrade()`:

```python
def upgrade() -> None:
    op.create_table(
        "import_runs",
        sa.Column("import_type", sa.String(length=32), nullable=False),
        sa.Column("target_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=True),
        sa.Column("processed", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("upload_ref", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_import_type", "import_runs", ["import_type"])
    op.create_index("ix_import_runs_target_key", "import_runs", ["target_key"])
    op.create_index("ix_import_runs_status", "import_runs", ["status"])
    op.create_index("ix_import_runs_workspace_id", "import_runs", ["workspace_id"])
    op.create_index("ix_import_runs_created_at", "import_runs", ["created_at"])
    op.create_table(
        "import_uploads",
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("import_uploads")
    for ix in ("created_at", "workspace_id", "status", "target_key", "import_type"):
        op.drop_index(f"ix_import_runs_{ix}", table_name="import_runs")
    op.drop_table("import_runs")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/api/test_import_repository.py -q`
Expected: PASS. (If `_run_migrations` errors, confirm the new migration's `down_revision` is `c8a0f2e4d6b8` and models are imported in `metadata.py`.)

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/imports backend/src/protcellar/infrastructure/persistence backend/alembic backend/tests/api/test_import_repository.py
git commit -m "feat(imports): import_runs + import_uploads tables, models, repositories"
```

---

### Task 3: `ProgressReporter` + thread it through the three runners

**Files:**
- Create: `application/imports/progress_reporter.py`
- Create: `infrastructure/persistence/sqlalchemy/imports/db_progress_reporter.py`
- Modify: `infrastructure/ingestion/import_runner.py`, `gene_enrichment_runner.py`, `go_import_runner.py`
- Test: `tests/unit/infrastructure/test_runner_progress.py`

**Interfaces:**
- Produces `ProgressReporter(Protocol)`: `async phase(label: str) -> None`, `async advance(processed: int, total: int | None = None) -> None`, `async source_version(version: str | None) -> None`. Plus `NoopProgressReporter` implementing all as no-ops.
- Produces `ImportRunProgressReporter(import_run_id, session_factory)` — each call loads the run via a short UoW, applies `record_progress` / `set_source_version`, saves, commits. Throttle `advance` to at most one DB write per second (track last-write monotonic time; always write the final call). Use `time.monotonic()` (allowed — not `Date.now`).
- Consumes: the three runners gain a constructor kwarg `reporter: ProgressReporter = NoopProgressReporter()` and call it at phase/chunk boundaries. Existing positional args are unchanged; `reporter` is keyword-only with a default.

Runner wiring (exact call sites):
- **`ProteomeImportRunner`** (`import_runner.py`): in `__init__` add `reporter: ProgressReporter = NoopProgressReporter()`. In `run()`, after resolving proteome metadata, `await self._reporter.phase("streaming entries")` and once the entry total is known `await self._reporter.advance(0, total)`; after each `_load_chunk`, `await self._reporter.advance(summary.entries)`; before `_reconcile_membership`, `await self._reporter.phase("linking membership")`; set `await self._reporter.source_version(source_release)` once known.
- **`GeneEnrichmentRunner`** (`gene_enrichment_runner.py`): `await self._reporter.phase("fetch GFF")` before fetch; `"parse"` after; `"fetch essentiality"` if loading; `"enrich"` before `self._bulk(...)`. No per-record advance needed (single bulk call) — optionally `await self._reporter.advance(len(records), len(records))` after.
- **`GoImportRunner`** (`go_import_runner.py`): `await self._reporter.phase("probe version")`, `"download"`, `"parse"`, `"upsert"` at the matching points; `await self._reporter.source_version(version)` once resolved.

- [ ] **Step 1: Write the failing test** — `tests/unit/infrastructure/test_runner_progress.py`. Use a recording reporter and the existing runner test doubles (see `tests/unit/infrastructure/test_gene_enrichment_runner.py` for the fake client + fake bulk pattern):

```python
from __future__ import annotations

import uuid

import pytest

from protcellar.application.imports.progress_reporter import ProgressReporter


class _RecordingReporter:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.advances: list[tuple[int, int | None]] = []
        self.versions: list[str | None] = []

    async def phase(self, label: str) -> None:
        self.phases.append(label)

    async def advance(self, processed: int, total: int | None = None) -> None:
        self.advances.append((processed, total))

    async def source_version(self, version: str | None) -> None:
        self.versions.append(version)


@pytest.mark.asyncio
async def test_gene_enrichment_runner_reports_phases() -> None:
    # Arrange the existing fake gff client + fake bulk-enrich (copy the doubles
    # from tests/unit/infrastructure/test_gene_enrichment_runner.py), then:
    reporter = _RecordingReporter()
    runner = _build_runner_under_test(reporter=reporter)  # helper using the fakes
    await runner.run(uuid.uuid4(), auth=_admin())
    assert "enrich" in reporter.phases
    assert reporter.phases[0] == "fetch GFF"


@pytest.mark.asyncio
async def test_noop_default_keeps_existing_behavior() -> None:
    # Build the SAME runner WITHOUT a reporter; assert run() still returns the
    # summary unchanged (regression guard for the default no-op path).
    runner = _build_runner_under_test()
    summary = await runner.run(uuid.uuid4(), auth=_admin())
    assert summary.matched >= 0
```

(Adapt `_build_runner_under_test` / `_admin` from the existing runner test's fixtures.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_runner_progress.py -q`
Expected: FAIL (`protcellar.application.imports.progress_reporter` missing).

- [ ] **Step 3: Implement** `progress_reporter.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    async def phase(self, label: str) -> None: ...
    async def advance(self, processed: int, total: int | None = None) -> None: ...
    async def source_version(self, version: str | None) -> None: ...


class NoopProgressReporter:
    async def phase(self, label: str) -> None:
        return None

    async def advance(self, processed: int, total: int | None = None) -> None:
        return None

    async def source_version(self, version: str | None) -> None:
        return None
```

`db_progress_reporter.py` — `ImportRunProgressReporter` loading/saving the run via `AsyncUnitOfWork(session_factory)` + `SQLAlchemyImportRunRepository`, throttling `advance` with `time.monotonic()`. Then thread `reporter` into the three runners exactly at the call sites listed in **Interfaces** (default `NoopProgressReporter()`).

- [ ] **Step 4: Run to verify** — new test green AND existing runner tests still pass:

Run: `uv run --directory backend pytest tests/unit/infrastructure -q`
Expected: PASS (new + all pre-existing runner tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/application/imports backend/src/protcellar/infrastructure backend/tests/unit/infrastructure/test_runner_progress.py
git commit -m "feat(imports): ProgressReporter + thread through proteome/enrichment/GO runners"
```

---

### Task 4: Application — param schemas, `StartImport`, list/get queries, `JobEnqueuer`

**Files:**
- Create: `application/imports/params.py`, `job_enqueuer.py`, `start_import.py`, `list_import_runs.py`, `get_import_run.py`
- Test: `tests/unit/application/imports/test_start_import.py`, `test_params.py`

**Interfaces:**
- `params.py`: `ProteomeParams(BaseModel)` `{proteome_id: str, force: bool=False, dry_run: bool=False, limit: int|None=None}`; `GeneEnrichmentParams` `{tax_id: int|None=None, organism_id: uuid.UUID|None=None, gff_url: str|None=None, essentiality_url: str|None=None, essentiality_upload_ref: uuid.UUID|None=None, force: bool=False}`; `GoOntologyParams` `{force: bool=False}`. Functions: `validate_params(import_type, raw: dict) -> dict` (returns normalized dict, raises `ValidationError` on bad input), `target_key(import_type, params: dict) -> str` (proteome→`proteome_id`; enrichment→`str(organism_id or tax_id)`; GO→`"go"`), `needs_upload(import_type, params) -> bool`, `upload_ref_of(import_type, params) -> uuid.UUID | None`.
- `job_enqueuer.py`: `JobEnqueuer(Protocol)` with `async enqueue_import(import_run_id: uuid.UUID) -> None`.
- `start_import.py`: `StartImportCommand(import_type: ImportType, params: dict)`; `StartImport(uow, run_repo, enqueuer)`; `__call__(cmd, auth) -> Result[ImportRun, DomainError]` — `require_admin`; `validate_params`; reject if `run_repo.find_active(...)` returns a run → `Failure(ConflictError)`; `ImportRun.create(...)`; save; `events = uow.commit()`; dispatch (no dispatcher needed for create — but pass one for audit; reuse the dispatcher like other commands); after commit `await enqueuer.enqueue_import(run.id)`; `Success(run)`.
- `list_import_runs.py` / `get_import_run.py`: `require_authenticated`; `ListImportRunsQuery(cursor: str|None, limit: int|None)` → `Result[PageResult[ImportRun], DomainError]` (decode cursor via `parse_ts_cursor`, fetch `limit+1`, encode next via `encode_ts_cursor(last.created_at, last.id)`); `GetImportRunQuery(import_run_id)` → `Result[ImportRun, DomainError]` (`Failure(NotFoundError("ImportRun", id))` if missing). Use the same `Query` base that `application/protein_catalog/list_genes.py` imports.

> **Layering note:** `StartImport` depends on `ImportRunRepository` (domain protocol) and `JobEnqueuer` (application protocol) + a dispatcher — no infrastructure imports. The concrete `ArqJobEnqueuer` arrives in Task 7.

- [ ] **Step 1: Write the failing test** — `tests/unit/application/imports/test_start_import.py` with fakes (mirror `tests/unit/application/protein_catalog/test_bulk_enrich_genes.py`'s `_FakeUoW`/`_NoopDispatcher`/`FakeAuth`):

```python
from __future__ import annotations

import uuid

import pytest
from returns.result import Failure, Success

from protcellar.application.imports.start_import import StartImport, StartImportCommand
from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.shared.errors import ConflictError
from tests.fakes.fake_auth import FakeAuth

pytestmark = pytest.mark.asyncio


class _FakeRunRepo:
    def __init__(self, active: ImportRun | None = None) -> None:
        self.saved: list[ImportRun] = []
        self._active = active

    async def save(self, run: ImportRun) -> None:
        self.saved.append(run)

    async def find_active(self, import_type, target_key):
        return self._active

    async def get(self, id):  # unused here
        return None

    async def list(self, *, cursor=None, limit=50):
        return []


class _FakeEnqueuer:
    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []

    async def enqueue_import(self, import_run_id: uuid.UUID) -> None:
        self.enqueued.append(import_run_id)


def _admin() -> FakeAuth:
    return FakeAuth(role="admin", workspace_id=uuid.uuid4(), user_id=uuid.uuid4())


async def test_start_import_persists_queued_and_enqueues() -> None:
    repo, enq = _FakeRunRepo(), _FakeEnqueuer()
    uc = StartImport(_FakeUoW(), repo, _NoopDispatcher(), enq)  # type: ignore[arg-type]
    cmd = StartImportCommand(import_type=ImportType.PROTEOME, params={"proteome_id": "UP000001584"})
    result = await uc(cmd, auth=_admin())
    run = result.unwrap()
    assert run.status is ImportStatus.QUEUED
    assert run.target_key == "UP000001584"
    assert repo.saved and enq.enqueued == [run.id]


async def test_start_import_rejects_duplicate_active_run() -> None:
    existing = ImportRun.create(
        import_type=ImportType.PROTEOME, params={"proteome_id": "UP000001584"},
        target_key="UP000001584", requested_by=uuid.uuid4(),
    )
    repo, enq = _FakeRunRepo(active=existing), _FakeEnqueuer()
    uc = StartImport(_FakeUoW(), repo, _NoopDispatcher(), enq)  # type: ignore[arg-type]
    cmd = StartImportCommand(import_type=ImportType.PROTEOME, params={"proteome_id": "UP000001584"})
    result = await uc(cmd, auth=_admin())
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), ConflictError)
    assert enq.enqueued == []  # not enqueued
```

(Define `_FakeUoW` / `_NoopDispatcher` locally exactly as in `test_bulk_enrich_genes.py`.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/unit/application/imports -q`
Expected: FAIL (missing modules).

- [ ] **Step 3: Implement** `params.py`, `job_enqueuer.py`, `start_import.py`, `list_import_runs.py`, `get_import_run.py` per **Interfaces**. `validate_params` dispatches on `import_type` to the matching Pydantic model, calling `Model(**raw).model_dump(mode="json")` and re-raising `pydantic.ValidationError` as the domain `ValidationError`.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/unit/application/imports -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/application/imports backend/tests/unit/application/imports
git commit -m "feat(imports): StartImport + list/get queries + param schemas + JobEnqueuer protocol"
```

---

### Task 5: Upload storage + server-side XLSX parse

**Files:**
- Modify: `pyproject.toml` (add `openpyxl>=3.1`)
- Create: `infrastructure/ingestion/dejesus_xlsx.py`
- Create: `application/imports/store_upload.py`
- Test: `tests/unit/infrastructure/test_dejesus_xlsx.py`, `tests/api/test_import_uploads.py` (store + retrieve round-trip; small XLSX fixture built in-test with openpyxl)

**Interfaces:**
- `dejesus_xlsx.py`: `essentiality_upload_to_tsv(filename: str, data: bytes) -> str` — `.xlsx`→ openpyxl: find the ORF/locus column + the Final-Call column (reuse `scripts/convert_dejesus_xlsx.py` heuristics) and emit `locus\tcall` TSV; `.tsv`/`.csv`/`.txt` → decode UTF-8. Then validate by running `parse_dejesus_essentiality(text)` and raising `ValueError("no essentiality rows parsed")` if it yields an empty dict.
- `store_upload.py`: `StoreUpload(uow, upload_repo)`; `__call__(*, filename, content_type, data: bytes, auth) -> Result[ImportUpload, DomainError]` (`require_admin`; `ImportUpload.create`; save; commit; `Success`). `GetUpload(uow, upload_repo)`; `__call__(upload_id, auth) -> Result[ImportUpload, DomainError]` (`require_authenticated`; `NotFoundError` if missing).

- [ ] **Step 1: Write the failing test** — `tests/unit/infrastructure/test_dejesus_xlsx.py`:

```python
from __future__ import annotations

import io

import openpyxl
import pytest

from protcellar.infrastructure.ingestion.dejesus_xlsx import essentiality_upload_to_tsv


def _xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ORF ID", "Name", "Final Call"])
    ws.append(["Rv0667", "rpoB", "ES"])
    ws.append(["Rv0668", "rpoC", "GD"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_to_tsv_extracts_locus_and_call() -> None:
    tsv = essentiality_upload_to_tsv("table_s3.xlsx", _xlsx_bytes())
    assert "Rv0667" in tsv and "ES" in tsv


def test_tsv_passthrough() -> None:
    tsv = essentiality_upload_to_tsv("d.tsv", b"Rv0667\tES\nRv0668\tGD\n")
    assert "Rv0667" in tsv


def test_unparseable_raises() -> None:
    with pytest.raises(ValueError):
        essentiality_upload_to_tsv("empty.tsv", b"\n\n")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_dejesus_xlsx.py -q`
Expected: FAIL (module + openpyxl missing). Add `openpyxl>=3.1` to `pyproject.toml` `[project].dependencies`, then `uv sync --directory backend`.

- [ ] **Step 3: Implement** `dejesus_xlsx.py` (port `scripts/convert_dejesus_xlsx.py` column-detection into an in-memory `openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)` reader; validate via `parse_dejesus_essentiality`) and `store_upload.py`.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_dejesus_xlsx.py tests/api/test_import_uploads.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/src/protcellar/infrastructure/ingestion/dejesus_xlsx.py backend/src/protcellar/application/imports/store_upload.py backend/tests
git commit -m "feat(imports): essentiality upload storage + server-side XLSX->TSV parse"
```

---

### Task 6: Infrastructure adapters (runner wiring) + registry

**Files:**
- Create: `infrastructure/ingestion/import_adapters.py`
- Test: `tests/unit/infrastructure/test_import_adapters.py`

**Interfaces:**
- `ImportRuntime` (frozen dataclass): `session_factory: async_sessionmaker[AsyncSession]`, `dispatcher: EventDispatcherProtocol`, `reporter: ProgressReporter`, `params: dict`, `auth: AuthContext`, `load_upload: Callable[[uuid.UUID], Awaitable[bytes]]`.
- `ImportAdapter` (Protocol): `import_type: ImportType`; `async run(rt: ImportRuntime) -> dict` (returns a JSON-able summary).
- `IMPORT_ADAPTERS: dict[ImportType, ImportAdapter]` — `{PROTEOME: ProteomeAdapter(), GENE_ENRICHMENT: GeneEnrichmentAdapter(), GO_ONTOLOGY: GoOntologyAdapter()}`.
- Each adapter wires the existing runner with `rt.reporter` (manual DI exactly like the CLI scripts — `AsyncUnitOfWork(rt.session_factory)`, repos, bulk use cases, httpx client in an `async with`) and returns `dataclasses.asdict(summary)` (or a hand-built dict).

`ProteomeAdapter.run`: build `uow`, `BulkUpsertProteins`, `BulkUpsertGenes`, `UniProtClient`, `ProteomeImportRunner(uow, client, bulk, gene_bulk=gene_bulk, reporter=rt.reporter)`; `summary = await runner.run(params["proteome_id"], dry_run=..., limit=..., force=..., auth=rt.auth)`; return `asdict(summary)`.

`GeneEnrichmentAdapter.run`: resolve organism via the existing `_resolve_organism_id(uow, organism_id=..., tax_id=...)` (import from `scripts.enrich_genes`); build essentiality loader from `rt.params` — if `essentiality_upload_ref`, `async def _load(): return (await rt.load_upload(ref)).decode()`; elif `essentiality_url`, fetch; else `None`; `GeneEnrichmentRunner(bulk, MycobrowserClient(http), gff_url=..., essentiality_loader=..., reporter=rt.reporter)`; return `asdict(summary)`.

`GoOntologyAdapter.run`: `GoImportRunner(uow, reporter=rt.reporter)`; `summary = await runner.run(force=params["force"])`; return `asdict(summary)`.

- [ ] **Step 1: Write the failing test** — `tests/unit/infrastructure/test_import_adapters.py`. The adapters do heavy real wiring, so unit-test the **registry shape + GO adapter against an in-memory sqlite-free path is hard**; instead assert the registry maps every `ImportType` and that `ProteomeAdapter.run` calls the runner with the reporter by monkeypatching `ProteomeImportRunner` to a stub recording its kwargs:

```python
from __future__ import annotations

import pytest

from protcellar.domain.imports.enums import ImportType
from protcellar.infrastructure.ingestion.import_adapters import IMPORT_ADAPTERS


def test_every_import_type_has_an_adapter() -> None:
    assert set(IMPORT_ADAPTERS) == set(ImportType)
    for t, adapter in IMPORT_ADAPTERS.items():
        assert adapter.import_type is t


@pytest.mark.asyncio
async def test_proteome_adapter_passes_reporter_to_runner(monkeypatch) -> None:
    captured = {}

    class _StubRunner:
        def __init__(self, *args, reporter=None, **kwargs) -> None:
            captured["reporter"] = reporter

        async def run(self, *args, **kwargs):
            from protcellar.infrastructure.ingestion.import_runner import ImportSummary
            return ImportSummary(proteome_id="UP1", created=3)

    monkeypatch.setattr(
        "protcellar.infrastructure.ingestion.import_adapters.ProteomeImportRunner", _StubRunner
    )
    rt = _runtime(params={"proteome_id": "UP1", "force": False, "dry_run": True, "limit": None})
    summary = await IMPORT_ADAPTERS[ImportType.PROTEOME].run(rt)
    assert summary["created"] == 3
    assert captured["reporter"] is rt.reporter
```

(`_runtime(...)` builds an `ImportRuntime` with a no-op reporter, a stub `session_factory`/`dispatcher`/`load_upload`, and `FakeAuth` admin — the stub runner never touches them.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_import_adapters.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `import_adapters.py` with `ImportRuntime`, the three adapter classes, and `IMPORT_ADAPTERS`. Import `ProteomeImportRunner`, `GeneEnrichmentRunner`, `GoImportRunner`, the bulk use cases, repos, clients, `_resolve_organism_id`, and `parse_dejesus_essentiality` at module top so the monkeypatch target resolves.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/unit/infrastructure/test_import_adapters.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/ingestion/import_adapters.py backend/tests/unit/infrastructure/test_import_adapters.py
git commit -m "feat(imports): infrastructure import adapters + registry (proteome/enrichment/GO)"
```

---

### Task 7: arq worker + `ArqJobEnqueuer` + Redis settings + DI wiring

**Files:**
- Modify: `pyproject.toml` (add `arq>=0.26`)
- Create: `infrastructure/ingestion/arq_enqueuer.py`, `infrastructure/ingestion/worker.py`, `infrastructure/di/imports.py`
- Modify: `infrastructure/di/container.py` (call `register_imports`)
- Test: `tests/api/test_import_worker.py`

**Interfaces:**
- `arq_enqueuer.py`: `redis_settings_from_env() -> arq.connections.RedisSettings` (parse `os.environ.get("REDIS_URL", "redis://localhost:6380")` via `RedisSettings.from_dsn`). `ArqJobEnqueuer(JobEnqueuer)` — lazy `await create_pool(...)` cached on first `enqueue_import`; `enqueue_import(id)` → `await pool.enqueue_job("run_import", str(id))`; `async aclose()`.
- `worker.py`: `async def run_import(ctx, import_run_id: str) -> None` — build `session_factory` from `ctx["session_factory"]` and a `dispatcher` from `ctx["dispatcher"]`; load run via `SQLAlchemyImportRunRepository`; `run.start()` + save + `events = await uow.commit()` + `await dispatcher.dispatch_all(events)`; resolve `IMPORT_ADAPTERS[run.import_type]`; build `ImportRuntime` (reporter = `ImportRunProgressReporter(run.id, session_factory)`, `load_upload` via `SQLAlchemyImportUploadRepository`, `auth = _ServiceAuth()`, `dispatcher`); `summary = await adapter.run(rt)`; reload run, `run.succeed(summary)`, save + commit + dispatch. On exception: reload run, `run.fail(repr(exc))`, save + commit + dispatch (best-effort), then re-raise so arq logs it. `WorkerSettings` with `functions=[run_import]`, `redis_settings=redis_settings_from_env()`, and `on_startup`/`on_shutdown` that build an engine + `session_factory` AND a `dispatcher = EventDispatcher()` with `AuditEventHandler(session_factory)` registered (mirror the `app.py` lifespan) into `ctx`, disposing the engine + arq resources on shutdown. (In the test, pass `ctx={"session_factory": factory, "dispatcher": <EventDispatcher with audit handler>}` — or a no-op dispatcher — directly.)
- `di/imports.py`: `register_imports(container)` — `container.define(SQLAlchemyImportRunRepository, lambda c: SQLAlchemyImportRunRepository(c[AsyncUnitOfWork]))` and likewise the upload repo; `JobEnqueuer` → `Singleton(ArqJobEnqueuer)`; `StartImport`, `ListImportRuns`, `GetImportRun`, `StoreUpload`, `GetUpload` defined pulling their deps from the container (`AsyncUnitOfWork`, the repos, `EventDispatcher`, `JobEnqueuer`). Call `register_imports(container)` at the end of `create_container()` next to the other `register_*` calls.

- [ ] **Step 1: Write the failing test** — `tests/api/test_import_worker.py` drives `run_import` directly against the test DB with a stubbed adapter (no redis):

```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.infrastructure.ingestion import worker as worker_mod
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

pytestmark = pytest.mark.asyncio


def _ctx(factory) -> dict:
    # No audit handler registered → dispatch_all is a harmless no-op.
    return {"session_factory": factory, "dispatcher": EventDispatcher()}


async def _seed_queued(factory) -> uuid.UUID:
    async with AsyncUnitOfWork(factory) as uow:
        repo = SQLAlchemyImportRunRepository(uow)
        run = ImportRun.create(
            import_type=ImportType.GO_ONTOLOGY, params={"force": False},
            target_key="go", requested_by=uuid.uuid4(),
        )
        await repo.save(run)
        await uow.commit()
        return run.id


async def test_worker_drives_queued_to_succeeded(database_url, _run_migrations, monkeypatch) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        run_id = await _seed_queued(factory)

        class _StubAdapter:
            import_type = ImportType.GO_ONTOLOGY
            async def run(self, rt):
                await rt.reporter.phase("upsert")
                return {"terms_upserted": 5, "edges": 9}

        monkeypatch.setitem(worker_mod.IMPORT_ADAPTERS, ImportType.GO_ONTOLOGY, _StubAdapter())
        await worker_mod.run_import(_ctx(factory), str(run_id))

        async with AsyncUnitOfWork(factory) as uow:
            run = await SQLAlchemyImportRunRepository(uow).get(run_id)
            assert run.status is ImportStatus.SUCCEEDED
            assert run.summary["terms_upserted"] == 5
    finally:
        await engine.dispose()


async def test_worker_marks_failed_on_adapter_error(database_url, _run_migrations, monkeypatch) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        run_id = await _seed_queued(factory)

        class _BoomAdapter:
            import_type = ImportType.GO_ONTOLOGY
            async def run(self, rt):
                raise RuntimeError("kaboom")

        monkeypatch.setitem(worker_mod.IMPORT_ADAPTERS, ImportType.GO_ONTOLOGY, _BoomAdapter())
        with pytest.raises(RuntimeError):
            await worker_mod.run_import(_ctx(factory), str(run_id))

        async with AsyncUnitOfWork(factory) as uow:
            run = await SQLAlchemyImportRunRepository(uow).get(run_id)
            assert run.status is ImportStatus.FAILED
            assert "kaboom" in run.error
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/api/test_import_worker.py -q`
Expected: FAIL (`arq` import / `worker` module missing). Add `arq>=0.26` to `pyproject.toml`, `uv sync --directory backend`.

- [ ] **Step 3: Implement** `arq_enqueuer.py`, `worker.py`, `di/imports.py`, and wire `register_imports` into `create_container()`. Keep `IMPORT_ADAPTERS` importable from `worker` (re-export: `from protcellar.infrastructure.ingestion.import_adapters import IMPORT_ADAPTERS`).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/api/test_import_worker.py -q`
Expected: PASS (2 tests). Then `uv run --directory backend lint-imports` → passes.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/src/protcellar/infrastructure/ingestion/arq_enqueuer.py backend/src/protcellar/infrastructure/ingestion/worker.py backend/src/protcellar/infrastructure/di backend/tests/api/test_import_worker.py
git commit -m "feat(imports): arq worker + enqueuer + DI registration"
```

---

### Task 8: API routes + dependencies + app wiring

**Files:**
- Create: `interface/routes/imports.py`, `interface/dependencies/_imports.py`
- Modify: `interface/dependencies/__init__.py`, `interface/app.py`
- Test: `tests/api/test_imports_api.py`

**Interfaces (routes, all under `router = APIRouter(prefix="/api/v1/imports", tags=["imports"])`):**
- `POST ""` → body `StartImportBody{import_type: ImportType, params: dict}` → `StartImportDep` → `202` `ImportRunResponse`.
- `GET ""` → `cursor`, `limit` → `ListImportRunsDep` → `PaginatedResponse[ImportRunResponse]`.
- `GET "/{import_run_id}"` → `GetImportRunDep` → `ImportRunResponse`.
- `POST "/uploads"` → `UploadFile` (multipart) → call `essentiality_upload_to_tsv(file.filename, await file.read())` (catch `ValueError` → `422`) → `StoreUploadDep` with the normalized bytes → `UploadResponse{upload_ref: uuid}`.
- `ImportRunResponse.from_domain(run)` maps every field incl. `progress={processed, total}`, `summary`, `status`, `phase`, `source_version`, `error`, `created_at/started_at/finished_at`.
- `_imports.py`: `StartImportDep`, `ListImportRunsDep`, `GetImportRunDep`, `StoreUploadDep`, `GetUploadDep` via `Annotated[UseCase, Depends(_get_use_case(UseCase))]`; export from `dependencies/__init__.py`.
- `app.py`: `include_router(imports_router)`; in lifespan shutdown, `await container[JobEnqueuer].aclose()` (guard with `getattr`).

- [ ] **Step 1: Write the failing test** — `tests/api/test_imports_api.py` (uses `client` + `api_app` from `tests/api/conftest.py`; override the enqueuer to avoid redis):

```python
from __future__ import annotations

import io

import openpyxl
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from protcellar.application.imports.job_enqueuer import JobEnqueuer

pytestmark = pytest.mark.asyncio


class _FakeEnqueuer:
    def __init__(self) -> None:
        self.enqueued = []

    async def enqueue_import(self, import_run_id) -> None:
        self.enqueued.append(import_run_id)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_enqueuer(api_app: FastAPI) -> _FakeEnqueuer:
    enq = _FakeEnqueuer()
    api_app.state.container[JobEnqueuer] = enq  # lagom override; adapt if API differs
    return enq


async def test_start_import_returns_202_queued_and_enqueues(client: AsyncClient, fake_enqueuer) -> None:
    resp = await client.post(
        "/api/v1/imports",
        json={"import_type": "proteome", "params": {"proteome_id": "UP000001584"}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["import_type"] == "proteome"
    assert len(fake_enqueuer.enqueued) == 1

    listed = await client.get("/api/v1/imports")
    assert any(r["id"] == body["id"] for r in listed.json()["items"])

    got = await client.get(f"/api/v1/imports/{body['id']}")
    assert got.json()["target_key"] == "UP000001584"


async def test_duplicate_active_import_is_rejected(client: AsyncClient, fake_enqueuer) -> None:
    payload = {"import_type": "go_ontology", "params": {"force": False}}
    first = await client.post("/api/v1/imports", json=payload)
    assert first.status_code == 202
    dup = await client.post("/api/v1/imports", json=payload)
    assert dup.status_code == 409


async def test_upload_essentiality_xlsx(client: AsyncClient) -> None:
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["ORF ID", "Final Call"]); ws.append(["Rv0667", "ES"])
    buf = io.BytesIO(); wb.save(buf)
    resp = await client.post(
        "/api/v1/imports/uploads",
        files={"file": ("table_s3.xlsx", buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    assert resp.json()["upload_ref"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/api/test_imports_api.py -q`
Expected: FAIL (routes not registered → 404).

- [ ] **Step 3: Implement** `imports.py` routes, `_imports.py` deps, export them, and wire the router + pool shutdown in `app.py`. (Confirm lagom container override syntax `container[JobEnqueuer] = enq`; if lagom requires `container.define(JobEnqueuer, lambda c: enq)`, use that in the fixture instead.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --directory backend pytest tests/api/test_imports_api.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/interface backend/tests/api/test_imports_api.py
git commit -m "feat(imports): /api/v1/imports routes (start, list, get, upload) + wiring"
```

---

### Task 9: Build/deploy wiring + docs + final verification

**Files:**
- Modify: `docker-compose.yml` (add `worker` service), `.env.example` (add `REDIS_URL`)
- Modify: `backend/README` (or a docstring) — "Running imports from the worker"

- [ ] **Step 1:** Add `REDIS_URL=redis://localhost:6380` to `.env.example` (matches the `valkey` host port). Add a `worker` service to `docker-compose.yml` mirroring the backend service's build/env, with command `uv run --directory backend arq protcellar.infrastructure.ingestion.worker.WorkerSettings` and `depends_on: [postgres, valkey]`.

- [ ] **Step 2:** Run the full backend gates:

Run: `uv run --directory backend pytest tests/unit tests/api -q`
Run: `uv run --directory backend lint-imports`
Run (from repo root): `make lint`
Expected: all green (no `imports` → infrastructure/cross-context leak from domain/application).

- [ ] **Step 3 — live smoke (manual):** `make up` (Postgres + Valkey + worker). In one shell run the worker if not containerized: `uv run --directory backend arq protcellar.infrastructure.ingestion.worker.WorkerSettings`. Then:

```bash
# Start a GO ontology import (smallest), capture the id:
curl -s -XPOST localhost:8000/api/v1/imports \
  -H 'content-type: application/json' \
  -d '{"import_type":"go_ontology","params":{"force":false}}'
# Poll:
curl -s localhost:8000/api/v1/imports/<id>
```

Confirm the run transitions `queued → running → succeeded` with a populated `summary`. Then repeat for a `proteome` import (`{"proteome_id":"UP000001584"}`) and a `gene_enrichment` import (upload the DeJesus XLSX to `/uploads` first, pass `essentiality_upload_ref`). Record the final summaries.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example backend/README*
git commit -m "chore(imports): worker compose service + REDIS_URL + run docs"
```

---

## Self-Review — spec coverage

- ImportRun aggregate + registry standardization → Tasks 1, 6. ✅
- arq worker execution → Task 7. ✅
- ProgressReporter additive refactor (CLI unchanged) → Task 3. ✅
- URL defaults + upload, server-side XLSX → Tasks 5, 8. ✅
- API surface (`/imports`, `/{id}`, `/uploads`) → Task 8 (cancel deferred per spec). ✅
- Concurrency guard (active run per `(type, target)`) → Tasks 2 (`find_active`), 4 (`StartImport`), 8 (409). ✅
- Audit = lifecycle events only → Task 1 (events on start/succeed/fail; none on progress). ✅
- Migrations (`import_runs`, `import_uploads`) → Task 2. ✅
- DI + app wiring + compose worker → Tasks 7, 8, 9. ✅

## Out of scope (this plan)

- **Frontend Import section** — separate follow-on plan (`*-import-frontend.md`), authored after this lands so Orval generates the client against the real OpenAPI.
- Cancellation endpoint (`CANCELLED` status exists; endpoint deferred to spec phase 2).
- Registry-driven dynamic param descriptors; scheduled/auto-refresh imports; targets import.
