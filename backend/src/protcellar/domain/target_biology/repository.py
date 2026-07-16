"""Target-biology repository protocols."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.essentiality import Essentiality


@runtime_checkable
class EssentialityRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Essentiality | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Essentiality]: ...

    async def save(self, aggregate: Essentiality) -> None: ...


@runtime_checkable
class CrispriStrainRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> CrispriStrain | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, target_gene_id: uuid.UUID
    ) -> list[CrispriStrain]: ...

    async def save(self, aggregate: CrispriStrain) -> None: ...
