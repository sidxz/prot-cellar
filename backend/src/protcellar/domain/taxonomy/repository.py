"""Taxonomy repository protocols."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from protcellar.domain.taxonomy.organism import Organism

if TYPE_CHECKING:
    from protcellar.domain.taxonomy.proteome import Proteome
    from protcellar.domain.taxonomy.strain import Strain


@runtime_checkable
class OrganismRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Organism | None: ...

    async def find_by_tax_id(self, tax_id: int) -> Organism | None: ...

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Organism | None: ...

    async def find_children(self, parent_id: uuid.UUID) -> list[Organism]: ...

    async def find_by_name(self, name: str) -> list[Organism]: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        rank: str | None = None,
    ) -> list[Organism]: ...

    async def save(self, aggregate: Organism) -> None: ...


@runtime_checkable
class StrainRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Strain | None: ...

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[Strain]: ...

    async def find_by_species(
        self, workspace_id: uuid.UUID, species_organism_id: uuid.UUID
    ) -> list[Strain]: ...

    async def save(self, aggregate: Strain) -> None: ...


@runtime_checkable
class ProteomeRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Proteome | None: ...

    async def find_by_proteome_id(self, uniprot_proteome_id: str) -> Proteome | None: ...

    async def find_by_organism(self, organism_id: uuid.UUID) -> list[Proteome]: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[Proteome]: ...

    async def save(self, aggregate: Proteome) -> None: ...
