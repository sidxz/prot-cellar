"""Target-biology repository protocols."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from protcellar.domain.target_biology.vulnerability import Vulnerability


@runtime_checkable
class EssentialityRepository(Protocol):
    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Essentiality | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Essentiality]: ...

    async def save(self, aggregate: Essentiality) -> None: ...

    async def delete(self, workspace_id: uuid.UUID, id: uuid.UUID) -> None: ...


@runtime_checkable
class CrispriStrainRepository(Protocol):
    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> CrispriStrain | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, target_gene_id: uuid.UUID
    ) -> list[CrispriStrain]: ...

    async def save(self, aggregate: CrispriStrain) -> None: ...


@runtime_checkable
class VulnerabilityRepository(Protocol):
    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Vulnerability | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Vulnerability]: ...

    async def save(self, aggregate: Vulnerability) -> None: ...


@runtime_checkable
class HypomorphRepository(Protocol):
    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Hypomorph | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Hypomorph]: ...

    async def save(self, aggregate: Hypomorph) -> None: ...


@runtime_checkable
class ResistanceMutationRepository(Protocol):
    async def find_owned(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> ResistanceMutation | None: ...

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[ResistanceMutation]: ...

    async def save(self, aggregate: ResistanceMutation) -> None: ...


@runtime_checkable
class ProteinProductionRepository(Protocol):
    async def find_owned(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> ProteinProduction | None: ...

    async def find_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[ProteinProduction]: ...

    async def save(self, aggregate: ProteinProduction) -> None: ...


@runtime_checkable
class ProteinActivityAssayRepository(Protocol):
    async def find_owned(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> ProteinActivityAssay | None: ...

    async def find_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[ProteinActivityAssay]: ...

    async def save(self, aggregate: ProteinActivityAssay) -> None: ...


@runtime_checkable
class UnpublishedStructureRepository(Protocol):
    async def find_owned(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> UnpublishedStructure | None: ...

    async def find_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[UnpublishedStructure]: ...

    async def save(self, aggregate: UnpublishedStructure) -> None: ...


@runtime_checkable
class SuggestedValuesReader(Protocol):
    """Distinct values already stored for each free-text vocabulary field, across all
    eight record kinds. Keyed by ``(kind, field)`` using their plain string names —
    the domain layer does not know about the application-level ``RecordKind`` enum.
    """

    async def for_all_kinds(self) -> dict[tuple[str, str], list[str]]: ...
