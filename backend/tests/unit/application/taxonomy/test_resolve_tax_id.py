"""Unit tests for the ResolveTaxId use case.

Uses an in-memory fake repository and a minimal no-op UnitOfWork stub so no
database connection is needed.
"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Self

import pytest
from returns.result import Failure, Success

from protcellar.application.taxonomy.resolve_tax_id import ResolveTaxId, ResolveTaxIdQuery
from protcellar.domain.shared.errors import GoneError, NotFoundError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.organism import Organism
from tests.fakes.fake_auth import FakeAuth

_AUTH = FakeAuth()

# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


class FakeUnitOfWork:
    """Minimal async context manager that satisfies UnitOfWork for testing."""

    @property
    def is_active(self) -> bool:
        return False

    @property
    def session(self) -> object:  # type: ignore[override]
        raise NotImplementedError("FakeUnitOfWork has no session")

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


class FakeOrganismRepository:
    """Dict-backed in-memory fake that implements the OrganismRepository protocol."""

    def __init__(self, organisms: list[Organism] | None = None) -> None:
        # Primary keyed by id
        self._by_id: dict[uuid.UUID, Organism] = {}
        # Indexed by ncbi_tax_id (only for organisms that have one)
        self._by_tax_id: dict[int, Organism] = {}
        for org in organisms or []:
            self._store(org)

    def _store(self, org: Organism) -> None:
        self._by_id[org.id] = org
        if org.ncbi_tax_id is not None:
            self._by_tax_id[org.ncbi_tax_id] = org

    async def find_readable(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Organism | None:
        org = self._by_id.get(id)
        if org is None:
            return None
        if org.workspace_id != workspace_id:
            return None
        return org

    async def find_by_tax_id(self, tax_id: int) -> Organism | None:
        return self._by_tax_id.get(tax_id)

    async def find_children(self, parent_id: uuid.UUID) -> list[Organism]:
        return [o for o in self._by_id.values() if o.parent_id == parent_id]

    async def find_by_name(self, name: str) -> list[Organism]:
        return [o for o in self._by_id.values() if o.scientific_name == name]

    async def find_all(
        self, *, cursor_id: uuid.UUID | None = None, limit: int | None = None
    ) -> list[Organism]:
        items = list(self._by_id.values())
        if cursor_id is not None:
            # Simple cursor: skip everything up to and including cursor_id
            ids = list(self._by_id.keys())
            try:
                idx = ids.index(cursor_id)
                items = items[idx + 1 :]
            except ValueError:
                pass
        if limit is not None:
            items = items[:limit]
        return items

    async def save(self, aggregate: Organism) -> None:
        self._store(aggregate)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_organism(*, ncbi_tax_id: int, scientific_name: str = "Homo sapiens") -> Organism:
    return Organism.create(
        workspace_id=SHARED_WORKSPACE_ID,
        ncbi_tax_id=ncbi_tax_id,
        rank="species",
        scientific_name=scientific_name,
    )


def _make_use_case(organisms: list[Organism]) -> ResolveTaxId:
    return ResolveTaxId(uow=FakeUnitOfWork(), repo=FakeOrganismRepository(organisms))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_live_organism_returns_success() -> None:
    """A lookup on a live, non-merged, non-deleted organism returns it."""
    org = _make_organism(ncbi_tax_id=9606, scientific_name="Homo sapiens")
    use_case = _make_use_case([org])

    result = await use_case(ResolveTaxIdQuery(tax_id=9606), auth=_AUTH)

    assert isinstance(result, Success)
    assert result.unwrap().ncbi_tax_id == 9606
    assert result.unwrap().scientific_name == "Homo sapiens"


@pytest.mark.asyncio
async def test_resolve_unknown_tax_id_returns_not_found() -> None:
    """A tax_id not in the repository returns a NotFoundError failure."""
    use_case = _make_use_case([])

    result = await use_case(ResolveTaxIdQuery(tax_id=99999), auth=_AUTH)

    assert isinstance(result, Failure)
    assert isinstance(result.failure(), NotFoundError)


@pytest.mark.asyncio
async def test_resolve_deleted_organism_returns_gone_error() -> None:
    """A tax_id that maps to a deleted organism returns a GoneError failure."""
    org = _make_organism(ncbi_tax_id=12345, scientific_name="Deleted virus")
    org.mark_deleted()
    use_case = _make_use_case([org])

    result = await use_case(ResolveTaxIdQuery(tax_id=12345), auth=_AUTH)

    assert isinstance(result, Failure)
    assert isinstance(result.failure(), GoneError)
    assert "12345" in result.failure().message


@pytest.mark.asyncio
async def test_resolve_merged_organism_returns_target() -> None:
    """A tax_id that maps to a merged organism transparently returns the merge target."""
    target = _make_organism(ncbi_tax_id=9606, scientific_name="Homo sapiens")
    merged = _make_organism(ncbi_tax_id=99999, scientific_name="Old Homo sapiens")
    merged.mark_merged_into(target.id)

    # Verify setup: merged organism should have the merge flag set
    assert merged.is_merged
    assert merged.merged_into_id == target.id

    use_case = _make_use_case([target, merged])

    result = await use_case(ResolveTaxIdQuery(tax_id=99999), auth=_AUTH)

    assert isinstance(result, Success)
    resolved = result.unwrap()
    assert resolved.id == target.id
    assert resolved.ncbi_tax_id == 9606
    assert resolved.scientific_name == "Homo sapiens"


@pytest.mark.asyncio
async def test_resolve_merged_organism_missing_target_returns_merged_node() -> None:
    """If a merged node's target is missing from the repo, fall back to the merged node itself."""
    missing_target_id = uuid.uuid4()
    merged = _make_organism(ncbi_tax_id=77777, scientific_name="Orphaned merge")
    merged.mark_merged_into(missing_target_id)

    use_case = _make_use_case([merged])

    result = await use_case(ResolveTaxIdQuery(tax_id=77777), auth=_AUTH)

    # Falls back to returning the merged node (target not found in repo)
    assert isinstance(result, Success)
    assert result.unwrap().id == merged.id


@pytest.mark.asyncio
async def test_resolve_uses_global_workspace_for_merge_target_lookup() -> None:
    """The merge target lookup must use the organism's workspace_id (SHARED_WORKSPACE_ID)."""
    target = _make_organism(ncbi_tax_id=1, scientific_name="Root organism")
    assert target.workspace_id == SHARED_WORKSPACE_ID

    merged = _make_organism(ncbi_tax_id=2, scientific_name="Merged organism")
    merged.mark_merged_into(target.id)
    assert merged.workspace_id == SHARED_WORKSPACE_ID

    use_case = _make_use_case([target, merged])

    result = await use_case(ResolveTaxIdQuery(tax_id=2), auth=_AUTH)

    assert isinstance(result, Success)
    assert result.unwrap().id == target.id
