"""Unit tests for StartImport use case (in-memory fakes — no DB)."""

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


class _FakeUoW:
    @property
    def is_active(self) -> bool:
        return True

    async def commit(self) -> list:
        return []

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _NoopDispatcher:
    async def dispatch_all(self, events: object) -> None:
        return None


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


async def test_start_import_sets_requested_by_from_auth() -> None:
    """requested_by should come from auth.user_id."""
    auth = _admin()
    repo, enq = _FakeRunRepo(), _FakeEnqueuer()
    uc = StartImport(_FakeUoW(), repo, _NoopDispatcher(), enq)  # type: ignore[arg-type]
    cmd = StartImportCommand(import_type=ImportType.PROTEOME, params={"proteome_id": "UP000001584"})
    result = await uc(cmd, auth=auth)
    run = result.unwrap()
    assert run.requested_by == auth.user_id


async def test_start_import_gene_enrichment() -> None:
    repo, enq = _FakeRunRepo(), _FakeEnqueuer()
    uc = StartImport(_FakeUoW(), repo, _NoopDispatcher(), enq)  # type: ignore[arg-type]
    org_id = uuid.uuid4()
    cmd = StartImportCommand(
        import_type=ImportType.GENE_ENRICHMENT,
        params={"organism_id": str(org_id)},
    )
    result = await uc(cmd, auth=_admin())
    run = result.unwrap()
    assert run.import_type is ImportType.GENE_ENRICHMENT
    assert run.target_key == str(org_id)


async def test_start_import_go_ontology() -> None:
    repo, enq = _FakeRunRepo(), _FakeEnqueuer()
    uc = StartImport(_FakeUoW(), repo, _NoopDispatcher(), enq)  # type: ignore[arg-type]
    cmd = StartImportCommand(import_type=ImportType.GO_ONTOLOGY, params={})
    result = await uc(cmd, auth=_admin())
    run = result.unwrap()
    assert run.import_type is ImportType.GO_ONTOLOGY
    assert run.target_key == "go"
