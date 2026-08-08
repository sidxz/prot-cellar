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
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
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

    async def find_by_accession(
        self, accession: str, *, workspace_id: uuid.UUID = SHARED_WORKSPACE_ID
    ) -> Protein | None:
        for p in self._by_id.values():
            if p.primary_accession == accession:
                return p
        for p in self._by_id.values():
            if accession in p.secondary_accessions:
                return p
        return None

    async def find_by_entry_name(
        self, entry_name: str, *, workspace_id: uuid.UUID = SHARED_WORKSPACE_ID
    ) -> Protein | None:
        return next((p for p in self._by_id.values() if p.entry_name == entry_name), None)


def _protein(accession: str, **kw: object) -> Protein:
    return Protein.create(
        workspace_id=SHARED_WORKSPACE_ID,
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
