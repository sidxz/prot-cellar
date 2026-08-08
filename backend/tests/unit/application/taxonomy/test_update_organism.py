"""Unit tests for UpdateOrganism's reference_strain_id validation.

This validation is unreachable through the API today: organisms are reference
data (design doc §1.5), every create writes SHARED_WORKSPACE_ID, and
find_owned only ever matches the caller's own workspace — so no tenant can
ever load an organism to PATCH in the first place, and every real PATCH
request 404s before this code runs (see test_workspace_isolation.py). That
made the HTTP-level test of this rule (test_organisms.py's former
test_reference_strain_must_belong_to_organism) permanently unreachable, so it
was deleted rather than kept lying about what it exercises.

The rule itself is still real code with a real branch, so it stays covered
here — via fake repositories that let find_owned succeed, the same trick
test_resolve_tax_id.py uses to reach ResolveTaxId's merge-redirect branch
without a database.
"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Self

import pytest
from returns.result import Failure, Success

from protcellar.application.taxonomy.update_organism import (
    UpdateOrganism,
    UpdateOrganismCommand,
)
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.strain import Strain
from tests.fakes.fake_auth import FakeAuth

_AUTH = FakeAuth(role="admin")

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
    """Dict-backed fake — find_owned matches on workspace_id like the real one."""

    def __init__(self, organisms: list[Organism]) -> None:
        self._by_id: dict[uuid.UUID, Organism] = {o.id: o for o in organisms}

    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Organism | None:
        org = self._by_id.get(id)
        if org is None or org.workspace_id != workspace_id:
            return None
        return org

    async def save(self, aggregate: Organism) -> None:
        self._by_id[aggregate.id] = aggregate


class FakeStrainRepository:
    """Dict-backed fake — find_readable matches on workspace_id like the real one."""

    def __init__(self, strains: list[Strain]) -> None:
        self._by_id: dict[uuid.UUID, Strain] = {s.id: s for s in strains}

    async def find_readable(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Strain | None:
        strain = self._by_id.get(id)
        if strain is None or strain.workspace_id != workspace_id:
            return None
        return strain


class FakeDispatcher:
    async def dispatch_all(self, events: list) -> None:
        return None


def _make_use_case(*, organisms: list[Organism], strains: list[Strain]) -> UpdateOrganism:
    return UpdateOrganism(
        uow=FakeUnitOfWork(),  # type: ignore[arg-type]
        repo=FakeOrganismRepository(organisms),  # type: ignore[arg-type]
        strain_repo=FakeStrainRepository(strains),  # type: ignore[arg-type]
        dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
    )


def _make_organism(**overrides: object) -> Organism:
    fields: dict = {
        "workspace_id": _AUTH.workspace_id,
        "ncbi_tax_id": 1,
        "rank": "species",
        "scientific_name": "Testus organismus",
    }
    fields.update(overrides)
    return Organism.create(**fields)


def _make_strain(*, species_organism_id: uuid.UUID, **overrides: object) -> Strain:
    fields: dict = {
        "workspace_id": _AUTH.workspace_id,
        "species_organism_id": species_organism_id,
        "name": "Test strain",
    }
    fields.update(overrides)
    return Strain.create(**fields)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_reference_strain_is_rejected() -> None:
    """A strain id that doesn't exist at all must be rejected, not stored."""
    org = _make_organism()
    use_case = _make_use_case(organisms=[org], strains=[])

    result = await use_case(
        UpdateOrganismCommand(organism_id=org.id, reference_strain_id=uuid.uuid4()),
        auth=_AUTH,
    )

    assert isinstance(result, Failure)
    assert isinstance(result.failure(), ValidationError)


@pytest.mark.asyncio
async def test_reference_strain_of_a_different_species_is_rejected() -> None:
    """A real strain that belongs to some OTHER organism must be rejected."""
    org = _make_organism()
    other_species_id = uuid.uuid4()
    off_species_strain = _make_strain(species_organism_id=other_species_id)
    use_case = _make_use_case(organisms=[org], strains=[off_species_strain])

    result = await use_case(
        UpdateOrganismCommand(organism_id=org.id, reference_strain_id=off_species_strain.id),
        auth=_AUTH,
    )

    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, ValidationError)
    assert "reference_strain_id" in failure.message


@pytest.mark.asyncio
async def test_reference_strain_of_the_same_species_is_accepted() -> None:
    """A strain that genuinely belongs to this organism is a valid reference."""
    org = _make_organism()
    matching_strain = _make_strain(species_organism_id=org.id)
    use_case = _make_use_case(organisms=[org], strains=[matching_strain])

    result = await use_case(
        UpdateOrganismCommand(organism_id=org.id, reference_strain_id=matching_strain.id),
        auth=_AUTH,
    )

    assert isinstance(result, Success)
    assert result.unwrap().reference_strain_id == matching_strain.id


@pytest.mark.asyncio
async def test_explicit_none_reference_strain_skips_validation() -> None:
    """Explicit None is a legitimate 'clear the reference', not a lookup miss —
    it must succeed even with no strain in the repository at all, because the
    isinstance(ref, uuid.UUID) guard should never call find_readable for it.
    """
    org = _make_organism()
    use_case = _make_use_case(organisms=[org], strains=[])

    result = await use_case(
        UpdateOrganismCommand(organism_id=org.id, reference_strain_id=None),
        auth=_AUTH,
    )

    assert isinstance(result, Success)
    assert result.unwrap().reference_strain_id is None
